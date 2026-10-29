# !! GENERATED from environment.settings.embed.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Number


class EnvironmentSettingsEmbedV1Camera(BaseModel):
    """EnvironmentSettingsEmbedV1Camera

    3D camera pose in the environment frame.
    """

    model_config = ConfigDict(extra="forbid")

    position: Annotated[list[Number], Field(min_length=3, max_length=3)] = ...
    target: Annotated[list[Number], Field(min_length=3, max_length=3)] = ...


class EnvironmentSettingsEmbedV1(BaseModel):
    """Environment live embed

    Configuration of an environment's public live embed: whether it is on, whether it shows the 3D scene or one camera sensor, and the 3D camera pose. Written by update_embed. Rules kept in Python: only sharing administrators change enabled; enabling needs camera; in sensor mode twin_uuid must be a twin of this environment and sensor_id one of its rgb or depth sensors.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: Boolean = Field(..., description="Whether the embed link is live.")
    mode: Literal["3d", "sensor"] = Field(
        ..., description="The 3D scene or a single camera sensor."
    )
    camera: EnvironmentSettingsEmbedV1Camera | None = Field(
        None, description="3D camera pose in the environment frame."
    )
    link_uuid: str | None = Field(
        None,
        json_schema_extra={"readOnly": True},
        description="The reader link share the server created when the embed was enabled.",
    )
    sensor_id: str | None = Field(
        None, description="Sensor of that twin; used in sensor mode."
    )
    twin_uuid: str | None = Field(
        None, description="Camera twin in this environment; used in sensor mode."
    )
