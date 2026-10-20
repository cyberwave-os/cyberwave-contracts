"""The contract index: who owns each contract, and every place it is copied.

The JSON Schemas beside this module describe one payload each. This describes the
*contracts* -- owner, the tree that owns the shape, and every mirror -- facts no
schema has anywhere to put, and which used to live as hardcoded path constants in
a backend test and a shell block in ``python-sdk-gen.sh``. Copies named in neither
drifted unwatched.

Not every contract has a JSON Schema. An edge-owned or protobuf-owned payload is
still a versioned contract, so ``schema`` is optional and ``schema_owner`` names
whatever does define the shape.

Which tree may own what is a rule, not a preference -- see ``SHAPE_OWNERSHIP``.
Without it ``schema_owner`` records where a shape happens to live today, which is
how the same payload ends up defined twice in two trees and neither is wrong.

**Mirror paths are repo-relative and are not resolved here.** A published package
has no monorepo to resolve them against, and pretending otherwise is how a library
grows a dependency on the checkout that built it. They are data -- strings naming
where a copy lives -- and the repo's own tests are what resolve and verify them.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

import yaml

#: This package's own data, found relative to the module rather than searched for.
#: The previous version probed a monorepo layout and container mount points to
#: locate these; shipping them inside the package removes the search entirely.
_PACKAGE_DIR = Path(__file__).resolve().parent
SCHEMAS_DIR = _PACKAGE_DIR / "schemas"
#: Section contracts live apart from payload schemas on purpose: everything in
#: ``schemas/`` is listed by ``GET /api/v1/contracts`` and embedded in the SDK, and
#: section contracts stay out of that public surface until they are settled.
SECTIONS_DIR = _PACKAGE_DIR / "sections"
MANIFEST_PATH = _PACKAGE_DIR / "manifest.yml"

#: Where the schema trees sit in the repository, for messages and for repo tooling
#: that has a checkout. Not used to find anything at runtime.
_PACKAGE_RELATIVE = "cyberwave-contracts/cyberwave_contracts"
SCHEMAS_RELATIVE = f"{_PACKAGE_RELATIVE}/schemas"
SECTIONS_RELATIVE = f"{_PACKAGE_RELATIVE}/sections"

#: Payload identity key spellings in use. ``version`` is the older spelling on the two
#: manifest contracts and carries a contract id, not a version; it is listed so a
#: third spelling cannot appear unnoticed, not because both are equally correct.
ID_FIELDS = frozenset({"contract", "version", "schema_version"})

#: Payloads identify their complete wire contract. Overlays constrain fields on
#: another payload and deliberately do not add an identity field to that wire.
#: Topic contracts are complete payloads identified by the MQTT topic they are
#: published on rather than by a field: the flat twin telemetry topics predate the
#: identity rule and have deployed publishers (drivers, an Android app) that send
#: no contract id. Requiring one would be a v2 those publishers do not emit, so
#: their schemas name the topic in a :data:`TOPIC_ANNOTATION` instead.
#: Sections describe one part of a stored JSON field; they are identified by where
#: they live, not by a field inside them.
CONTRACT_KINDS = frozenset({"payload", "overlay", "topic", "section"})

#: The kinds whose payload names its own contract in ``id_field``. Every other
#: kind declares ``id_field: null``.
SELF_IDENTIFYING_KINDS = frozenset({"payload"})

#: The root schema annotation a ``topic`` contract names its topic with: relative
#: to the environment prefix, with ``{twin_uuid}``-style placeholders. An ``x-``
#: key, so validators and the model generator treat it as documentation.
TOPIC_ANNOTATION = "x-mqtt-topic"

#: What a section holds, which decides who may write it. The Kubernetes
#: spec/status split applied to the JSON fields: user configuration and curated
#: catalog definitions are client-writable and validated; reported state is
#: written by runtime processes such as device drivers and the platform; derived values are computed
#: for reading; bookkeeping is server-only.
SECTION_KINDS = frozenset(
    {"configuration", "catalog", "reported", "derived", "bookkeeping"}
)

#: How a twin inherits an asset section. Only ``Asset.*`` sections carry one, and
#: an asset section that omits it is ``instance_only``: never inherited.
MERGE_STRATEGIES = frozenset(
    {"instance_only", "replace", "narrow_only", "seed_once", "precedence_chain"}
)

#: The models whose JSON fields sections describe, as ``location`` spells them.
SECTION_ENTITIES = frozenset(
    {
        "Asset",
        "ControllerPolicy",
        "Environment",
        "EnvironmentObject",
        "MLModel",
        "PolicyJointBinding",
        "Twin",
    }
)

#: ``Entity.field[.path...]``, e.g. ``Environment.settings.geo``.
_LOCATION_PATTERN = re.compile(r"^[A-Z][A-Za-z]*(\.[a-z_][a-z0-9_]*)+$")

#: Derived, not restated: an owner exists exactly when it has a rule below. A
#: second spelling of this list is a way for the two to disagree.
SCHEMA_OWNERS: frozenset[str]

#: What each shape owner is entitled to define, and the source key that must name
#: the definition. The rule is directional: a payload the robot *reports* is state
#: and its shape belongs in ``common/protobuf``, where the field is typed and the
#: unit sits on the type; a payload the platform *issues* is a command or a plan
#: and its shape belongs in this package's ``schemas/``, where it is validated
#: per request and versioned with the API. ``python`` is neither -- it is the escape
#: hatch for a shape no schema defines, and every entry using it names the module
#: that is the definition of record.
#:
#: Enforced by :func:`validate_ownership`. An entry that satisfies the key checks
#: but sits in the wrong tree is the failure this cannot catch; the rule is
#: written here so that review has something to check it against.
SHAPE_OWNERSHIP: dict[str, dict[str, Any]] = {
    "json_schema": {
        "source_key": "schema",
        # One home, inside this package. These schemas are read by the SDK, by
        # edge components, and by partners writing a driver against the published
        # wheel -- none of which can import a Django app directory. The backend
        # serves them over /api/v1/contracts, which is a use, not ownership.
        "trees": (SCHEMAS_RELATIVE, SECTIONS_RELATIVE),
        "suffix": ".schema.json",
        "defines": (
            "commands, plans, transport overlays and stored sections defined as "
            "JSON Schema"
        ),
    },
    "protobuf": {
        "source_key": "proto_source",
        "trees": ("common/protobuf/proto",),
        "suffix": ".proto",
        "defines": "state -- payloads a robot, driver or simulator reports",
    },
    "python": {
        "source_key": "python_source",
        # No tree, because this owner is defined by what does *not* describe the
        # shape -- no JSON Schema -- rather than by where it lives. It covers a
        # dataclass on the edge runtime and a backend validator whose cross-field
        # rules a schema could only restate in part.
        "trees": (),
        "suffix": ".py",
        "defines": "shapes no JSON Schema defines, held by a Python module",
    },
}

SCHEMA_OWNERS = frozenset(SHAPE_OWNERSHIP)

#: How a mirror is kept in step with the definition. The first two describe a
#: *copy* and differ only in what verifies it; ``dependency`` describes a consumer
#: that installs the definition instead of copying it, so there is nothing to
#: drift and nothing to check. Recording it is still worth it -- the entry is how
#: you find every consumer of a contract before changing it.
#:
#: There is no kind for a copy that nothing verifies. There used to be
#: (``unchecked``); its last three users now import the definition, and leaving
#: the kind in place would let the next hand copy be recorded instead of fixed.
SYNC_KINDS = frozenset({"generated", "field_names", "dependency"})

#: Mirrors that copy the definition, and so can drift from it. ``dependency``
#: mirrors are excluded by construction rather than by exception -- subtracted
#: from :data:`SYNC_KINDS` rather than re-listed, so a new sync kind is covered
#: here the moment it is added there.
COPYING_SYNC_KINDS = SYNC_KINDS - {"dependency"}


@dataclass(frozen=True)
class Mirror:
    path: str
    language: str
    sync: str


@dataclass(frozen=True)
class Contract:
    id: str
    owner: str
    schema_owner: str
    id_field: str | None
    python_source: str | None
    mirrors: tuple[Mirror, ...]
    kind: str = "payload"
    schema: str | None = None
    proto_source: str | None = None
    #: Section contracts only: where the section is stored, what it holds, and
    #: (asset sections only) how a twin inherits it.
    location: str | None = None
    section_kind: str | None = None
    merge: str | None = None

    @property
    def copied_mirrors(self) -> tuple[Mirror, ...]:
        """Mirrors holding a copy of the definition, and so able to drift from it.

        A ``dependency`` mirror installs the definition rather than copying it, so
        its ``path`` names a package rather than a file in this checkout. Drift
        checks iterate this instead of :attr:`mirrors` so that distinction is made
        once here rather than re-derived at each call site.
        """
        return tuple(m for m in self.mirrors if m.sync in COPYING_SYNC_KINDS)

    @property
    def shape_source(self) -> str | None:
        """The path that defines this contract's shape, per :data:`SHAPE_OWNERSHIP`.

        Distinct from ``python_source``, which a protobuf- or JSON-Schema-owned
        contract may also carry: that one is the backend's reader, not the
        definition. Conflating them is what lets a hand-written mirror quietly
        become the thing everyone edits.
        """
        key = SHAPE_OWNERSHIP[self.schema_owner]["source_key"]
        value: str | None = getattr(self, key)
        return value

    @property
    def schema_path(self) -> Path:
        """The JSON Schema backing this contract.

        Only meaningful when ``schema`` is set; callers gate on ``has_schema``
        rather than catching this.
        """
        if self.schema is None:
            raise ValueError(f"{self.id} declares no JSON Schema")
        directory = SECTIONS_DIR if self.kind == "section" else SCHEMAS_DIR
        return directory / f"{self.id}.schema.json"

    @property
    def has_schema(self) -> bool:
        return self.schema is not None

    def schema_json(self) -> dict[str, Any]:
        """The parsed schema.

        Cached by path: these files are package data and cannot change without a
        reinstall, and the drift checks read each of them many times over.
        Returns a fresh copy, so a caller that mutates one does not edit the
        cache out from under the next.
        """
        return deepcopy(_read_schema(self.schema_path))


@cache
def _read_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_contracts() -> tuple[Contract, ...]:
    document = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return tuple(
        Contract(
            id=entry["id"],
            kind=entry.get("kind", "payload"),
            owner=entry["owner"],
            schema_owner=entry["schema_owner"],
            # Sections are identified by `location`, so they omit it.
            id_field=entry.get("id_field"),
            schema=entry.get("schema"),
            proto_source=entry.get("proto_source"),
            python_source=entry.get("python_source"),
            location=entry.get("location"),
            section_kind=entry.get("section_kind"),
            merge=entry.get("merge"),
            mirrors=tuple(
                Mirror(
                    path=mirror["path"],
                    language=mirror["language"],
                    sync=mirror["sync"],
                )
                for mirror in entry.get("mirrors", ())
            ),
        )
        for entry in document["contracts"]
    )


def validate_ownership(contract: Contract) -> list[str]:
    """Reasons *contract* violates :data:`SHAPE_OWNERSHIP`, empty when it complies.

    Returns reasons rather than raising so a caller can report every offending
    entry at once instead of one per run.
    """
    rule = SHAPE_OWNERSHIP[contract.schema_owner]
    source_key = str(rule["source_key"])
    reasons: list[str] = []

    source = contract.shape_source
    if source is None:
        return [
            f"schema_owner {contract.schema_owner!r} requires {source_key!r} to "
            f"name the definition ({rule['defines']})"
        ]

    if not source.endswith(str(rule["suffix"])):
        reasons.append(f"{source_key} {source!r} does not end in {rule['suffix']!r}")

    trees: tuple[str, ...] = tuple(rule["trees"])
    if trees and not any(source.startswith(f"{tree}/") for tree in trees):
        legal = " or ".join(f"{tree}/" for tree in trees)
        reasons.append(
            f"{contract.schema_owner} owns {rule['defines']}, which live in "
            f"{legal} — {source!r} does not"
        )

    # A shape has exactly one owner. Naming a second owner's source key makes the
    # index ambiguous about which copy is the definition, which is the state the
    # index exists to end. ``python_source`` is exempt: a JSON-Schema- or
    # protobuf-owned contract legitimately names the backend's reader alongside
    # its definition, and only the ``python`` owner treats it as the shape.
    for other_rule in SHAPE_OWNERSHIP.values():
        other_key = str(other_rule["source_key"])
        if other_key in {source_key, "python_source"}:
            continue
        if getattr(contract, other_key) is not None:
            reasons.append(
                f"schema_owner is {contract.schema_owner!r} but {other_key!r} is "
                f"also set; a shape has one owner, not two"
            )
    return reasons


def validate_section(contract: Contract) -> list[str]:
    """Reasons *contract* breaks the section rules, empty when it complies.

    A section is identified by where it is stored, so it carries ``location``
    instead of an ``id_field``, says what it holds (:data:`SECTION_KINDS`), and --
    only when it lives on an asset -- how a twin inherits it
    (:data:`MERGE_STRATEGIES`). The section-only keys are refused on every other
    kind, so a payload cannot half-declare itself a section.
    """
    section_keys = {
        "location": contract.location,
        "section_kind": contract.section_kind,
        "merge": contract.merge,
    }
    is_section = contract.kind == "section"
    reasons: list[str] = []
    if contract.schema is not None and is_section != contract.schema.startswith(
        f"{SECTIONS_RELATIVE}/"
    ):
        reasons.append(
            f"a section's schema lives in {SECTIONS_RELATIVE}/, not {contract.schema!r}"
            if is_section
            else f"a {contract.kind}'s schema lives in {SCHEMAS_RELATIVE}/; "
            f"{SECTIONS_RELATIVE}/ holds section contracts only"
        )
    if not is_section:
        reasons += [
            f"{key} is only meaningful on a section, not on a {contract.kind}"
            for key, value in section_keys.items()
            if value is not None
        ]
        return reasons

    if contract.id_field is not None:
        reasons.append(
            "a section is identified by its location; it must not declare an "
            f"id_field (got {contract.id_field!r})"
        )

    location = contract.location
    if location is None:
        reasons.append(
            "a section must declare its location, e.g. Asset.metadata.drivers"
        )
    elif not _LOCATION_PATTERN.match(location):
        reasons.append(
            f"location {location!r} must read Entity.field[.path], e.g. "
            "Environment.settings.geo"
        )
    elif (entity := location.split(".", 1)[0]) not in SECTION_ENTITIES:
        reasons.append(
            f"location {location!r} names {entity!r}, which is not one of "
            f"{sorted(SECTION_ENTITIES)}"
        )

    if contract.section_kind not in SECTION_KINDS:
        reasons.append(
            f"section_kind must be one of {sorted(SECTION_KINDS)}, got "
            f"{contract.section_kind!r}"
        )

    if contract.merge is not None:
        if location is None or not location.startswith("Asset."):
            reasons.append(
                "merge describes how a twin inherits an asset section; only "
                f"Asset.* sections may declare it (location is {location!r})"
            )
        if contract.merge not in MERGE_STRATEGIES:
            reasons.append(
                f"merge must be one of {sorted(MERGE_STRATEGIES)}, got "
                f"{contract.merge!r}"
            )

    return reasons
