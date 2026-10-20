"""Refuse a schema change that breaks the data the previous version described.

A contract id is a promise: data valid under ``foo.v1`` today stays valid under
``foo.v1`` tomorrow. A change that cannot keep it gets a new id (``foo.v2``) and a
migration, never an edit in place. This checks the promise mechanically, by
comparing each schema with its version on the base branch.

The question asked is always *can a reader built from one schema accept every
document a writer built from the other produces* -- :func:`incompatibilities`.
Which direction matters depends on what the schema describes:

* **Stored sections** (``sections/``) must be **backward** compatible: the new
  reader reads every row the old one wrote. Checking each change against its base
  makes this transitive over the whole history, because each step only widens the
  set of accepted documents.
* **Payloads and overlays** (``schemas/``) travel between processes that upgrade
  at different times, so they must be **fully** compatible: backward, and also
  forward -- an old reader accepts what the new writer sends.

Conservative by design: where a change cannot be proved safe (a new ``pattern``,
a reworded ``oneOf``) it is reported. A false alarm costs a reviewer a look; a
missed break costs stored data.

Run from a git checkout against a base revision::

    python -m cyberwave_contracts._compat --base <git-rev>
"""

from __future__ import annotations

import argparse
import json
import operator
import subprocess
import sys
from pathlib import Path
from typing import Any

from cyberwave_contracts.manifest import SCHEMAS_RELATIVE, SECTIONS_RELATIVE

#: Bounds a reader may only relax, each with the test for "the writer was looser".
_BOUNDS = {
    **dict.fromkeys(
        ("minimum", "exclusiveMinimum", "minLength", "minItems"), operator.lt
    ),
    **dict.fromkeys(
        ("maximum", "exclusiveMaximum", "maxLength", "maxItems"), operator.gt
    ),
}

#: Keywords compared by exact equality, because a change to them cannot be shown
#: to keep every document valid without solving the language they describe.
_OPAQUE = ("pattern", "oneOf", "anyOf", "allOf", "not", "format", "multipleOf")


def _types(spec: dict[str, Any]) -> set[str] | None:
    """The JSON types *spec* admits, or None when it does not constrain the type."""
    json_type = spec.get("type")
    if json_type is None:
        return None
    return set(json_type) if isinstance(json_type, list) else {json_type}


