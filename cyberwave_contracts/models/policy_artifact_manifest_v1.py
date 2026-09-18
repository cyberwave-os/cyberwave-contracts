# !! GENERATED from policy_artifact_manifest.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Boolean, Integer


class ArtifactFile(BaseModel):
    """ArtifactFile"""

    model_config = ConfigDict(extra="allow")

    path: str = ...
    content_type: str | None = None
    download_url: str | None = None
    required: Boolean | None = None
    sha256: str | None = None
    size_bytes: Integer | None = Field(None, ge=0)
    storage_key: str | None = None


class PolicyArtifactManifestV1(BaseModel):
    """Cyberwave Policy Artifact Manifest

    Canonical manifest for policy artifact files shared by seeding, uploads, simulation export, and simulator loading.
    """

    model_config = ConfigDict(extra="allow")

    version: Literal["policy_artifact_manifest.v1"] = ...
    artifact_prefix: str | None = None
    cdn_prefix: str | None = None
    format: str | None = None
    optional_files: list[ArtifactFile] | None = None
    required_files: list[ArtifactFile] | None = None
    updated_at: str | None = None
    uploaded_files: list[ArtifactFile] | None = None
