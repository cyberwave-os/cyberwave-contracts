# !! GENERATED from common.pose.v1.schema.json -- do not edit.

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Number

from cyberwave_contracts.models.common_quaternion_v1 import CommonQuaternionV1


class CommonPoseV1Position(BaseModel):
    """CommonPoseV1Position

    Position in metres.
    """

    model_config = ConfigDict(extra="allow")

    x: Number = Field(..., description="X, in metres.")
    y: Number = Field(..., description="Y, in metres.")
    z: Number = Field(..., description="Z, in metres.")


class CommonPoseV1(BaseModel):
    """Cyberwave Pose

    Where a body is and which way it faces, in a frame the enclosing contract names: a position in metres and an orientation as a quaternion. The same six numbers as protobuf geometry.v1.Pose (`position`, `orientation`) and as the Pose in cyberwave-robot-format and the Python SDK. A pose locates one body in one frame; a transform relating two frames uses `translation` and `rotation`.
    """

    model_config = ConfigDict(extra="allow")

    orientation: CommonQuaternionV1 = ...
    position: CommonPoseV1Position = Field(..., description="Position in metres.")
