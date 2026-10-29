# !! GENERATED from common.vector3.v1.schema.json -- do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Number


class CommonVector3V1(BaseModel):
    """Cyberwave Vector3

    Three numbers with named components. The keys carry the meaning, so key order is irrelevant and an array is never used. The enclosing field names the quantity and its unit (a position in metres, a linear velocity in metres per second, a size as extents along the world axes). The same x, y, z as protobuf geometry.v1.Vector3 and as the Vector3 in cyberwave-robot-format and the Python SDK.
    """

    model_config = ConfigDict(extra="forbid")

    x: Number = Field(..., description="X component.")
    y: Number = Field(..., description="Y component.")
    z: Number = Field(..., description="Z component.")
