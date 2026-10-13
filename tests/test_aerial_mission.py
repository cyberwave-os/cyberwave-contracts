"""The aerial mission contract: a flight plan's shape, item vocabulary and limits."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from cyberwave_contracts import MODELS_BY_CONTRACT_ID, load_contracts

CONTRACT = "aerial.mission.v1"
MODEL = MODELS_BY_CONTRACT_ID[CONTRACT]
_ENTRY = {contract.id: contract for contract in load_contracts()}[CONTRACT]


def mission(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "contract": CONTRACT,
        "name": "north field",
        "home": {"latitude": 45.56, "longitude": 12.24, "altitude_amsl_m": 10.0},
        "default_altitude_m": 100,
        "items": [
            {"type": "waypoint", "latitude": 45.565, "longitude": 12.245},
            {
                "type": "loiter_time",
                "latitude": 45.57,
                "longitude": 12.24,
                "seconds": 60,
            },
            {
                "type": "loiter_turns",
                "latitude": 45.565,
                "longitude": 12.235,
                "turns": 2,
                "radius_m": 70,
                "direction": "ccw",
            },
            {"type": "loiter_unlimited", "latitude": 45.566, "longitude": 12.236},
        ],
    }
    base.update(overrides)
    return base


def test_the_contract_is_indexed_as_a_self_identifying_payload() -> None:
    assert _ENTRY.kind == "payload"
    assert _ENTRY.id_field == "contract"
    assert _ENTRY.schema_owner == "json_schema"
    schema = _ENTRY.schema_json()
    assert schema["properties"]["contract"] == {"const": CONTRACT}
    assert {"contract", "name", "home", "items"} <= set(schema["required"])


def test_a_mission_validates_and_defaults_its_reference_frame() -> None:
    model = MODEL.model_validate(mission())
    assert model.altitude_reference == "home"
    assert model.night is False
    assert [item.type for item in model.items] == [
        "waypoint",
        "loiter_time",
        "loiter_turns",
        "loiter_unlimited",
    ]
    assert model.items[2].direction == "ccw"


def test_every_item_type_is_accepted() -> None:
    items = [
        {"type": "waypoint", "latitude": 1, "longitude": 2, "acceptance_radius_m": 5},
        {"type": "loiter_time", "latitude": 1, "longitude": 2, "seconds": 30},
        {"type": "loiter_turns", "latitude": 1, "longitude": 2, "turns": 1},
        {"type": "land_start", "latitude": 1, "longitude": 2},
        {"type": "return_to_launch"},
    ]
    assert len(MODEL.model_validate(mission(items=items)).items) == 5
    assert MODEL.model_validate(mission(items=[{"type": "loiter_unlimited"}]))


@pytest.mark.parametrize("reference", ["home", "amsl", "terrain"])
def test_altitude_references(reference: str) -> None:
    assert MODEL.model_validate(mission(altitude_reference=reference))


@pytest.mark.parametrize(
    "overrides",
    [
        {"contract": "aerial.mission.v2"},
        {"altitude_reference": "ellipsoid"},
        {"home": {"latitude": 91, "longitude": 0, "altitude_amsl_m": 0}},
        {"home": {"latitude": 0, "longitude": 0}},
        {"cruise_speed_ms": 0},
        {"night": "yes"},
        {"items": [{"type": "takeoff", "latitude": 1, "longitude": 2}]},
        {
            "items": [
                {"type": "loiter_turns", "latitude": 1, "longitude": 2, "turns": 0}
            ]
        },
        {
            "items": [
                {"type": "loiter_turns", "latitude": 1, "longitude": 2, "turns": 256}
            ]
        },
        {
            "items": [
                {"type": "loiter_turns", "latitude": 1, "longitude": 2, "turns": 1.5}
            ]
        },
        {
            "items": [
                {"type": "loiter_time", "latitude": 1, "longitude": 2, "seconds": 0}
            ]
        },
        {"items": [{"type": "waypoint", "latitude": "45", "longitude": 2}]},
        {
            "items": [
                {"type": "waypoint", "latitude": 1, "longitude": 2, "speed_ms": -1}
            ]
        },
        {
            "items": [
                {
                    "type": "loiter_turns",
                    "latitude": 1,
                    "longitude": 2,
                    "turns": 1,
                    "direction": "left",
                }
            ]
        },
    ],
)
def test_malformed_missions_are_refused(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MODEL.model_validate(mission(**overrides))


def test_a_whole_number_float_is_an_integer_turn_count() -> None:
    # JSON has one number type; 2020-12 counts 2.0 as an integer.
    item = {"type": "loiter_turns", "latitude": 1, "longitude": 2, "turns": 2.0}
    assert MODEL.model_validate(mission(items=[item])).items[0].turns == 2


def test_the_root_and_items_stay_open() -> None:
    raw = mission(
        mission_id="M-12",
        items=[{"type": "waypoint", "latitude": 1, "longitude": 2, "x-note": "gate"}],
    )
    model = MODEL.model_validate(raw)
    dumped = model.model_dump(exclude_none=True)
    assert dumped["mission_id"] == "M-12"
    assert dumped["items"][0]["x-note"] == "gate"


def test_the_schema_carries_no_vehicle_envelope() -> None:
    """Bank limit, airspeeds and endurance belong to the vehicle, not the plan."""
    schema = _ENTRY.schema_json()
    names = set(schema["properties"])
    for definition in schema["$defs"].values():
        names |= set(definition["properties"])
    for vehicle_key in ("max_bank", "endurance", "airspeed", "loiter_radius"):
        assert not [name for name in names if vehicle_key in name]
