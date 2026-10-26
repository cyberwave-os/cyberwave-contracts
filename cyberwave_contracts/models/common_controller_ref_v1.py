# !! GENERATED from common.controller_ref.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CommonControllerRefV1(BaseModel):
    """Cyberwave Controller Reference

    A typed reference to a controller policy: how it is looked up, and the value to look it up by. Used wherever a payload or a stored section names a controller (policy_ref, manual_controller_ref, default_runtime_routes values). `catalog_key` is the current spelling of a catalog reference; `catalog_seed_id` is its legacy spelling, accepted on read for one version and still what the backend emits until writers move to `catalog_key`.
    """

    model_config = ConfigDict(extra="allow")

    kind: Literal["uuid", "catalog_key", "catalog_seed_id", "slug"] = Field(
        ...,
        description="How `value` identifies the controller: its database uuid, its catalog key (shared across tiers), its slug.",
    )
    value: str = Field(
        ...,
        min_length=1,
        description="The uuid, catalog key or slug, according to `kind`.",
    )
