"""The ``simulation.*`` contracts: fixtures against the generated models, the
index entries, and the generator features they rely on (``pattern``, typed
maps, unreferenced ``$defs``)."""

from __future__ import annotations

import json
import sys
import types
from collections import Counter
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from cyberwave_contracts import _generate
from cyberwave_contracts.manifest import load_contracts
from cyberwave_contracts.models import MODELS_BY_CONTRACT_ID
from cyberwave_contracts.models import simulation_replay_trace_v1 as trace_models

FIXTURES = Path(__file__).parent / "fixtures" / "simulation"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]

SIMULATION_CONTRACTS = {
    "feature_profile": "simulation.feature_profile.v1",
    "scene_bundle_manifest": "simulation.scene_bundle_manifest.v1",
    "runtime_audit": "simulation.runtime_audit.v1",
    "compatibility_attestation": "simulation.compatibility_attestation.v1",
    "replay_trace_header": "simulation.replay_trace.v1",
    "hardware_qualification": "simulation.hardware_qualification.v1",
}


def _fixtures(kind: str) -> list[Path]:
    return sorted(
        p
        for p in FIXTURES.glob(f"*.{kind}*.json")
        if p.name.split(".")[0] in SIMULATION_CONTRACTS
    )


def _model(path: Path) -> type[BaseModel]:
    return MODELS_BY_CONTRACT_ID[SIMULATION_CONTRACTS[path.name.split(".")[0]]]


@pytest.mark.parametrize(
    "schema",
    sorted((PACKAGE_ROOT / "cyberwave_contracts" / "schemas").glob("*.schema.json")),
    ids=lambda p: p.name,
)
def test_every_shipped_schema_is_a_valid_draft_2020_12_schema(schema: Path) -> None:
    """The generator tolerates a malformed schema; any jsonschema consumer does not.

    A duplicate entry in ``required`` once generated a working model while every
    ``Draft202012Validator`` built on the schema raised ``SchemaError``.
    """
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(
        json.loads(schema.read_text(encoding="utf-8"))
    )


def test_every_simulation_contract_has_valid_and_invalid_fixtures() -> None:
    for stem in SIMULATION_CONTRACTS:
        assert (FIXTURES / f"{stem}.valid.json").exists(), stem
        assert list(FIXTURES.glob(f"{stem}.invalid.*.json")), stem


@pytest.mark.parametrize("path", _fixtures("valid"), ids=lambda p: p.name)
def test_valid_fixture(path: Path) -> None:
    _model(path).model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", _fixtures("invalid"), ids=lambda p: p.name)
def test_invalid_fixture(path: Path) -> None:
    with pytest.raises(ValidationError):
        _model(path).model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_contracts_are_indexed_with_existing_python_source() -> None:
    by_id = {c.id: c for c in load_contracts()}
    for contract_id in SIMULATION_CONTRACTS.values():
        contract = by_id[contract_id]
        assert contract.python_source, contract_id
        assert (PACKAGE_ROOT.parent / contract.python_source).exists(), (
            contract.python_source
        )


def test_trace_record_models_accept_the_fixture_trace() -> None:
    models = {
        "command": trace_models.ReplayTraceCommandRecord,
        "state": trace_models.ReplayTraceStateRecord,
        "lifecycle": trace_models.ReplayTraceLifecycleRecord,
        "readiness": trace_models.ReplayTraceReadinessRecord,
        "sensor": trace_models.ReplayTraceSensorRecord,
        "camera_frame": trace_models.ReplayTraceCameraFrameRecord,
    }
    lines = (
        (FIXTURES / "traces" / "baseline.local.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    MODELS_BY_CONTRACT_ID["simulation.replay_trace.v1"].model_validate(
        json.loads(lines[0])
    )
    seen = set()
    for line in lines[1:]:
        record = json.loads(line)
        models[record["kind"]].model_validate(record)
        seen.add(record["kind"])
    assert {"command", "state", "lifecycle", "readiness", "camera_frame"} <= seen


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("/abs/scene.usda", False),
        ("../scene.usda", False),
        ("a/./b", False),
        ("scene.usda\n", False),
        ("assets/robot.usda", True),
    ],
)
def test_bundle_file_path_pattern_matches_the_helper(path: str, value: bool) -> None:
    from cyberwave_contracts.simulation import is_confined_relative_path

    model = MODELS_BY_CONTRACT_ID["simulation.scene_bundle_manifest.v1"]
    manifest = json.loads(
        (FIXTURES / "scene_bundle_manifest.valid.json").read_text(encoding="utf-8")
    )
    manifest["files"][0]["path"] = path
    try:
        model.model_validate(manifest)
        accepted = True
    except ValidationError:
        accepted = False
    assert accepted is value is is_confined_relative_path(path)


