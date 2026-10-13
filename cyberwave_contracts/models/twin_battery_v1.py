# !! GENERATED from twin.battery.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Number


class TwinBatteryV1(BaseModel):
    """Cyberwave Twin Battery Status

    A robot's own reading of its main battery. Published on {prefix}cyberwave/twin/{twin_uuid}/battery/status. A publisher that cannot report a percentage (e.g. an ArduPilot battery monitor with no configured capacity) publishes nothing here rather than a placeholder. Identified by its topic, not by a field: the payload carries no contract id.
    """

    model_config = ConfigDict(extra="allow")

    percentage: Number = Field(
        ...,
        ge=0,
        le=100,
        description="Remaining charge in percent, 0 to 100. Not a 0-1 fraction: a value in that range reads as a nearly flat battery.",
    )
    source_type: Literal[
        "edge", "edge_leader", "edge_follower", "tele", "edit", "sim", "sim_tele"
    ] = Field(
        ...,
        description="Runtime that produced the reading: edge for a real battery, sim for a simulated one. Same vocabulary as source_type.envelope.v1.",
    )
    timestamp: Number = Field(
        ..., description="Unix time in seconds at which the reading was taken."
    )
    session_id: str | None = Field(
        None,
        description="Driver session the reading belongs to, when the driver runs inside one; absent or null outside one.",
    )
    voltage: Number | None = Field(
        None,
        ge=0,
        description="Pack voltage in volts. Omitted when unknown; publishers should not send 0 as a placeholder.",
    )
