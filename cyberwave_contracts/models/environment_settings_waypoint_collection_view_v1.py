# !! GENERATED from environment.settings.waypoint_collection_view.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from cyberwave_contracts.models._scalars import Boolean


class Entry(BaseModel):
    """Entry"""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["markers", "trajectory"] | None = Field(
        None,
        description="Individual markers or one connected path; trajectory when absent.",
    )
    shown: Boolean | None = Field(
        None, description="Whether the collection is drawn; true when absent."
    )


class EnvironmentSettingsWaypointCollectionViewV1(RootModel[dict[str, Entry]]):
    """Waypoint collection display

    Whether each waypoint collection of an environment is drawn in the editor, and whether as separate markers or one connected trajectory. Keyed by collection name. Shared by everyone who opens the environment. A collection with no entry is shown as a trajectory.
    """
