"""The twin telemetry topic contracts: flight controller, flight state, battery.

These are the first ``topic`` contracts -- identified by the MQTT topic they are
published on rather than by a contract field -- so the rules that make that kind
safe are pinned here: the schema names its topic, and it repeats the envelope's
``source_type`` vocabulary exactly rather than a private copy of it.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from cyberwave_contracts import (
    MODELS_BY_CONTRACT_ID,
    SOURCE_TYPE_VALUES,
    load_contracts,
)
from cyberwave_contracts.manifest import (
    CONTRACT_KINDS,
    SELF_IDENTIFYING_KINDS,
    TOPIC_ANNOTATION,
)

FLIGHT_CONTROLLER = "twin.flight_controller.v1"
FLIGHT_STATE = "twin.flight_state.v1"
BATTERY = "twin.battery.v1"

_CONTRACTS = {contract.id: contract for contract in load_contracts()}
_TOPIC_CONTRACTS = [c for c in _CONTRACTS.values() if c.kind == "topic"]


def test_the_telemetry_contracts_are_topic_contracts() -> None:
    assert {c.id for c in _TOPIC_CONTRACTS} >= {
        FLIGHT_CONTROLLER,
        FLIGHT_STATE,
        BATTERY,
    }
    assert "topic" in CONTRACT_KINDS
    assert "topic" not in SELF_IDENTIFYING_KINDS


@pytest.mark.parametrize("contract", _TOPIC_CONTRACTS, ids=lambda c: c.id)
def test_a_topic_contract_names_its_topic_and_no_identity_field(contract: Any) -> None:
    assert contract.id_field is None, (
        f"{contract.id} is identified by its topic; an id_field would claim a "
        "wire field its publishers do not send"
    )
    topic = contract.schema_json().get(TOPIC_ANNOTATION)
    assert isinstance(topic, str) and topic.startswith("cyberwave/twin/{twin_uuid}/"), (
        f"{contract.id} must name its twin topic in {TOPIC_ANNOTATION}"
    )


def test_topics_are_unique() -> None:
    topics = [c.schema_json()[TOPIC_ANNOTATION] for c in _TOPIC_CONTRACTS]
    assert len(topics) == len(set(topics))


@pytest.mark.parametrize(
    "contract",
    [c for c in _CONTRACTS.values() if c.has_schema],
    ids=lambda c: c.id,
)
def test_a_declared_source_type_enum_is_the_envelope_vocabulary(contract: Any) -> None:
    """A schema that spells out the enum must spell all of it, in wire order.

    The envelope is the one definition; a payload schema repeats it only so a
    validator reading that schema alone checks the field. A copy that dropped or
    added a value would be a second vocabulary.
    """
    spec = (contract.schema_json().get("properties") or {}).get("source_type")
    if spec is None or "enum" not in spec:
        pytest.skip(f"{contract.id} does not enumerate source_type")
    assert tuple(spec["enum"]) == SOURCE_TYPE_VALUES


# --- the models ------------------------------------------------------------


def _flight_controller(**over: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "flight_controller",
        "source_type": "edge",
        "timestamp": 1_760_000_000.0,
        "armed": False,
        "mode": "AUTO.LOITER",
        "custom_mode": 50593792,
        "system_status": 3,
        "failsafe": False,
        "ready_to_arm": None,
        "status_texts": [{"severity": 4, "text": "Preflight Fail: ekf2 missing data"}],
    }
    payload.update(over)
    return payload


def test_flight_controller_accepts_both_driver_shapes() -> None:
    model = MODELS_BY_CONTRACT_ID[FLIGHT_CONTROLLER]
    # PX4: no link block, a nullable pre-arm verdict, a driver-specific `params`.
    px4 = model.model_validate(
        _flight_controller(params={"requested": {}, "applied": True, "error": None})
    )
    assert px4.model_dump()["params"]["applied"] is True
    # ArduPilot via a listen-only link, before the first heartbeat named a sysid.
    model.model_validate(
        _flight_controller(
            autopilot="ardupilot",
            vehicle="plane",
            mode="LOITER",
            status_texts=[],
            link={
                "connected": False,
                "vehicle_sysid": None,
                "transmit_enabled": False,
                "reboots": 0,
            },
            mission={"current_seq": 2, "total": 7, "last_reached_seq": 1},
            home={"latitude": 45.0, "longitude": 9.0, "altitude": 120.5},
            control_level=3,
        )
    )


@pytest.mark.parametrize(
    "over",
    [
        {"type": "position"},
        {"armed": "false"},
        {"source_type": "browser"},
        {"status_texts": ["a bare string"]},
        {"status_texts": [{"severity": 9, "text": "x"}]},
        {"link": {"connected": True, "vehicle_sysid": 0}},
        {"link": {"vehicle_sysid": 1}},
        {"mission": {"total": 3}},
        {"home": {"latitude": 91.0, "longitude": 0.0, "altitude": 0.0}},
    ],
    ids=repr,
)
def test_flight_controller_rejects(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MODELS_BY_CONTRACT_ID[FLIGHT_CONTROLLER].model_validate(
            _flight_controller(**over)
        )


@pytest.mark.parametrize(
    "missing", ["type", "source_type", "timestamp", "armed", "mode", "failsafe"]
)
def test_flight_controller_requires(missing: str) -> None:
    payload = _flight_controller()
    del payload[missing]
    with pytest.raises(ValidationError):
        MODELS_BY_CONTRACT_ID[FLIGHT_CONTROLLER].model_validate(payload)


def test_flight_state() -> None:
    model = MODELS_BY_CONTRACT_ID[FLIGHT_STATE]
    model.model_validate(
        {
            "source_type": "edge",
            "timestamp": 1.0,
            "is_flying": True,
            "flight_mode": "GPS_ATTI",
        }
    )
    model.model_validate({"source_type": "sim", "timestamp": 1.0, "is_flying": False})
    for bad in (
        {"source_type": "edge", "timestamp": 1.0, "is_flying": "false"},
        {"source_type": "edge", "timestamp": 1.0},
        {"timestamp": 1.0, "is_flying": True},
    ):
        with pytest.raises(ValidationError):
            model.model_validate(bad)


@pytest.mark.parametrize("source_type", SOURCE_TYPE_VALUES)
def test_battery_accepts_every_source_type(source_type: str) -> None:
    MODELS_BY_CONTRACT_ID[BATTERY].model_validate(
        {"source_type": source_type, "timestamp": 1.0, "percentage": 78.0}
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"source_type": "edge", "timestamp": 1.0, "percentage": 100.1},
        {"source_type": "edge", "timestamp": 1.0, "percentage": -1},
        {"source_type": "edge", "timestamp": 1.0, "percentage": "78"},
        {"source_type": "edge", "timestamp": 1.0, "percentage": 78, "voltage": -1},
        # `percent` is a name a consumer may tolerate; it is not the contract.
        {"source_type": "edge", "timestamp": 1.0, "percent": 78.0},
    ],
    ids=repr,
)
def test_battery_rejects(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MODELS_BY_CONTRACT_ID[BATTERY].model_validate(payload)
