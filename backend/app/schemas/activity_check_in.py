from pydantic import BaseModel, ConfigDict, Field

from app.schemas.activity import Latitude, Longitude

ACTIVITY_CHECK_IN_REQUEST_EXAMPLE = {"latitude": 52.4232, "longitude": 16.9461}


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
