# !! GENERATED from environment.settings.geo.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Number


class EnvironmentSettingsGeoV1(BaseModel):
    """Environment georeference

    Where on Earth an environment's origin sits, Clients provide the five location fields; the server sets contract_version, source, anchor_status, set_at and set_by, and replaces the whole object on every write. heading_deg is the true-north bearing of the environment's +Y axis in degrees clockwise.
    """

    model_config = ConfigDict(extra="forbid")

    altitude: Number = Field(
        ..., description="Altitude in metres, in altitude_datum, at environment z == 0."
    )
    altitude_datum: Literal["msl", "ellipsoid"] = Field(
        ..., description="Datum the altitude is expressed in."
    )
    anchor_status: Literal["manual", "unverified"] = Field(
        ...,
        json_schema_extra={"readOnly": True},
        description="unverified after an environment is cloned, until the georeference is confirmed again.",
    )
    contract_version: Literal[1] = Field(
        ...,
        json_schema_extra={"readOnly": True},
        description="Version of the georeference layout.",
    )
    heading_deg: Number = Field(
        ...,
        ge=-360,
        le=360,
        description="True-north bearing of the environment +Y axis, degrees clockwise.",
    )
    latitude: Number = Field(
        ...,
        ge=-90,
        le=90,
        description="WGS-84 latitude of the environment origin, in degrees.",
    )
    longitude: Number = Field(
        ...,
        ge=-180,
        le=180,
        description="WGS-84 longitude of the environment origin, in degrees.",
    )
    set_at: str = Field(
        ...,
        json_schema_extra={"readOnly": True},
        min_length=1,
        description="When the georeference was set, as an ISO 8601 timestamp.",
    )
    set_by: str = Field(
        ...,
        json_schema_extra={"readOnly": True},
        min_length=1,
        description="UUID of the user who set the georeference.",
    )
    source: Literal["manual"] = Field(
        ...,
        json_schema_extra={"readOnly": True},
        description="How the georeference was set.",
    )
