# !! GENERATED from environment.settings.pinned_layout.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class View(BaseModel):
    """View"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "control", "camera", "audio", "route", "vehicle", "commands", "map"
    ] = ...
    mapUuid: str | None = Field(None, description="The map kind only.")
    routeId: str | None = Field(
        None, max_length=128, description="Route views only; required there."
    )
    sensorId: str | None = Field(None, max_length=128, description="Camera views only.")
    twinUuid: str | None = Field(None, description="Every kind except map.")


class EnvironmentSettingsPinnedLayoutV1(BaseModel):
    """Environment pinned layout

    The shared workspace layout of an environment: which twin and map views are pinned. It names twins and maps by uuid and grants no control. Written by PUT /environments/{uuid}/pinned-layout. Rules kept in Python: each twinItems key equals its views' twinUuid, twins and maps belong to the environment, routeId is a manual control route, sensorId applies to camera views and routeId to route views, views are not repeated.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[View] = Field(..., max_length=100)
    name: str = Field(..., min_length=1, max_length=80)
    version: Literal[1] = Field(
        ...,
        description="Version of the layout. An enum, not a const: a stored layout of another version is reported, not refused, so the shared-layout remove can still answer it with its own 409.",
    )
    twinItems: dict[str, Annotated[list[View], Field(max_length=100)]] | None = Field(
        None,
        description="Views for one twin, keyed by twin uuid. Omitted when empty; an empty list hides every view of that twin.",
    )
