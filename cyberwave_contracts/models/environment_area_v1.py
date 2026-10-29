# !! GENERATED from environment.area.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Number

from cyberwave_contracts.models.common_quaternion_v1 import CommonQuaternionV1

from cyberwave_contracts.models.common_vector3_v1 import CommonVector3V1


class EnvironmentAreaV1Source(BaseModel):
    """EnvironmentAreaV1Source

    Where an imported area came from.
    """

    model_config = ConfigDict(extra="forbid")

    format: Literal["kml", "geojson", "manual"] = Field(
        ..., description="Import format."
    )
    name: str = Field(..., description="Source file or layer name.")


class EnvironmentAreaV1(BaseModel):
    """Environment area

    A semantic zone as stored: a box area, or an operating area that also carries geodetic geometry and an altitude band.
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
    size: CommonVector3V1 = Field(
        ..., description="Box extents along the world axes, metres."
    )
    altitude_reference: Literal["geo_anchor"] | None = Field(
        None, description="What floor_m and ceiling_m are measured from."
    )
    ceiling_m: Number | None = Field(
        None, description="Upper altitude bound, metres above the geo anchor."
    )
    floor_m: Number | None = Field(
        None, description="Lower altitude bound, metres above the geo anchor."
    )
    geometry: dict[str, Any] | None = Field(
        None,
        description="Geodetic polygon of an operating area (type, vertices, holes). Its ring rules stay with the platform.",
    )
    locked: Boolean | None = Field(
        None, description="Whether the editor refuses to move it."
    )
    metadata: dict[str, Any] | None = Field(None, description="Open user data.")
    role: str | None = Field(
        None,
        description="Operating-area role. The allowed values stay with the platform.",
    )
    source: EnvironmentAreaV1Source | None = Field(
        None, description="Where an imported area came from."
    )
    visible: Boolean | None = Field(None, description="Whether the area is drawn.")
