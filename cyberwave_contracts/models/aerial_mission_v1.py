# !! GENERATED from aerial.mission.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Integer, Number


class MissionHome(BaseModel):
    """MissionHome

    The planned launch point. Its altitude anchors every home-relative altitude and the terrain clearance check, so it must be orthometric (MSL), not ellipsoidal (HAE).
    """

    model_config = ConfigDict(extra="allow")

    altitude_amsl_m: Number = Field(
        ..., description="Ground altitude at home in metres above mean sea level."
    )
    latitude: Number = Field(
        ..., ge=-90, le=90, description="WGS-84 latitude in degrees."
    )
    longitude: Number = Field(
        ..., ge=-180, le=180, description="WGS-84 longitude in degrees."
    )


class MissionItem(BaseModel):
    """MissionItem

    One mission item. Which fields apply depends on type: waypoint takes a position and optionally acceptance_radius_m; loiter_time takes a position and seconds (no radius: the autopilot's default loiter radius is flown); loiter_turns takes a position, turns and optionally radius_m and direction; loiter_unlimited takes a position and optionally radius_m and direction; return_to_launch takes nothing; land_start optionally takes a position. On waypoint and loiter items, speed_ms sets the airspeed from the leg to this item onwards.
    """

    model_config = ConfigDict(extra="allow")

    type: Literal[
        "waypoint",
        "loiter_time",
        "loiter_turns",
        "loiter_unlimited",
        "return_to_launch",
        "land_start",
    ] = ...
    acceptance_radius_m: Number | None = Field(
        None,
        ge=0,
        description="waypoint: distance at which the waypoint counts as reached. Omitted or 0: the autopilot default.",
    )
    altitude_m: Number | None = Field(
        None,
        description="Item altitude in metres, in the mission's altitude_reference frame.",
    )
    direction: Literal["cw", "ccw"] | None = Field(
        None, description="Loiter direction, clockwise when omitted."
    )
    latitude: Number | None = Field(
        None, ge=-90, le=90, description="WGS-84 latitude in degrees."
    )
    longitude: Number | None = Field(
        None, ge=-180, le=180, description="WGS-84 longitude in degrees."
    )
    radius_m: Number | None = Field(
        None,
        ge=0,
        description="loiter_turns / loiter_unlimited: loiter radius in metres. Omitted or 0: the vehicle's default loiter radius.",
    )
    seconds: Number | None = Field(
        None, gt=0, description="loiter_time: how long to loiter, in seconds."
    )
    speed_ms: Number | None = Field(
        None,
        gt=0,
        description="Waypoint and loiter items: airspeed in metres per second from the leg to this item onwards (MAV_CMD_DO_CHANGE_SPEED before the item).",
    )
    turns: Integer | None = Field(
        None,
        ge=1,
        le=255,
        description="loiter_turns: whole number of turns (stored in one byte by ArduPilot).",
    )


class AerialMissionV1(BaseModel):
    """Cyberwave Aerial Mission

    A flight plan for an aircraft: a planned home (launch point) and an ordered list of mission items. It carries the operator's intent only; the vehicle's flight envelope (bank limit, airspeeds, endurance, loiter radius, RTL altitude) comes from the twin's capabilities, never from the plan. Item semantics follow MAVLink mission commands as ArduPilot and PX4 fly them: waypoint (MAV_CMD_NAV_WAYPOINT), loiter_time (MAV_CMD_NAV_LOITER_TIME, flown at the autopilot's default loiter radius), loiter_turns (MAV_CMD_NAV_LOITER_TURNS, whole turns), loiter_unlimited (MAV_CMD_NAV_LOITER_UNLIM, ends the mission), return_to_launch (MAV_CMD_NAV_RETURN_TO_LAUNCH, ends the mission) and land_start (MAV_CMD_DO_LAND_START, a marker where a landing sequence begins). Positioned items need latitude, longitude and an altitude (their own altitude_m or the mission's default_altitude_m); per-type rules beyond the shape are enforced by the platform's plan validation.
    """

    model_config = ConfigDict(extra="allow")

    contract: Literal["aerial.mission.v1"] = ...
    home: MissionHome = ...
    items: list[MissionItem] = Field(
        ...,
        description="Mission items in flight order. At least one must be positioned. Nothing may follow return_to_launch or loiter_unlimited.",
    )
    name: str = Field(
        ...,
        description="Human-readable mission name. Plans of the same twin and name are versions of one mission.",
    )
    altitude_reference: Literal["home", "amsl", "terrain"] = Field(
        "home",
        description="What item altitudes are measured from. home: metres above the planned home (MAV_FRAME_GLOBAL_RELATIVE_ALT). amsl: metres above mean sea level (MAV_FRAME_GLOBAL). terrain: metres above the terrain under the item (MAV_FRAME_GLOBAL_TERRAIN_ALT).",
    )
    cruise_speed_ms: Number | None = Field(
        None,
        gt=0,
        description="Planned cruise airspeed in metres per second, used for timing and turn geometry. Omitted: the vehicle's cruise airspeed.",
    )
    default_altitude_m: Number | None = Field(
        None,
        description="Altitude for positioned items that give none, in the altitude_reference frame.",
    )
    night: Boolean = Field(
        False,
        description="The mission flies at night, so the vehicle's night endurance applies.",
    )
