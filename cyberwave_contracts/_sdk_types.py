"""Write the Python SDK's two controller types from their contract schemas.

``PolicyRefPayload`` and ``ControlRuntimeTargetPayload`` were hand-written
``TypedDict``s that copied ``common.controller_ref.v1`` and
``common.runtime_target.v1``. They stay plain dictionaries for SDK users, but the
definition is now the schema: this module renders them and writes
``cyberwave/_contract_types.py`` in the SDK.

Regenerate (``make -C cyberwave-contracts models`` does this)::

    python3 -m cyberwave_contracts._sdk_types

Only the constructs these two schemas use are supported: required and optional
properties, strings, booleans, closed string enums, nullable strings and an open
object. Anything else raises, as the model generator does.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cyberwave_contracts.manifest import SCHEMAS_DIR

#: contract id -> the name the SDK has always exported it under.
SDK_TYPES: dict[str, str] = {
    "common.controller_ref.v1": "PolicyRefPayload",
    "common.runtime_target.v1": "ControlRuntimeTargetPayload",
}

#: Where the SDK keeps the output, relative to the monorepo root. The public
#: contracts repository has no SDK beside it, so the writer skips when absent.
SDK_TYPES_RELATIVE = "cyberwave-sdks/cyberwave-python/cyberwave/_contract_types.py"

_MONOREPO_ROOT = Path(__file__).resolve().parents[2]


class UnsupportedSdkType(Exception):
    """A schema used something this writer does not model. Never guess."""


def _annotation(prop: str, spec: dict[str, Any]) -> str:
    if "enum" in spec:
        values = ", ".join(json.dumps(v) for v in spec["enum"])
        return f"Literal[{values}]"
    json_type = spec.get("type")
    if isinstance(json_type, list):
        members = [t for t in json_type if t != "null"]
        if members != ["string"] or "null" not in json_type:
            raise UnsupportedSdkType(f"{prop}: unsupported union {json_type!r}")
        return "str | None"
    if json_type == "string":
        return "str"
    if json_type == "boolean":
        return "bool"
    if json_type == "object" and not spec.get("properties"):
        return "Dict[str, Any]"
    raise UnsupportedSdkType(f"{prop}: unsupported type {json_type!r}")


def _render_class(name: str, schema: dict[str, Any]) -> str:
    required = set(schema.get("required", []))
    properties: dict[str, Any] = schema["properties"]
    fields = []
    for prop in sorted(properties, key=lambda p: (p not in required, p)):
        wrapper = "Required" if prop in required else "NotRequired"
        fields.append(f"    {prop}: {wrapper}[{_annotation(prop, properties[prop])}]")
    description = schema.get("description", "")
    return (
        f"class {name}(TypedDict, total=False):\n"
        f'    """{schema["title"]}\n\n    {description}\n    """\n\n'
        + "\n".join(fields)
        + "\n"
    )


def render() -> str:
    classes = []
    for contract_id, name in SDK_TYPES.items():
        path = SCHEMAS_DIR / f"{contract_id}.schema.json"
        schema = json.loads(path.read_text(encoding="utf-8"))
        classes.append((contract_id, _render_class(name, schema)))
    body = "\n\n".join(source for _, source in classes)
    typing_names = [n for n in ("Any", "Dict", "Literal") if n in body]
    sources = ", ".join(f"{cid}.schema.json" for cid, _ in classes)
    return (
        f"# !! GENERATED from {sources} -- do not edit.\n"
        "# Run `make -C cyberwave-contracts models` in the monorepo to regenerate.\n\n"
        "from __future__ import annotations\n\n"
        f"from typing import {', '.join(typing_names)}\n\n"
        "from typing_extensions import NotRequired, Required, TypedDict\n\n\n" + body
    )


def main() -> None:
    target = _MONOREPO_ROOT / SDK_TYPES_RELATIVE
    if not target.parent.is_dir():
        return
    target.write_text(render(), encoding="utf-8")


if __name__ == "__main__":
    main()
