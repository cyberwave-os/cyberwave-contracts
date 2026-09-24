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
MANIFEST_PATH = _PACKAGE_DIR / "manifest.yml"

#: Where the schema tree sits in the monorepo, for messages and for repo tooling
#: that has a checkout. Not used to find anything at runtime.
SCHEMAS_RELATIVE = "cyberwave-contracts/cyberwave_contracts/schemas"

#: Payload identity key spellings in use. ``version`` is the older spelling on the two
#: manifest contracts and carries a contract id, not a version; it is listed so a
#: third spelling cannot appear unnoticed, not because both are equally correct.
ID_FIELDS = frozenset({"contract", "version", "schema_version"})

#: Payloads identify their complete wire contract. Overlays constrain fields on
#: another payload and deliberately do not add an identity field to that wire.
CONTRACT_KINDS = frozenset({"payload", "overlay"})

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
        "trees": (SCHEMAS_RELATIVE,),
        "suffix": ".schema.json",
        "defines": "commands, plans, and transport overlays defined as JSON Schema",
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

#: How a mirror is kept in step with the definition. The first three describe a
#: *copy* and differ only in what verifies it; ``dependency`` describes a consumer
#: that installs the definition instead of copying it, so there is nothing to
#: drift and nothing to check. Recording it is still worth it -- the entry is how
#: you find every consumer of a contract before changing it.
SYNC_KINDS = frozenset({"generated", "field_names", "unchecked", "dependency"})

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
        return SCHEMAS_DIR / f"{self.id}.schema.json"

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
            id_field=entry["id_field"],
            schema=entry.get("schema"),
            proto_source=entry.get("proto_source"),
            python_source=entry.get("python_source"),
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
