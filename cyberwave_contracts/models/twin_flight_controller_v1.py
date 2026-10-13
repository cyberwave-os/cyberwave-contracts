# !! GENERATED from twin.flight_controller.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Integer, Number


class TwinFlightControllerV1Home(BaseModel):
    """TwinFlightControllerV1Home

    The home position the autopilot returns to (HOME_POSITION).
    """

    model_config = ConfigDict(extra="allow")

    altitude: Number = Field(
        ..., description="Altitude in metres above mean sea level."
    )
    latitude: Number = Field(
        ..., ge=-90, le=90, description="WGS-84 latitude in decimal degrees."
    )
    longitude: Number = Field(
        ..., ge=-180, le=180, description="WGS-84 longitude in decimal degrees."
    )


class TwinFlightControllerV1Link(BaseModel):
    """TwinFlightControllerV1Link

    The driver's MAVLink link to the autopilot. Present for drivers that keep running, and keep publishing this state, while the aircraft is unreachable.
    """

    model_config = ConfigDict(extra="allow")

    connected: Boolean = Field(
        ...,
        description="Whether a HEARTBEAT arrived within the driver's link timeout. When false every other field is the last known value.",
    )
    reboots: Integer | None = Field(
        None,
        ge=0,
        description="Autopilot reboots the driver has observed since it started.",
    )
    transmit_enabled: Boolean | None = Field(
        None,
        description="Whether the driver may transmit to the autopilot; false on a listen-only link.",
    )
    vehicle_sysid: Integer | None = Field(
        None,
        ge=1,
        le=255,
        description="MAVLink system id of the vehicle the driver follows; null before the first HEARTBEAT.",
    )


class TwinFlightControllerV1Mission(BaseModel):
    """TwinFlightControllerV1Mission

    Progress through the mission loaded on the autopilot, as the autopilot numbers its items.
    """

    model_config = ConfigDict(extra="allow")

    current_seq: Integer = Field(
        ...,
        ge=0,
        description="Sequence number of the item the autopilot is executing (MISSION_CURRENT.seq).",
    )
    last_reached_seq: Integer | None = Field(
        None,
        ge=0,
        description="Sequence number of the last item the autopilot reported reached (MISSION_ITEM_REACHED).",
    )
    total: Integer | None = Field(
        None,
        ge=1,
        description="Number of items in the loaded mission, when the autopilot reports it.",
    )


class TwinFlightControllerV1StatusTexts(BaseModel):
    """TwinFlightControllerV1StatusTexts"""

    model_config = ConfigDict(extra="allow")

    text: str = Field(
        ..., description="The message text, without trailing NUL padding."
    )
    severity: Integer | None = Field(
        None,
        ge=0,
        le=7,
        description="MAV_SEVERITY: 0 emergency ... 3 error, 4 warning ... 6 info, 7 debug.",
    )


class TwinFlightControllerV1(BaseModel):
    """Cyberwave Twin Flight Controller State

    The autopilot's slowly-changing state as an aircraft driver decodes it: armed, flight mode, failsafe, pre-arm verdict, recent status texts, and optionally the link, mission progress and home position. Published on {prefix}cyberwave/twin/{twin_uuid}/flight_controller whenever it changes, plus a slow refresh, so a stored history is a mode-transition history. Identified by its topic, not by a field: the payload carries no contract id. Fields a single driver adds beyond these (PX4's params, a control level) ride along under the open root and are not part of this contract.
    """

    model_config = ConfigDict(extra="allow")

    armed: Boolean = Field(
        ...,
        description="Whether the autopilot reports its motors armed (MAV_MODE_FLAG_SAFETY_ARMED).",
    )
    failsafe: Boolean = Field(
        ...,
        description="Whether the autopilot is in a failsafe, as the driver derives it for its firmware.",
    )
    mode: str = Field(
        ...,
        description="Decoded flight mode name as the firmware's own ground station shows it, e.g. AUTO.LOITER on PX4 or RTL on ArduPilot. For display; its spelling is the firmware's, so readers must not parse it. An undecodable mode is reported as UNKNOWN(<custom_mode>).",
    )
    source_type: Literal[
        "edge", "edge_leader", "edge_follower", "tele", "edit", "sim", "sim_tele"
    ] = Field(
        ...,
        description="Runtime that produced the state: edge for a real autopilot, sim for a simulated one (SITL). Same vocabulary as source_type.envelope.v1.",
    )
    timestamp: Number = Field(
        ..., description="Unix time in seconds at which the driver sampled the state."
    )
    type: Literal["flight_controller"] = Field(
        ..., description="Payload discriminator, always flight_controller."
    )
    autopilot: str | None = Field(
        None,
        description="Autopilot firmware family, e.g. ardupilot or px4. Absent when the driver serves one firmware and does not say which.",
    )
    custom_mode: Integer | None = Field(
        None,
        ge=0,
        description="The raw HEARTBEAT custom_mode the mode name was decoded from. Firmware-specific; meaningful only together with autopilot.",
    )
    home: TwinFlightControllerV1Home | None = Field(
        None, description="The home position the autopilot returns to (HOME_POSITION)."
    )
    link: TwinFlightControllerV1Link | None = Field(
        None,
        description="The driver's MAVLink link to the autopilot. Present for drivers that keep running, and keep publishing this state, while the aircraft is unreachable.",
    )
    mission: TwinFlightControllerV1Mission | None = Field(
        None,
        description="Progress through the mission loaded on the autopilot, as the autopilot numbers its items.",
    )
    ready_to_arm: Boolean | None = Field(
        None,
        description="The autopilot's pre-arm verdict. null or absent when the autopilot does not report one; false also while the driver itself blocks arming.",
    )
    session_id: str | None = Field(
        None,
        description="Driver session the state belongs to, when the driver runs inside one; absent or null outside one.",
    )
    status_texts: list[TwinFlightControllerV1StatusTexts] | None = Field(
        None,
        description="The most recent STATUSTEXT messages the autopilot sent, oldest first, as evidence for the state (e.g. why pre-arm fails).",
    )
    system_status: Integer | None = Field(
        None,
        ge=0,
        description="The raw HEARTBEAT system_status (MAV_STATE): 3 standby, 4 active, 5 critical, 6 emergency, 8 flight termination.",
    )
    vehicle: str | None = Field(
        None,
        description="Airframe class the firmware flies, e.g. plane, copter or vtol.",
    )
