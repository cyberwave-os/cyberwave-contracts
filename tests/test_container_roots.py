"""Sections stored as a list, a map or a bare value, and ``$defs`` that are not objects."""

from __future__ import annotations

import pytest
from cyberwave_contracts._generate import Generator
from cyberwave_contracts.models import (
    EnvironmentSettingsEmbedV1,
    EnvironmentSettingsMissionsV1,
    EnvironmentSettingsSimulatorV1,
    EnvironmentSettingsTwinMotionV1,
)
from pydantic import ValidationError


def _source(schema: dict) -> str:
    return Generator(
        {"$id": "https://schemas.cyberwave.com/x.section.v1.schema.json", **schema}
    ).run()


def test_a_list_root_is_a_root_model_of_its_item() -> None:
    source = _source(
        {"type": "array", "items": {"type": "string"}, "maxItems": 3, "title": "t"}
    )
    assert "RootModel[Annotated[list[str], Field(max_length=3)]]" in source


def test_a_map_root_is_a_root_model_of_its_values() -> None:
    source = _source({"type": "object", "additionalProperties": {"type": "number"}})
    assert "RootModel[dict[str, Number]]" in source


def test_an_array_def_is_the_list_it_describes_not_an_open_class() -> None:
    schema = {
        "type": "object",
        "required": ["at"],
        "properties": {"at": {"$ref": "#/$defs/vec3"}},
        "$defs": {
            "vec3": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
            }
        },
    }
    source = _source(schema)
    assert "class Vec3" not in source
    assert "list[Number]" in source


def test_the_embed_camera_rejects_what_is_not_a_triple() -> None:
    camera = {"position": [1, 2, 3], "target": [0, 0, 0]}
    EnvironmentSettingsEmbedV1.model_validate(
        {"enabled": False, "mode": "3d", "camera": camera}
    )
    for bad in ({**camera, "position": [1, 2]}, {**camera, "target": "origin"}):
        with pytest.raises(ValidationError):
            EnvironmentSettingsEmbedV1.model_validate(
                {"enabled": False, "mode": "3d", "camera": bad}
            )


def test_a_bare_value_section_validates_through_its_vocabulary() -> None:
    assert EnvironmentSettingsSimulatorV1.model_validate("isaac").root.root == "isaac"
    with pytest.raises(ValidationError):
        EnvironmentSettingsSimulatorV1.model_validate("mjwarp")


def test_list_and_map_sections_validate_their_elements() -> None:
    EnvironmentSettingsMissionsV1.model_validate(
        [{"id": "m", "name": "n", "twinUuid": "t"}]
    )
    with pytest.raises(ValidationError):
        EnvironmentSettingsMissionsV1.model_validate([{"name": "no id"}])
    with pytest.raises(ValidationError):
        EnvironmentSettingsTwinMotionV1.model_validate({"t": {"keyframes": "x"}})


# --- type unions --------------------------------------------------------------


def _union_source(prop: dict) -> str:
    return _source(
        {
            "type": "object",
            "required": [],
            "properties": {"colour": prop},
        }
    )


def test_a_type_union_is_one_annotation_per_member() -> None:
    source = _union_source({"type": ["string", "array"], "items": {"type": "number"}})
    assert "str | list[Number]" in source


def test_a_nullable_type_union_gains_none() -> None:
    source = _union_source({"type": ["string", "object", "null"]})
    assert "str | dict[str, Any] | None" in source


def test_a_type_union_refuses_a_bound_it_cannot_place() -> None:
    from cyberwave_contracts._generate import UnsupportedConstruct

    with pytest.raises(UnsupportedConstruct, match="cannot carry"):
        _union_source({"type": ["string", "number"], "minimum": 0})
