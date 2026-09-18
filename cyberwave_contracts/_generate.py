"""Generate pydantic models from the contract schemas in ``schemas/``.

The schema is the contract; this makes it executable. A model generated from the
schema cannot drift from it, which a hand-written validator can and does -- see
``test_contract_conformance.py`` for the divergences that exist today.

Scoped deliberately to the constructs the contract schemas actually use rather
than the whole of JSON Schema: anything else raises :class:`UnsupportedConstruct`
instead of generating something subtly wrong. Widening it is a deliberate act
with a test, not a silent fallback.

Two mappings are load-bearing and easy to get wrong; both are commented at the
site: the disjoint ``anyOf`` domain on ``duration_ms``, and the numeric/boolean
guards that stop pydantic's lax mode accepting a string where JSON Schema wants
a number.

Regenerate every model (and format the output, which this does not do itself)::

    make -C cyberwave-contracts models

Output is committed. ``test_generated_models_are_current`` fails if a schema
changes without it.

This writes one module per schema **and** ``models/__init__.py``. The module
name, the root class and the nested class names are all things this generator
already computes, so re-stating them by hand only created a step that could be
forgotten -- and the guards to catch forgetting it. Adding a contract is now a
schema plus ``make models``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from cyberwave_contracts.manifest import SCHEMAS_DIR

_PRIMITIVES = {
    "number": "Number",
    "integer": "Integer",
    "string": "str",
    "boolean": "Boolean",
}


class UnsupportedConstruct(Exception):
    """A schema used something the generator does not model. Never guess."""


#: Every keyword the generator actually honours. The type-level guards above stop
#: a model being *looser* than its schema about types; this stops the same thing
#: happening one level down, where a dropped ``minLength`` or ``pattern`` is
#: invisible: the model still validates, just without the rule. Anything not
#: listed raises rather than being ignored, so widening the generator stays a
#: deliberate act. Add a keyword here only together with the code that honours it.
_MODELLED_KEYWORDS = frozenset(
    {
        "type",
        "title",
        "description",
        "default",
        "const",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "$defs",
        "$ref",
        "items",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "anyOf",
        "dependentRequired",
    }
)

#: Bookkeeping that identifies the document rather than constraining the payload.
#: Legal at the root only; on a property it is a mistake worth reporting.
_DOCUMENT_KEYWORDS = frozenset({"$schema", "$id"})


def _unmodelled(spec: dict[str, Any], *, root: bool = False) -> list[str]:
    """Keywords in *spec* the generator would silently drop.

    ``x-`` keys are annotations by JSON Schema convention -- they carry no
    validation rule, so ignoring them loses nothing. Everything else does.
    """
    allowed = _MODELLED_KEYWORDS | (_DOCUMENT_KEYWORDS if root else frozenset())
    return sorted(k for k in spec if k not in allowed and not k.startswith("x-"))


def _declares_object_properties(spec: dict[str, Any]) -> bool:
    """Does *spec* become a generated class?

    The only place an object-level rule can be attached. ``type`` may be a list
    (``["object", "null"]``), which is how every nullable object in these
    schemas is spelled.
    """
    json_type = spec.get("type")
    types = json_type if isinstance(json_type, list) else [json_type]
    return "object" in types and bool(spec.get("properties"))


def _py_str_tuple(values: list[str]) -> str:
    """A Python tuple literal of strings, double-quoted as ruff format wants."""
    inner = ", ".join(json.dumps(v) for v in sorted(values))
    return f"({inner},)" if len(values) == 1 else f"({inner})"


def _pascal(text: str) -> str:
    """artifactFile / policy_artifact_manifest.v1 -> ArtifactFile / ...V1"""
    parts = re.split(r"[._\-]", text)
    out = []
    for part in parts:
        if not part:
            continue
        out.append(part[0].upper() + part[1:])
    return "".join(out)


class Generator:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema
        self.contract_id = schema["$id"].rsplit("/", 1)[-1].removesuffix(".schema.json")
        self.defs: dict[str, Any] = schema.get("$defs", {})
        #: Emitted leaf-first, so a class is always defined before the class that
        #: references it. Avoids relying on pydantic forward-ref rebuilding.
        self.classes: list[str] = []
        #: The same classes by name, for the package __init__ this generator also
        #: writes. Kept beside the sources so the re-export list cannot name a
        #: class the module does not define.
        self.class_names: list[str] = []
        #: Both set by :meth:`run`: the model the contract id maps to, and the
        #: module source, kept so the __init__ writer need not generate twice.
        self.root_class = ""
        self.source = ""
        self.emitted: dict[str, str] = {}

    # -- type mapping ------------------------------------------------------

    def _ref_target(self, ref: str) -> str:
        if not ref.startswith("#/$defs/"):
            raise UnsupportedConstruct(f"only #/$defs/ refs are supported, got {ref!r}")
        name = ref.removeprefix("#/$defs/")
        if name not in self.defs:
            raise UnsupportedConstruct(f"{ref!r} does not resolve")
        return self._emit_object(_pascal(name), self.defs[name])

    def _annotation(
        self, prop: str, spec: dict[str, Any], owner: str
    ) -> tuple[str, list[str]]:
        """Return (annotation, Field constraints) for one property schema."""
        if unknown := _unmodelled(spec):
            raise UnsupportedConstruct(
                f"{prop}: schema uses {unknown}, which this generator does not "
                "model. Generating anyway would emit a model more permissive "
                "than the contract it claims to implement."
            )
        # ``dependentRequired`` is honoured in _emit_object, and _emit_object is
        # reached from here only for an object that declares properties. On a
        # $ref, an enum, an open bag mapped to dict[str, Any], an array or a
        # scalar there is no class to hang the rule on, so listing the keyword in
        # _MODELLED_KEYWORDS would let it vanish in silence -- the one thing this
        # generator exists to refuse. Checked before the branches, not inside
        # each of them, so a branch added later inherits the guard.
        if "dependentRequired" in spec and not _declares_object_properties(spec):
            raise UnsupportedConstruct(
                f"{prop}: dependentRequired needs an object with declared "
                "properties to attach to; here it would be dropped."
            )

        constraints: list[str] = []

        if "$ref" in spec:
            return self._ref_target(spec["$ref"]), constraints

        if "const" in spec:
            return f"Literal[{spec['const']!r}]", constraints

        # Checked before `type`: several properties carry `enum` with no `type`.
        if "enum" in spec:
            values = ", ".join(repr(v) for v in spec["enum"])
            return f"Literal[{values}]", constraints

        json_type = spec.get("type")

        # `"type": ["string", "null"]` -- nullable is a union member on the wire,
        # not an absent field. It stays required if `required` says so; what it
        # gains is `| None`, and that distinction is why this is not folded into
        # the optional-field handling below.
        nullable = False
        if isinstance(json_type, list):
            members = [t for t in json_type if t != "null"]
            nullable = "null" in json_type
            if len(members) != 1:
                raise UnsupportedConstruct(f"{prop}: unsupported union {json_type!r}")
            json_type = members[0]
            spec = {**spec, "type": json_type}

        if json_type == "array":
            items = spec.get("items")
            if not items:
                raise UnsupportedConstruct(f"{prop}: array without items")
            item_type, _ = self._annotation(prop, items, owner)
            annotation = f"list[{item_type}]"
        elif json_type == "object":
            if spec.get("properties"):
                annotation = self._emit_object(f"{owner}{_pascal(prop)}", spec)
            else:
                # An object with no declared properties is an open bag. Modelling
                # it as a class would invent a shape the contract does not state.
                annotation = "dict[str, Any]"
        elif json_type in _PRIMITIVES:
            annotation = _PRIMITIVES[json_type]
            if "minimum" in spec:
                constraints.append(f"ge={spec['minimum']}")
            if "maximum" in spec:
                constraints.append(f"le={spec['maximum']}")
            # 2020-12 spells an exclusive bound as the number itself. draft-04
            # spelled it `true` alongside `minimum`, and that form would emit
            # `gt=True` -- a bound of 1, silently, on every value. Refuse it.
            for keyword, param in (
                ("exclusiveMinimum", "gt"),
                ("exclusiveMaximum", "lt"),
            ):
                if keyword not in spec:
                    continue
                bound = spec[keyword]
                if isinstance(bound, bool):
                    raise UnsupportedConstruct(
                        f"{prop}: {keyword} is draft-04's boolean form; these "
                        "schemas are 2020-12, where it carries the bound itself."
                    )
                constraints.append(f"{param}={bound}")
        else:
            raise UnsupportedConstruct(f"{prop}: unsupported type {json_type!r}")

        if nullable:
            annotation = f"{annotation} | None"
        return annotation, constraints

    def _anyof_validator(self, prop: str, spec: dict[str, Any]) -> str | None:
        """Model the one anyOf shape the contracts use: a const escape OR a range.

        `duration_ms` is `{anyOf: [{const: 0}, {minimum: 50, maximum: 30000}]}` --
        a disjoint domain that ge/le cannot express, because 0 is legal and 1..49
        is not. Emitting a validator keeps that rule in the generated model rather
        than widening it to 0..30000, which is what the obvious mapping does and
        what nothing downstream would catch.
        """
        branches = spec.get("anyOf")
        if not branches:
            return None

        consts = [b["const"] for b in branches if "const" in b]
        ranges = [b for b in branches if "minimum" in b or "maximum" in b]
        if not consts or len(ranges) != 1:
            raise UnsupportedConstruct(f"{prop}: unsupported anyOf {branches!r}")

        lo, hi = ranges[0].get("minimum"), ranges[0].get("maximum")
        allowed = " or ".join(f"v == {c}" for c in consts)
        spelled = "/".join(str(c) for c in consts)
        return (
            f"\n    @field_validator({prop!r})\n"
            f"    @classmethod\n"
            f"    def _check_{prop}(cls, v: int) -> int:\n"
            f"        if {allowed}:\n"
            f"            return v\n"
            f"        if {lo} <= v <= {hi}:\n"
            f"            return v\n"
            f"        raise ValueError(\n"
            f'            "{prop} must be {spelled} or between {lo} and {hi}"\n'
            f"        )\n"
        )

    def _dependent_required_validator(
        self, name: str, spec: dict[str, Any]
    ) -> str | None:
        """Model ``dependentRequired``: if one property is present, another must be.

        Presence, not truthiness. ``model_fields_set`` is exactly the set of keys
        the payload carried, so an explicit ``null`` still counts as present --
        which is what JSON Schema means, and what the hand-written check in
        ``cyberwave-sim/control/locomotion_policy.py`` (``if minimums and ...``)
        gets wrong for a falsy value. Emitting the rule rather than dropping it
        is the difference between a model that enforces the contract and one that
        only looks like it does.
        """
        rules = spec.get("dependentRequired")
        if not rules:
            return None
        if not isinstance(rules, dict) or not all(
            isinstance(trigger, str)
            and isinstance(dependents, list)
            and dependents
            and all(isinstance(d, str) for d in dependents)
            for trigger, dependents in rules.items()
        ):
            raise UnsupportedConstruct(
                f"{name}: dependentRequired must map a property name to a "
                f"non-empty list of property names, got {rules!r}"
            )

        pairs = "".join(
            f"            ({json.dumps(trigger)}, {_py_str_tuple(dependents)}),\n"
            for trigger, dependents in sorted(rules.items())
        )
        return (
            '\n    @model_validator(mode="after")\n'
            f"    def _check_dependent_required(self) -> {name}:\n"
            '        """Schema `dependentRequired`: one key present requires another.\n'
            "\n"
            "        Presence, not truthiness -- `model_fields_set` is the set of\n"
            "        keys the payload carried, so an explicit null still counts.\n"
            '        """\n'
            "        for trigger, dependents in (\n"
            f"{pairs}"
            "        ):\n"
            "            if trigger not in self.model_fields_set:\n"
            "                continue\n"
            "            missing = [\n"
            "                d for d in dependents if d not in self.model_fields_set\n"
            "            ]\n"
            "            if missing:\n"
            "                raise ValueError("
            "f\"{trigger} requires {', '.join(missing)}\")\n"
            "        return self\n"
        )

    # -- class emission ----------------------------------------------------

    def _emit_object(
        self, name: str, spec: dict[str, Any], *, root: bool = False
    ) -> str:
        if unknown := _unmodelled(spec, root=root):
            raise UnsupportedConstruct(
                f"{name}: schema uses {unknown}, which this generator does not "
                "model. Generating anyway would emit a model more permissive "
                "than the contract it claims to implement."
            )
        if name in self.emitted:
            return name
        # Reserve the name before recursing so a self-referential $def terminates.
        self.emitted[name] = name

        properties: dict[str, Any] = spec.get("properties", {})
        required = set(spec.get("required", []))

        fields: list[str] = []
        validators: list[str] = []

        # Required first, so the generated class reads like the schema's own list.
        for prop in sorted(properties, key=lambda p: (p not in required, p)):
            pspec = properties[prop]
            annotation, constraints = self._annotation(prop, pspec, name)
            validator = self._anyof_validator(prop, pspec)
            if validator:
                validators.append(validator)

            if description := pspec.get("description"):
                constraints.append(f"description={description!r}")

            if prop in required:
                default = "..."
            elif "default" in pspec:
                default = repr(pspec["default"])
            else:
                # Absent is distinct from null: a field the payload omits stays
                # None here, and `exclude_none` on dump keeps it omitted rather
                # than writing an explicit null another consumer has to handle.
                if not annotation.endswith("| None"):
                    annotation = f"{annotation} | None"
                default = "None"

            if constraints:
                fields.append(
                    f"    {prop}: {annotation} = Field({default}, "
                    f"{', '.join(constraints)})"
                )
            else:
                fields.append(f"    {prop}: {annotation} = {default}")

        if dependent_required := self._dependent_required_validator(name, spec):
            validators.append(dependent_required)

        # additionalProperties is load-bearing, not incidental: an open root lets
        # a v2 payload carry fields this version has never heard of, and a model
        # that dropped them would silently strip another component's data on a
        # round-trip. `false` is equally deliberate where a schema states it.
        extra = "allow" if spec.get("additionalProperties") is not False else "forbid"

        title = spec.get("title", name)
        description = spec.get("description", "")
        body = "\n".join(fields) if fields else "    pass"

        # A $def usually carries neither title nor description, and emitting the
        # blank summary+body form for those produces a docstring ruff format
        # collapses -- which reads as generator drift to the freshness test. Emit
        # the form ruff would leave alone.
        if description:
            docstring = f'    """{title}\n\n    {description}\n    """\n'
        else:
            docstring = f'    """{title}"""\n'

        self.class_names.append(name)
        self.classes.append(
            f"class {name}(BaseModel):\n"
            f"{docstring}\n"
            f'    model_config = ConfigDict(extra="{extra}")\n\n'
            f"{body}\n" + "".join(validators)
        )
        return name

    def run(self) -> str:
        self.root_class = _pascal(self.contract_id)
        self._emit_object(self.root_class, self.schema, root=True)
        body = "\n\n".join(self.classes)

        # Emit only the imports the output actually uses. Generated code is
        # committed and linted like any other, so an unused import is a CI
        # failure rather than cosmetic -- and conditioning on the body is more
        # honest than a fixed block that happens to fit the widest schema.
        typing_names = [n for n in ("Any", "Literal") if n in body]
        pydantic_names = [
            n
            for n in (
                "BaseModel",
                "ConfigDict",
                "Field",
                "field_validator",
                "model_validator",
            )
            if n in body
        ]
        scalar_names = [n for n in ("Boolean", "Integer", "Number") if n in body]

        imports = (
            [f"from typing import {', '.join(typing_names)}"] if typing_names else []
        )
        imports.append(f"from pydantic import {', '.join(pydantic_names)}")
        if scalar_names:
            imports.append(
                "from cyberwave_contracts.models._scalars import "
                f"{', '.join(scalar_names)}"
            )

        self.source = (
            f"# !! GENERATED from {self.contract_id}.schema.json -- do not edit.\n\n"
            "from __future__ import annotations\n\n"
            + "\n\n".join(imports)
            + "\n\n\n"
            + body
            + "\n"
        )
        return self.source