def test_generated_class_names_are_unique_across_modules() -> None:
    # models/__init__ flattens every module into one namespace.
    names = Counter(
        name for g in _generate._run_all().values() for name in g.class_names
    )
    assert [n for n, c in names.items() if c > 1] == []


# -- generator features ---------------------------------------------------------------


def _schema(properties: dict, defs: dict | None = None) -> dict:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://schemas.cyberwave.com/test.generator_probe.v1.schema.json",
        "title": "Probe",
        "description": "Generator probe.",
        "type": "object",
        "additionalProperties": True,
        "required": ["contract", *properties],
        "properties": {"contract": {"const": "test.generator_probe.v1"}, **properties},
    }
    if defs:
        schema["$defs"] = defs
    return schema


def _build(schema: dict) -> dict:
    # A real module, so the generated `from __future__ import annotations`
    # resolves its names the way the committed models do.
    module = types.ModuleType("generator_probe")
    sys.modules[module.__name__] = module
    try:
        exec(
            compile(_generate.generate(schema), "<generated>", "exec"), module.__dict__
        )  # noqa: S102
    finally:
        del sys.modules[module.__name__]
    return module.__dict__


def test_generator_enforces_pattern() -> None:
    model = _build(
        _schema({"digest": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}})
    )["TestGeneratorProbeV1"]
    model.model_validate(
        {"contract": "test.generator_probe.v1", "digest": "sha256:" + "a" * 64}
    )
    with pytest.raises(ValidationError):
        model.model_validate(
            {"contract": "test.generator_probe.v1", "digest": "md5:abc"}
        )


@pytest.mark.parametrize(
    "spec",
    [
        {"type": "string", "pattern": "^(?=a)a$"},  # lookahead: not portable to JS/ECMA
        {"type": "string", "pattern": "^(a)\\1$"},  # backreference
        {"type": "string", "pattern": "\\Aa\\Z"},
        {"type": "string", "pattern": "^\\d{3}$"},  # Unicode digits in Python
        {"type": "string", "pattern": "^\\w+$"},
        {"type": "string", "pattern": "^\\bab$"},  # word boundary
        {"type": "string", "pattern": "(?i)^a$"},  # inline flag: none in ECMA-262
        {"type": "string", "pattern": "^(?>a)$"},  # atomic group
        {"type": "string", "pattern": "^[[:alpha:]]$"},  # POSIX class: Rust only
        {"enum": ["a"], "pattern": "^a$"},
        {"type": "integer", "pattern": "^1$"},
        {"type": "string", "pattern": "("},
    ],
)
def test_generator_refuses_unportable_or_misplaced_pattern(spec: dict) -> None:
    with pytest.raises(_generate.UnsupportedConstruct):
        _generate.generate(_schema({"value": spec}))


def test_generator_emits_typed_maps_and_unreferenced_defs() -> None:
    namespace = _build(
        _schema(
            {"counts": {"type": "object", "additionalProperties": {"type": "integer"}}},
            defs={
                "probeRecord": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["n"],
                    "properties": {"n": {"type": "integer"}},
                }
            },
        )
    )
    model = namespace["TestGeneratorProbeV1"]
    model.model_validate({"contract": "test.generator_probe.v1", "counts": {"a": 1}})
    with pytest.raises(ValidationError):
        model.model_validate(
            {"contract": "test.generator_probe.v1", "counts": {"a": "x"}}
        )
    assert "ProbeRecord" in namespace


def test_generator_emits_no_class_for_a_non_object_def() -> None:
    # An enum or map $def has no class to emit; one emitted anyway would be an
    # empty extra="allow" model that accepts any object.
    namespace = _build(
        _schema(
            {"n": {"type": "integer"}},
            defs={
                "statusEnum": {"type": "string", "enum": ["ok", "fail"]},
                "countMap": {
                    "type": "object",
                    "additionalProperties": {"type": "integer"},
                },
            },
        )
    )
    assert "StatusEnum" not in namespace and "CountMap" not in namespace
    assert "TestGeneratorProbeV1" in namespace


def test_generator_enforces_constrained_map_values_and_items() -> None:
    # A bound on an element has no field of its own, so it rides on the element
    # type through Annotated rather than being dropped.
    namespace = _build(
        _schema(
            {
                "m": {
                    "type": "object",
                    "additionalProperties": {"type": "integer", "minimum": 0},
                },
                "l": {"type": "array", "items": {"type": "string", "pattern": "^a$"}},
            }
        )
    )
    model = namespace["TestGeneratorProbeV1"]
    model.model_validate(
        {"contract": "test.generator_probe.v1", "m": {"x": 0}, "l": ["a"]}
    )
    for bad in ({"m": {"x": -1}}, {"l": ["b"]}):
        with pytest.raises(ValidationError):
            model.model_validate({"contract": "test.generator_probe.v1", **bad})
