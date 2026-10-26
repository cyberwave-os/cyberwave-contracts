# !! GENERATED from common.quaternion.v1.schema.json -- do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Number


class CommonQuaternionV1(BaseModel):
    """Cyberwave Quaternion

    A rotation as a quaternion with named components, listed x, y, z, w as in protobuf geometry.v1.Quaternion. The keys carry the meaning, so key order is irrelevant and the xyzw/wxyz question never arises in JSON; an array is never used. A rotation is expected to have unit length; the schema cannot say so, and writers that care check the norm with cyberwave_geometry.
    """

    model_config = ConfigDict(extra="allow")

    w: Number = Field(..., description="W component (the real part).")
    x: Number = Field(..., description="X component.")
    y: Number = Field(..., description="Y component.")
    z: Number = Field(..., description="Z component.")