def generate(schema: dict[str, Any]) -> str:
    return Generator(schema).run()


def _module_stem(contract_id: str) -> str:
    """The module a contract's model lives in. One rule, used by every writer."""
    return contract_id.replace(".", "_")


def _run_all() -> dict[str, Generator]:
    """Run the generator over every shipped schema, keyed by contract id."""
    generators = {}
    for path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        generator = Generator(json.loads(path.read_text(encoding="utf-8")))
        generator.run()
        generators[generator.contract_id] = generator
    return generators


#: Prose for the generated package __init__, quotes added at render time. Held
#: here rather than hand-edited in the output, which is the whole reason that file
#: used to be written by hand.
_INIT_DOCSTRING = """Pydantic models generated from the contract schemas in ``cyberwave_contracts/schemas``.

Generated, not written -- this file included: run ``make -C cyberwave-contracts
models``. A model here cannot drift from the schema it came from, which is the
whole reason it exists -- the backend's ``test_contract_conformance.py`` measures
the hand-written checks against these and fails on any undeclared disagreement.

Import the model, never re-implement the rule it carries.
"""


def render_init(generators: dict[str, Generator]) -> str:
    """The ``models/__init__.py`` source for *generators*.

    Every name in it is something the generator already computed, so the
    re-export list, the contract-id mapping and ``__all__`` cannot fall behind
    the modules beside them.
    """
    ordered = sorted(generators.items())
    quote = '"""'
    imports = "\n".join(
        f"from cyberwave_contracts.models.{_module_stem(contract_id)} import ("
        + "".join(f"\n    {name}," for name in sorted(generator.class_names))
        + "\n)"
        for contract_id, generator in ordered
    )
    mapping = "".join(
        f"\n    {json.dumps(contract_id)}: {generator.root_class},"
        for contract_id, generator in ordered
    )
    exported = sorted(
        {name for generator in generators.values() for name in generator.class_names}
        | {"MODELS_BY_CONTRACT_ID"}
    )
    all_block = "".join(f"\n    {json.dumps(name)}," for name in exported)
    return (
        f"{quote}{_INIT_DOCSTRING}{quote}\n\n"
        f"{imports}\n\n"
        "#: Contract id -> its root model. Keyed so a caller can walk the manifest\n"
        "#: and find the model for each indexed contract without a second mapping\n"
        "#: to keep in step with it.\n"
        f"MODELS_BY_CONTRACT_ID = {{{mapping}\n}}\n\n"
        f"__all__ = [{all_block}\n]\n"
    )


def generate_all() -> dict[str, str]:
    """Return {filename: source} for every file ``make models`` writes."""
    generators = _run_all()
    sources = {
        f"{_module_stem(contract_id)}.py": generator.source
        for contract_id, generator in generators.items()
    }
    sources["__init__.py"] = render_init(generators)
    return sources


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(generate(json.loads(Path(sys.argv[1]).read_text())))
    else:
        out = Path(__file__).resolve().parent / "models"
        out.mkdir(exist_ok=True)
        for filename, source in sorted(generate_all().items()):
            (out / filename).write_text(source)
            print(f"  models/{filename}")
