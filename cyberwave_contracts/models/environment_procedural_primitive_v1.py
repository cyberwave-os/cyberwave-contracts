# !! GENERATED from environment.procedural_primitive.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Number

from cyberwave_contracts.models.common_quaternion_v1 import CommonQuaternionV1

from cyberwave_contracts.models.common_vector3_v1 import CommonVector3V1


class EnvironmentProceduralPrimitiveV1(BaseModel):
    """Environment procedural primitive

    Compiled procedural geometry as stored: walls, racks, floor slabs and other primitives.
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
    primitive_type: str = Field(
        ...,
        min_length=1,
        description="Kind of geometry, for example box, wall or rack.",
    )
    rotation: CommonQuaternionV1 = Field(
        ...,
        description="Orientation as a quaternion. Writers are expected to keep it unit length; the schema cannot say so.",
    )
    size: CommonVector3V1 = Field(
        ..., description="Extents along the world axes, metres."
    )
    attach_offset: dict[str, Any] | None = Field(
        None, description="Offset from that frame: position and rotation."
    )
    attach_to: dict[str, Any] | None = Field(
        None,
        description="The frame the primitive hangs off. Its rules stay with the platform.",
    )
    color: str | list[Number] | None = Field(
        None, description="A colour name or hex string, or a list of channel values."
    )
    compiled: dict[str, Any] | None = Field(
        None, description="Compiled geometry the template produced."
    )
    fixed_base: Boolean | None = Field(
        None, description="Whether physics treats it as fixed."
    )
    locked: Boolean | None = Field(
        None, description="Whether the editor refuses to move it."
    )
    material: str | dict[str, Any] | None = Field(
        None, description="A material name or a material description."
    )
    metadata: dict[str, Any] | None = Field(None, description="Open user data.")
    parameters: dict[str, Any] | None = Field(None, description="Template parameters.")
    style: dict[str, Any] | None = Field(None, description="Rendering style hints.")
    template_key: str | None = Field(
        None, description="Procedural template the primitive was compiled from."
    )
    template_version: str | None = Field(None, description="Version of that template.")
    visible: Boolean | None = Field(None, description="Whether the primitive is drawn.")
