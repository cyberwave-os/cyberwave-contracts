# !! GENERATED from locomotion.velocity_command.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cyberwave_contracts.models._scalars import Integer, Number


class LocomotionVelocityCommandV1(BaseModel):
    """Cyberwave Locomotion Velocity Command

    Canonical body-frame velocity command consumed by backend, SDK, simulator, and edge locomotion adapters.
    """

    model_config = ConfigDict(extra="allow")

    angular_z: Number = Field(..., description="Yaw velocity in radians per second.")
    contract: Literal["locomotion.velocity_command.v1"] = ...
    duration_ms: Integer = Field(
        ...,
        ge=0,
        le=30000,
        description="Requested command hold duration. A value of 0 represents an immediate stop command.",
    )
    gait: Literal["walk", "trot", "stand"] = ...
    linear_x: Number = Field(
        ...,
        description="Forward velocity in meters per second in the robot body frame.",
    )
    origin: Literal["teleop", "ai_policy", "navigation", "workflow"] = ...
    linear_y: Number = Field(
        0.0,
        description="Lateral velocity in meters per second in the robot body frame. Adapters without lateral motion support must clamp or drop this to zero.",
    )

    @field_validator("duration_ms")
    @classmethod
    def _check_duration_ms(cls, v: int) -> int:
        if v == 0:
            return v
        if 50 <= v <= 30000:
            return v
        raise ValueError("duration_ms must be 0 or between 50 and 30000")
