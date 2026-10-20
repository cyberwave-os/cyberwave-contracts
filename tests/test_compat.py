"""The compatibility check: what a schema change may and may not do within an id."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from cyberwave_contracts._compat import check, compare_with, incompatibilities

_BASE: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["mode"],
    "properties": {
        "mode": {"enum": ["a", "b"]},
        "speed": {"type": "number", "minimum": 0, "maximum": 10},
        "name": {"type": "string", "maxLength": 8},
        "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "pose": {"$ref": "#/$defs/pose"},
    },
    "$defs": {"pose": {"type": "object", "properties": {"x": {"type": "number"}}}},
}


def _edit(**changes: Any) -> dict[str, Any]:
    schema = json.loads(json.dumps(_BASE))
    for dotted, value in changes.items():
        *parents, leaf = dotted.split("__")
        target = schema
        for part in parents:
            target = target[part]
        if value is _DELETE:
            del target[leaf]
        else:
            target[leaf] = value
    return schema


_DELETE = object()


def test_an_unchanged_schema_is_compatible() -> None:
    assert check(_BASE, _BASE, full=True) == []


@pytest.mark.parametrize(
    "changes",
    [
        # Additive and optional: a new reader still reads every stored document.
        {"properties__note": {"type": "string"}},
        {"properties__mode__enum": ["a", "b", "c"]},
        {"properties__speed__maximum": 20},
        {"properties__name__maxLength": 16},
        {"properties__speed__type": ["number", "null"]},
        {"properties__tags__maxItems": 8},
    ],
)
def test_backward_compatible_changes_pass_for_a_section(changes: dict) -> None:
    assert check(_BASE, _edit(**changes), full=False) == []


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"properties__name": _DELETE}, "no longer allowed"),
        ({"required": ["mode", "speed"]}, "now required"),
        ({"properties__mode__enum": ["a"]}, "no longer accepts ['b']"),
        ({"properties__speed__maximum": 5}, "maximum tightened"),
        ({"properties__speed__minimum": 1}, "minimum tightened"),
        ({"properties__name__maxLength": 4}, "maxLength tightened"),
        ({"properties__name__type": "integer"}, "no longer accepts ['string']"),
        ({"properties__name__pattern": "^[a-z]+$"}, "pattern changed"),
        ({"properties__tags__items": {"type": "integer"}}, "no longer accepts"),
        ({"$defs__pose__properties__x__type": "string"}, "$.pose.x"),
        ({"properties__tags__maxItems": 2}, "maxItems tightened"),
    ],
)
def test_breaking_changes_are_reported(changes: dict, fragment: str) -> None:
    problems = check(_BASE, _edit(**changes), full=False)
    assert any(fragment in p for p in problems), problems


def test_a_payload_also_needs_forward_compatibility() -> None:
    """Adding an enum value is safe for stored data, not for an old reader."""
    widened = _edit(properties__mode__enum=["a", "b", "c"])
    assert check(_BASE, widened, full=False) == []
    assert any("forward" in p for p in check(_BASE, widened, full=True))


def test_closing_an_open_object_is_a_break() -> None:
    open_schema = _edit(additionalProperties=True)
    problems = check(open_schema, _BASE, full=False)
    assert any("closed to properties" in p for p in problems), problems


def test_an_integer_is_a_number() -> None:
    assert incompatibilities({"type": "number"}, {"type": "integer"}) == []
    assert incompatibilities({"type": "integer"}, {"type": "number"})


def test_recursive_definitions_terminate() -> None:
    schema = {
        "$ref": "#/$defs/node",
        "$defs": {
            "node": {
                "type": "object",
                "properties": {"child": {"$ref": "#/$defs/node"}},
            }
        },
    }
    assert incompatibilities(schema, schema) == []


# --- against git ------------------------------------------------------------

_SECTION = "cyberwave-contracts/cyberwave_contracts/sections/demo.v1.schema.json"
_PAYLOAD = "cyberwave-contracts/cyberwave_contracts/schemas/demo.v1.schema.json"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(tmp_path, "init", "-q", "-b", "base")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    for rel in (_SECTION, _PAYLOAD):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_BASE))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_a_breaking_edit_in_the_working_tree_is_reported(repo: Path) -> None:
    (repo / _SECTION).write_text(json.dumps(_edit(required=["mode", "speed"])))
    report = compare_with("base", repo)
    assert list(report) == [_SECTION]


def test_a_removed_contract_file_is_reported(repo: Path) -> None:
    (repo / _PAYLOAD).unlink()
    report = compare_with("base", repo)
    assert _PAYLOAD in report
    assert "removed" in report[_PAYLOAD][0]


def test_a_compatible_tree_reports_nothing(repo: Path) -> None:
    (repo / _SECTION).write_text(json.dumps(_edit(properties__note={"type": "string"})))
    assert compare_with("base", repo) == {}
