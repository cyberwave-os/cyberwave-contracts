import pytest
from pydantic import ValidationError

from cyberwave_contracts import (
    source_types_where,
    MODELS_BY_CONTRACT_ID,
    SOURCE_TYPE_AXES_PATH,
    SOURCE_TYPE_VALUES,
    SourceTypeEnvelopeV1,
    load_contracts,
    load_source_type_axes,
)


def test_source_type_axes_ship_inside_the_package() -> None:
    assert SOURCE_TYPE_AXES_PATH.is_file()
    document = load_source_type_axes()
    assert document["version"] == 1
    assert set(document["values"]) == {
        "edge",
        "edge_leader",
        "edge_follower",
        "sim",
        "tele",
        "sim_tele",
        "edit",
    }


def test_package_declares_its_inline_types() -> None:
    assert SOURCE_TYPE_AXES_PATH.with_name("py.typed").is_file()


def test_source_type_axes_are_returned_as_a_fresh_copy() -> None:
    document = load_source_type_axes()
    document["values"].clear()
    assert load_source_type_axes()["values"]


def test_source_type_vocabulary_matches_the_axes_contract() -> None:
    assert set(SOURCE_TYPE_VALUES) == set(load_source_type_axes()["values"])


def test_v1_envelope_model_matches_the_packaged_contract() -> None:
    contract = next(
        contract
        for contract in load_contracts()
        if contract.id == "source_type.envelope.v1"
    )
    declared = contract.schema_json()
    generated = SourceTypeEnvelopeV1.model_json_schema()

    assert declared["required"] == ["source_type"]
    assert declared["additionalProperties"] is True
    assert generated["required"] == declared["required"]
    assert generated["additionalProperties"] is declared["additionalProperties"]
    assert set(declared["properties"]["source_type"]["enum"]) == set(
        load_source_type_axes()["values"]
    )


def test_v1_envelope_is_generated_and_registered() -> None:
    assert SourceTypeEnvelopeV1.__module__ == (
        "cyberwave_contracts.models.source_type_envelope_v1"
    )
    assert MODELS_BY_CONTRACT_ID["source_type.envelope.v1"] is SourceTypeEnvelopeV1


@pytest.mark.parametrize("source_type", SOURCE_TYPE_VALUES)
def test_v1_envelope_accepts_every_declared_source_type(source_type: str) -> None:
    envelope = SourceTypeEnvelopeV1.model_validate(
        {"source_type": source_type, "domain_field": 42}
    )

    assert envelope.source_type == source_type
    assert envelope.model_dump()["domain_field"] == 42


def test_v1_envelope_requires_source_type() -> None:
    with pytest.raises(ValidationError, match="source_type"):
        SourceTypeEnvelopeV1.model_validate({"domain_field": 42})


def test_v1_envelope_rejects_unknown_source_type() -> None:
    with pytest.raises(ValidationError, match="source_type"):
        SourceTypeEnvelopeV1.model_validate({"source_type": "unknown"})


def test_source_types_where_separates_absent_role_from_any_role() -> None:
    assert source_types_where(substrate="hardware") == {
        "edge",
        "edge_leader",
        "edge_follower",
        "tele",
    }
    assert source_types_where(substrate="hardware", role=None) == {"edge", "tele"}
    assert source_types_where(
        substrate="hardware", direction="state", role_not="leader"
    ) == {"edge", "edge_follower"}
