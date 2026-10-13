# !! GENERATED from twin.flight_state.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Number


class TwinFlightStateV1(BaseModel):
    """Cyberwave Twin Flight State

    Whether an aircraft is airborne, as the aircraft itself reports it. Published on {prefix}cyberwave/twin/{twin_uuid}/flight_state on a plain interval with no change guard, so a reader can expire the value when the reports stop. An aircraft whose airborne state is not yet known publishes nothing rather than guessing. Identified by its topic, not by a field: the payload carries no contract id.
    """

    model_config = ConfigDict(extra="allow")

    is_flying: Boolean = Field(
        ...,
        description="Whether the aircraft is airborne. A boolean, never a string: consumers reject anything else rather than coerce it.",
    )
    source_type: Literal[
        "edge", "edge_leader", "edge_follower", "tele", "edit", "sim", "sim_tele"
    ] = Field(
        ...,
        description="Runtime that produced the report: edge for a real aircraft, sim for a simulated one. Same vocabulary as source_type.envelope.v1.",
    )
    timestamp: Number = Field(
        ..., description="Unix time in seconds at which the aircraft sampled the state."
    )
    flight_mode: str | None = Field(
        None,
        description="The aircraft's flight mode name in its own vocabulary, e.g. GPS_ATTI (DJI) or LOITER (ArduPilot). For display. Absent or empty means not reported on this tick, not that the mode was cleared.",
    )
    session_id: str | None = Field(
        None,
        description="Driver session the report belongs to, when the driver runs inside one; absent or null outside one.",
    )
