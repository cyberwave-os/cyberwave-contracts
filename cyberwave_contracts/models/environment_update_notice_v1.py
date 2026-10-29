# !! GENERATED from environment.update_notice.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Number


class UpdateData(BaseModel):
    """UpdateData"""

    model_config = ConfigDict(extra="allow")

    changed_fields: list[
        Literal["embed", "navigation", "odometry_anchors", "scene_hierarchy"]
    ] = Field(
        ...,
        min_length=1,
        description="The settings sections that changed. embed: the share embed. navigation: the navigation anchor. odometry_anchors: the twins' odometry anchors. scene_hierarchy: scene groups, ordering and the waypoint collections moved with them.",
    )


class EnvironmentUpdateNoticeV1(BaseModel):
    """Cyberwave Environment Update Notice

    Tells open viewers that part of an environment changed, so they refetch it. Published by the backend on {prefix}cyberwave/environment/{environment_uuid}/update after the change is committed. changed_fields names the settings sections that changed; the set is closed, so a publisher naming a section nobody listens for is an error rather than a silent no-op. The environment's twin events travel on sibling topics (twin_added, twin_updated, twin_deleted) with their own data and are not covered here. Identified by its topic, not by a field: the payload carries no contract id.
    """

    model_config = ConfigDict(extra="allow")

    data: UpdateData = ...
    type: Literal["environment_update"] = Field(
        ..., description="The message family on the environment topics."
    )
    update_type: Literal["environment_updated"] = Field(
        ..., description="What happened: part of the environment's own data changed."
    )
    source_type: str | None = Field(
        None,
        description="Who made the change, one of the source_type values. Absent on the navigation and odometry anchor notices, which predate the field; readers treat absence as lenient.",
    )
    timestamp: Number | None = Field(
        None,
        description="Seconds since the epoch. No publisher of this notice sends it today.",
    )
