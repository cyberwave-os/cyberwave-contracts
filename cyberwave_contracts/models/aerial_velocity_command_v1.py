# !! GENERATED from aerial.velocity_command.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cyberwave_contracts.models._scalars import Integer, Number


class AerialVelocityCommandV1(BaseModel):
    """Cyberwave Aerial Velocity Command

    Canonical body-frame velocity command consumed by drone simulation and edge flight adapters.
    """

    model_config = ConfigDict(extra="allow")

    angular_z: Number = Field(..., description="Yaw velocity in radians per second.")
    contract: Literal["aerial.velocity_command.v1"] = ...
    duration_ms: Integer = Field(
        ...,
        ge=0,
        le=30000,
        description="Requested command hold duration. A value of 0 represents an immediate stop command.",
    )
    linear_x: Number = Field(
        ...,
        description="Forward velocity in meters per second in the aircraft body frame.",
    )
    linear_z: Number = Field(
        ..., description="Vertical velocity in meters per second, positive upward."
    )
    origin: Literal["teleop", "ai_policy", "navigation", "workflow"] = ...
    linear_y: Number = Field(
        0.0,
        description="Lateral velocity in meters per second in the aircraft body frame.",
    )

    @field_validator("duration_ms")
    @classmethod
    def _check_duration_ms(cls, v: int) -> int:
        if v == 0:
            return v
        if 50 <= v <= 30000:
            return v
        raise ValueError("duration_ms must be 0 or between 50 and 30000")
