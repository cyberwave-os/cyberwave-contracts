# !! GENERATED from environment.settings.twin_motion.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from cyberwave_contracts.models._scalars import Number


class AnimationSteps(BaseModel):
    """AnimationSteps"""

    model_config = ConfigDict(extra="forbid")

    hold_ms: Number = Field(..., ge=0)
    keyframe: str = ...
    transition_ms: Number = Field(..., ge=0)


class Animation(BaseModel):
    """Animation"""

    model_config = ConfigDict(extra="allow")

    name: str = ...
    description: str | None = None
    duration: Number | None = Field(None, ge=0, description="Seconds.")
    endKeyframe: str | None = None
    interpolation: Literal["linear", "ease-in", "ease-out", "ease-in-out"] | None = None
    scope: Literal["environment", "twin", "asset"] | None = None
    startKeyframe: str | None = None
    steps: list[AnimationSteps] | None = None
    timestamp: str | None = None


class Keyframe(BaseModel):
    """Keyframe"""

    model_config = ConfigDict(extra="allow")

    name: str = ...
    description: str | None = None
    jointAngles: dict[str, Number] | None = Field(
        None, description="Joint name to angle."
    )
    joints: dict[str, Number] | None = Field(
        None, description="Legacy name for jointAngles; the backend still reads it."
    )
    scope: Literal["environment", "twin", "asset"] | None = None
    timestamp: str | None = Field(None, description="ISO 8601 time the pose was saved.")


class TwinMotion(BaseModel):
    """TwinMotion"""

    model_config = ConfigDict(extra="forbid")

    animations: list[Animation] | None = None
    keyframes: list[Keyframe] | None = None


class EnvironmentSettingsTwinMotionV1(RootModel[dict[str, TwinMotion]]):
    """Environment twin poses and movements

    Poses (keyframes) and movements (animations) saved at environment scope, keyed by twin uuid. A pose or movement is looked up by name, case-insensitively, trying the twin, then its asset, then the environment. Items stay open until the census shows which extra keys exist.
    """
