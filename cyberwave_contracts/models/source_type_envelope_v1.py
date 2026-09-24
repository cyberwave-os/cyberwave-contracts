# !! GENERATED from source_type.envelope.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceTypeEnvelopeV1(BaseModel):
    """Cyberwave Source Type Envelope

    Shared transport overlay for the source_type discriminator on flat Cyberwave messages.
    """

    model_config = ConfigDict(extra="allow")

    source_type: Literal[
        "edge", "edge_leader", "edge_follower", "tele", "edit", "sim", "sim_tele"
    ] = Field(..., description="Origin and routing discriminator for the message.")
