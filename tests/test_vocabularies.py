"""The generator and manifest rules that shared vocabularies rely on.

A vocabulary is a value other contracts embed. Unlike a payload it is never sent on
its own, so it has no identity field; unlike a ``$defs`` entry it is a contract with
a version of its own, which another schema references as ``<id>.schema.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from cyberwave_contracts import MODELS_BY_CONTRACT_ID
from cyberwave_contracts._generate import (
    Generator,
    UnsupportedConstruct,
    _nullable_ref,
    generate_all,
)
from cyberwave_contracts import manifest
from cyberwave_contracts.manifest import bundle_schema, load_contracts
from pydantic import ValidationError

_VOCABULARIES = {c.id: c for c in load_contracts() if c.kind == "vocabulary"}


def _schema(**properties: object) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://schemas.cyberwave.com/example.holder.v1.schema.json",
        "type": "object",
        "additionalProperties": True,
        "properties": properties,
    }


def test_a_vocabulary_has_no_identity_field() -> None:
    assert _VOCABULARIES
    assert all(c.id_field is None for c in _VOCABULARIES.values())


# --- a root enum -----------------------------------------------------------


def test_an_enum_vocabulary_is_a_model_that_validates_one_value() -> None:
    model = MODELS_BY_CONTRACT_ID["common.simulation_backend.v1"]

    assert model.model_validate("playground").root == "playground"
    with pytest.raises(ValidationError):
        model.model_validate("gazebo")


@pytest.mark.parametrize(
    ("values", "message"),
    [(["a", 1], "non-empty list of strings"), (["a", "a"], "twice")],
)
def test_an_enum_vocabulary_refuses_a_malformed_value_list(
    values: list[object], message: str
) -> None:
    schema = {
        "$id": "https://schemas.cyberwave.com/example.mode.v1.schema.json",
        "type": "string",
        "enum": values,
    }
    with pytest.raises(UnsupportedConstruct, match=message):
        Generator(schema).run()


# --- a reference to another contract ---------------------------------------


def test_a_reference_is_the_shared_model_not_a_copy() -> None:
    pose = MODELS_BY_CONTRACT_ID["common.pose.v1"]
    quaternion = MODELS_BY_CONTRACT_ID["common.quaternion.v1"]

    assert pose.model_fields["orientation"].annotation is quaternion
    parsed = pose.model_validate(
        {
            "position": {"x": 0, "y": 0, "z": 1},
            "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
        }
    )
    assert isinstance(parsed.orientation, quaternion)
    with pytest.raises(ValidationError):
        pose.model_validate(
            {"position": {"x": 0, "y": 0, "z": 1}, "orientation": {"x": 0}}
        )


def test_the_referencing_module_imports_the_vocabulary() -> None:
    source = generate_all()["common_pose_v1.py"]

    assert (
        "from cyberwave_contracts.models.common_quaternion_v1 import CommonQuaternionV1"
        in source
    )


def test_only_a_vocabulary_can_be_referenced() -> None:
    schema = _schema(command={"$ref": "locomotion.velocity_command.v1.schema.json"})
    with pytest.raises(UnsupportedConstruct, match="does not name a vocabulary"):
        Generator(schema).run()


def test_a_contract_cannot_reference_itself() -> None:
    schema = _schema(me={"$ref": "example.holder.v1.schema.json"})
    with pytest.raises(UnsupportedConstruct, match="itself"):
        Generator(schema).run()


def test_a_fragment_reference_to_another_file_is_still_refused() -> None:
    schema = _schema(x={"$ref": "common.pose.v1.schema.json#/properties/position"})
    with pytest.raises(UnsupportedConstruct, match="only #/\\$defs/ refs"):
        Generator(schema).run()


def test_a_reference_or_null_is_an_optional_reference() -> None:
    ref = {"$ref": "common.quaternion.v1.schema.json"}
    schema = _schema(rotation={"anyOf": [ref, {"type": "null"}]})
    source = Generator(schema).run()

    assert "rotation: CommonQuaternionV1 | None = None" in source
    assert _nullable_ref({"anyOf": [ref, {"type": "string"}]}) is None
    assert _nullable_ref({"anyOf": [ref]}) is None


# --- bundling --------------------------------------------------------------


def test_a_bundled_schema_needs_no_resolver() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    pose = _VOCABULARIES["common.pose.v1"]

    bundled = pose.bundled_schema()

    assert "common.quaternion.v1.schema.json" not in json.dumps(bundled)
    validator = jsonschema.Draft202012Validator(bundled)
    good = {
        "position": {"x": 0, "y": 0, "z": 0},
        "orientation": {"x": 0, "y": 0, "z": 0, "w": 1},
    }
    assert validator.is_valid(good)
    assert not validator.is_valid({**good, "orientation": {"x": 0}})


def test_bundling_leaves_the_source_schema_untouched() -> None:
    pose = _VOCABULARIES["common.pose.v1"]
    before = json.dumps(pose.schema_json(), sort_keys=True)

    bundle_schema(pose.schema_json())

    assert json.dumps(pose.schema_json(), sort_keys=True) == before
    assert (
        pose.schema_json()["properties"]["orientation"]["$ref"]
        == "common.quaternion.v1.schema.json"
    )


def test_no_vocabulary_has_its_own_defs() -> None:
    # bundle_schema inlines a vocabulary under `$defs`, which would strand its local refs.
    for contract in load_contracts():
        if contract.kind == "vocabulary":
            assert "$defs" not in contract.schema_json(), contract.id


def test_bundling_refuses_a_vocabulary_with_its_own_defs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "x.schema.json").write_text(
        json.dumps({"type": "object", "$defs": {"a": {"type": "string"}}})
    )
    monkeypatch.setattr(manifest, "SCHEMAS_DIR", tmp_path)
    with pytest.raises(ValueError, match="cannot have \\$defs"):
        bundle_schema({"properties": {"x": {"$ref": "x.schema.json"}}})


def test_a_schema_with_no_references_bundles_to_itself() -> None:
    source = _VOCABULARIES["common.controller_ref.v1"].schema_json()

    assert bundle_schema(source) == source


# --- common.contract_id.v1 --------------------------------------------------


def test_the_contract_id_schema_is_generated_from_the_manifest() -> None:
    from cyberwave_contracts import _contract_ids
    from cyberwave_contracts.manifest import SCHEMAS_DIR

    on_disk = (SCHEMAS_DIR / f"{_contract_ids.CONTRACT_ID}.schema.json").read_text(
        encoding="utf-8"
    )
    assert on_disk == _contract_ids.render(), (
        "common.contract_id.v1 is stale: run `make -C cyberwave-contracts models`"
    )


def test_a_registered_id_leaves_the_unregistered_list() -> None:
    from cyberwave_contracts._contract_ids import (
        UNREGISTERED_CONTRACT_IDS,
        registered_contract_ids,
    )

    both = set(registered_contract_ids()) & set(UNREGISTERED_CONTRACT_IDS)
    assert not both, f"{sorted(both)} now have a contract; remove them from the list"
    assert list(UNREGISTERED_CONTRACT_IDS) == sorted(UNREGISTERED_CONTRACT_IDS)


def test_the_contract_id_model_rejects_a_typo() -> None:
    model = MODELS_BY_CONTRACT_ID["common.contract_id.v1"]

    with pytest.raises(ValidationError):
        model.model_validate("locomotion.velocity_comand.v1")
