# !! GENERATED from environment.waypoint.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models.common_quaternion_v1 import CommonQuaternionV1

from cyberwave_contracts.models.common_vector3_v1 import CommonVector3V1


class EnvironmentWaypointV1Frame(BaseModel):
    """EnvironmentWaypointV1Frame

    Frame the pose is expressed in. Absent or null means the environment frame.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["twin_link", "waypoint"] = Field(
        ..., description="What the pose is relative to."
    )
    link: str | None = Field(None, description="Link of that twin.")
    twin_uuid: str | None = Field(None, description="Twin the link belongs to.")
    waypoint_id: str | None = Field(None, description="Parent waypoint.")


class EnvironmentWaypointV1(BaseModel):
    """Environment waypoint

    A named navigation point as stored for an environment: the row's columns and payload, before any read-time defaults. A missing or null pose column is reported, because readers silently turn it into zero.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        min_length=1,
        description="Stable id, unique within the environment and type.",
    )
    name: str = Field(
        ...,
        description="Display name. May be empty: readers then show a numbered fallback.",
    )
    position: CommonVector3V1 = Field(
        ..., description="Position in the environment frame, metres."
    )
    rotation: CommonQuaternionV1 = Field(
        ...,
        description="Orientation as a quaternion. Writers are expected to keep it unit length; the schema cannot say so.",
    )
    collection: str | None = Field(
        None, description="Name of the collection the waypoint belongs to."
    )
    frame: EnvironmentWaypointV1Frame | None = Field(
        None,
        description="Frame the pose is expressed in. Absent or null means the environment frame.",
    )
    metadata: dict[str, Any] | None = Field(None, description="Open user data.")
    motion_space: Literal["surface", "free_space"] | None = Field(
        None, description="Whether the pose is on a surface or free in space."
    )