def _resolve(
    spec: dict[str, Any], document: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    """Follow a local ``$ref``; return the target and its name (for cycle checks)."""
    ref = spec.get("$ref")
    if not ref:
        return spec, None
    if not ref.startswith("#/$defs/"):
        raise ValueError(f"only #/$defs/ refs are supported, got {ref!r}")
    name = ref.removeprefix("#/$defs/")
    target = {**document.get("$defs", {}).get(name, {})}
    # Sibling keywords of a $ref (readOnly, description) apply alongside it.
    target.update({k: v for k, v in spec.items() if k != "$ref"})
    return target, name


def incompatibilities(
    reader: dict[str, Any],
    writer: dict[str, Any],
    *,
    reader_doc: dict[str, Any] | None = None,
    writer_doc: dict[str, Any] | None = None,
    path: str = "$",
    _seen: frozenset[tuple[str | None, str | None]] = frozenset(),
) -> list[str]:
    """Why a document valid under *writer* might be rejected by *reader*.

    Empty when every document *writer* admits is also admitted by *reader*, as far
    as this can tell. ``reader_doc``/``writer_doc`` are the whole schemas the two
    specs come from, used to resolve ``$ref``.
    """
    reader_doc = reader if reader_doc is None else reader_doc
    writer_doc = writer if writer_doc is None else writer_doc
    reader, reader_ref = _resolve(reader, reader_doc)
    writer, writer_ref = _resolve(writer, writer_doc)
    if reader_ref or writer_ref:
        key = (reader_ref, writer_ref)
        if key in _seen:
            return []  # a recursive $def already being compared up the stack
        _seen = _seen | {key}

    problems: list[str] = []

    def recurse(r: dict[str, Any], w: dict[str, Any], where: str) -> None:
        problems.extend(
            incompatibilities(
                r,
                w,
                reader_doc=reader_doc,
                writer_doc=writer_doc,
                path=where,
                _seen=_seen,
            )
        )

    # -- types, constants, enums --------------------------------------------
    reader_types, writer_types = _types(reader), _types(writer)
    if reader_types is not None:
        if writer_types is None and "const" not in writer and "enum" not in writer:
            problems.append(f"{path}: now restricted to type {sorted(reader_types)}")
        elif writer_types is not None:
            extra = writer_types - reader_types
            if "number" in reader_types:
                extra.discard("integer")  # every integer is a number
            if extra:
                problems.append(
                    f"{path}: type {sorted(writer_types)} -> {sorted(reader_types)} "
                    f"no longer accepts {sorted(extra)}"
                )

    if "const" in reader and writer.get("const", object()) != reader["const"]:
        if not ("enum" in writer and writer["enum"] == [reader["const"]]):
            problems.append(f"{path}: const is now {reader['const']!r}")
    if "enum" in reader:
        if "const" in writer:
            allowed = [writer["const"]]
        elif "enum" in writer:
            allowed = writer["enum"]
        else:
            allowed = None
        if allowed is None:
            problems.append(f"{path}: now restricted to {reader['enum']!r}")
        elif dropped := [v for v in allowed if v not in reader["enum"]]:
            problems.append(f"{path}: no longer accepts {dropped!r}")

    # -- bounds ---------------------------------------------------------------
    for keyword, looser in _BOUNDS.items():
        if keyword in reader and (
            keyword not in writer or looser(writer[keyword], reader[keyword])
        ):
            problems.append(
                f"{path}: {keyword} tightened to {reader[keyword]!r} "
                f"(was {writer.get(keyword)!r})"
            )

    for keyword in _OPAQUE:
        if keyword in reader and reader.get(keyword) != writer.get(keyword):
            problems.append(
                f"{path}: {keyword} changed and cannot be proved compatible"
            )

    # -- objects --------------------------------------------------------------
    reader_props: dict[str, Any] = reader.get("properties", {})
    writer_props: dict[str, Any] = writer.get("properties", {})
    reader_required = set(reader.get("required", []))
    writer_required = set(writer.get("required", []))

    for name in sorted(reader_required - writer_required):
        problems.append(f"{path}.{name}: now required")

    reader_extra = reader.get("additionalProperties", True)
    writer_extra = writer.get("additionalProperties", True)
    if reader_extra is False:
        for name in sorted(set(writer_props) - set(reader_props)):
            problems.append(f"{path}.{name}: no longer allowed (object is closed)")
        if writer_extra is not False:
            problems.append(f"{path}: closed to properties it used to accept")
    elif isinstance(reader_extra, dict):
        if isinstance(writer_extra, dict):
            recurse(reader_extra, writer_extra, f"{path}.*")
        elif writer_extra is not False:
            problems.append(f"{path}.*: map values are now typed")
        for name in sorted(set(writer_props) - set(reader_props)):
            recurse(reader_extra, writer_props[name], f"{path}.{name}")

    # A property the reader newly declares while the writer was open is not
    # compared: old documents could in principle carry that key with any value,
    # but flagging every added optional field would make every addition a break.
    for name in sorted(set(reader_props) & set(writer_props)):
        recurse(reader_props[name], writer_props[name], f"{path}.{name}")

    for trigger, needs in (reader.get("dependentRequired") or {}).items():
        had = set((writer.get("dependentRequired") or {}).get(trigger, []))
        if missing := sorted(set(needs) - had):
            problems.append(f"{path}: {trigger} now requires {missing}")

    # -- arrays ---------------------------------------------------------------
    if "items" in reader:
        if "items" in writer:
            recurse(reader["items"], writer["items"], f"{path}[]")
        else:
            problems.append(f"{path}[]: items are now typed")

    return problems


def check(old: dict[str, Any], new: dict[str, Any], *, full: bool) -> list[str]:
    """Breaks between two versions of one schema. *full* adds the forward check."""
    problems = [f"backward: {p}" for p in incompatibilities(new, old)]
    if full:
        problems += [f"forward: {p}" for p in incompatibilities(old, new)]
    return problems


# -- command line ---------------------------------------------------------------

#: The trees checked, and whether each needs full compatibility.
_TREES = {SCHEMAS_RELATIVE: True, SECTIONS_RELATIVE: False}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def compare_with(base: str, root: Path) -> dict[str, list[str]]:
    """Problems per schema path, comparing the working tree at *root* to *base*."""
    report: dict[str, list[str]] = {}
    for tree, full in _TREES.items():
        listed = _git("ls-tree", "-r", "--name-only", base, "--", tree)
        for path in listed.split():
            if not path.endswith(".schema.json"):
                continue
            current = root / path
            if not current.is_file():
                report[path] = [
                    "removed: a contract id is permanent; retire it in the manifest "
                    "and keep the file, or move readers to a new id first"
                ]
                continue
            old = json.loads(_git("show", f"{base}:{path}"))
            new = json.loads(current.read_text(encoding="utf-8"))
            if problems := check(old, new, full=full):
                report[path] = problems
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", required=True, help="git revision to compare with")
    args = parser.parse_args(argv)
    root = Path(_git("rev-parse", "--show-toplevel").strip())
    report = compare_with(args.base, root)
    if not report:
        print(f"✅ every contract schema is compatible with {args.base}")
        return 0
    for path, problems in sorted(report.items()):
        print(f"❌ {path}")
        for problem in problems:
            print(f"   - {problem}")
    print(
        "\nA breaking change needs a new contract id (…v2) and a data migration. "
        "If this break is intended and approved, label the PR "
        "`contract-break-approved`."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
