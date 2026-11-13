from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.capture.template import validate_endpoint_path, validate_template

# The request ID comes from an IFS link and goes into the IFS URL, so only
# allow characters that can't change the URL's meaning.
REQUEST_ID_PATTERN = r"^[A-Za-z0-9_.:-]{1,100}$"


class CaptureTargetIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    connection_id: int
    endpoint_path: str = Field(min_length=1, max_length=1000)
    http_method: Literal["PATCH", "POST"] = "PATCH"
    body_template: str = Field(min_length=2, max_length=10000)
    enabled: bool = True

    @model_validator(mode="after")
    def check_templates(self) -> Self:
        validate_endpoint_path(self.endpoint_path)
        validate_template(self.body_template)
        return self


class CaptureTargetOut(BaseModel):
    id: int
    public_id: str
    name: str
    connection_id: int
    connection_name: str
    endpoint_path: str
    http_method: Literal["PATCH", "POST"]
    body_template: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CaptureDefaults(BaseModel):
    endpoint_path: str
    http_method: Literal["PATCH", "POST"]
    body_template: str
    placeholders: dict[str, str]


class CaptureOut(BaseModel):
    id: int
    target_id: int
    target_name: str
    request_id: str
    status: str
    latitude: float | None
    longitude: float | None
    accuracy: float | None
    location_error: str | None
    ip: str | None
    user_agent: str | None
    platform: str | None
    screen: str | None
    captured_at: datetime
    writeback_status: str
    writeback_error: str | None
    sent_at: datetime | None


# --- Public capture page ---


class CaptureLinkInfo(BaseModel):
    target_name: str
    request_id: str
    already_sent: bool


class CaptureSubmit(BaseModel):
    status: Literal["captured", "denied", "unavailable"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0, le=10_000_000)
    location_error: str | None = Field(default=None, max_length=500)
    user_agent: str | None = Field(default=None, max_length=512)
    platform: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=50)
    time_zone: str | None = Field(default=None, max_length=100)
    screen: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def check_location(self) -> Self:
        if self.status == "captured" and (self.latitude is None or self.longitude is None):
            raise ValueError("A captured location needs latitude and longitude.")
        if self.status != "captured":
            self.latitude = self.longitude = self.accuracy = None
        return self


class CaptureResult(BaseModel):
    ok: bool
    message: str
