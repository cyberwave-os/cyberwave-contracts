# !! GENERATED from twin.command_response.v1.schema.json -- do not edit.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cyberwave_contracts.models._scalars import Number


class TwinCommandResponseV1(BaseModel):
    """Cyberwave Twin Command Response

    The one reply a twin's command handler publishes for a command sent with MQTT v5 request/response properties. The request carries a Response Topic of the form {prefix}cyberwave/twin/{twin_uuid}/command/{requester_client_id}/response and opaque Correlation Data; the handler publishes this payload to that topic with the same Correlation Data. A request without a Response Topic (for example from an MQTT 3.1.1 client) gets no reply.
    """

    model_config = ConfigDict(extra="allow")

    command: str = Field(
        ..., description="The command name from the request, e.g. arm, takeoff, goto."
    )
    contract: Literal["twin.command_response.v1"] = ...
    status: Literal["accepted", "rejected", "denied", "timeout"] = Field(
        ...,
        description="accepted: the device took the command. rejected: the handler refused it before it reached the device (stale, wrong source type, unsupported or malformed). denied: the device refused it. timeout: the device did not answer in time.",
    )
    timestamp: Number = Field(
        ..., description="Unix time in seconds at which the reply was produced."
    )
    twin_uuid: str = Field(
        ..., description="The twin whose command topic received the request."
    )
    device_result: str | None = Field(
        None,
        description="The device's own result code, when it returned one (e.g. MAV_RESULT_DENIED).",
    )
    messages: list[str] | None = Field(
        None,
        description="Recent status messages the device emitted while handling the command, oldest first (e.g. PX4 preflight failures).",
    )
    reason: str | None = Field(
        None,
        description="Human-readable explanation, for any status other than accepted.",
    )
    source_type: str | None = Field(
        None,
        description="Runtime that produced the reply: edge for a physical device, sim for a simulated one.",
    )
