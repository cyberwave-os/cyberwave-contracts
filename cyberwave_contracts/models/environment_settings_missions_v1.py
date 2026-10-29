# !! GENERATED from environment.settings.missions.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from cyberwave_contracts.models._scalars import Boolean, Number

from cyberwave_contracts.models.common_quaternion_v1 import CommonQuaternionV1

from cyberwave_contracts.models.common_vector3_v1 import CommonVector3V1


class WaypointGeodeticPosition(BaseModel):
    """WaypointGeodeticPosition"""

    model_config = ConfigDict(extra="forbid")

    altitude: Number = ...
    latitude: Number = ...
    longitude: Number = ...


class Waypoint(BaseModel):
    """Waypoint"""

    model_config = ConfigDict(extra="allow")

    duration_seconds: Number | None = None
    geodetic_position: WaypointGeodeticPosition | None = None
    id: str | None = None
    metadata: dict[str, Any] | None = None
    orientation: dict[str, Any] | None = None
    position: CommonVector3V1 | None = None
    rotation: CommonQuaternionV1 | None = None
    yaw: Number | None = Field(None, description="Legacy; the editor drops it on save.")


class NavigationPlan(BaseModel):
    """NavigationPlan"""

    model_config = ConfigDict(extra="allow")

    waypoints: list[Waypoint] = ...
    controller_policy_uuid: str | None = None
    id: str | None = None
    metadata: dict[str, Any] | None = None
    name: str | None = None
    reference_frame: str | None = None


class Mission(BaseModel):
    """Mission"""

    model_config = ConfigDict(extra="allow")

    id: str = ...
    name: str = ...
    twinUuid: str = ...
    createdAt: str | None = Field(None, description="ISO 8601.")
    description: str | None = None
    isActive: Boolean | None = None
    navigation: NavigationPlan | None = None
    waypoints: list[Waypoint] | None = Field(
        None,
        description="Legacy home of the waypoints; read when navigation is absent and cleared on the next edit.",
    )


class EnvironmentSettingsMissionsV1(RootModel[list[Mission]]):
    """Environment editor missions

    Waypoint paths authored in the environment editor: one list for every twin, filtered by twinUuid. Frontend-authored. Not the table-backed Mission model, and its waypoints are inline navigation waypoints, not environment waypoint objects. At most one mission per twin is active, which only the editor enforces.
    """
