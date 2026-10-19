from pydantic import BaseModel, ConfigDict, Field

from app.schemas.activity import Latitude, Longitude

ACTIVITY_CHECK_IN_REQUEST_EXAMPLE = {
    "latitude": 52.4232,
    "longitude": 16.9461,
    "accuracy_m": 20,
}


class ActivityCheckIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [ACTIVITY_CHECK_IN_REQUEST_EXAMPLE]},
    )

    latitude: Latitude = Field(
        description="Submitted WGS 84 latitude (-90 to 90). Used transiently, not stored."
    )
    longitude: Longitude = Field(
        description="Submitted WGS 84 longitude (-180 to 180). PostGIS point uses longitude first. Used transiently, not stored."
    )
    accuracy_m: float = Field(
        gt=0,
        allow_inf_nan=False,
        description="Required client-reported location accuracy radius in meters, finite and positive. Values above ACTIVITY_CHECK_IN_MAX_ACCURACY_METERS (default 100) are rejected with 409 before the separate PostGIS radius check. Used transiently, not stored. This does not prevent GPS spoofing.",
    )
