from datetime import date as Date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Location(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)
    label: str = Field(min_length=1, max_length=160)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=1, max_length=80)

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("请选择有效的城市时区") from exc
        return value


class ManualWeather(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    feels_min: float = Field(ge=-60, le=60)
    feels_max: float = Field(ge=-60, le=60)
    rain_probability: float = Field(default=0, ge=0, le=100)
    wind_kph: float = Field(default=0, ge=0, le=300)

    @model_validator(mode="after")
    def temperature_order(self):
        if self.feels_min > self.feels_max:
            raise ValueError("最低体感温度不能高于最高体感温度")
        return self


class WeatherInput(BaseModel):
    location: Location | None = None
    date: Date
    start_hour: int = Field(default=8, ge=0, le=23)
    end_hour: int = Field(default=20, ge=0, le=24)
    manual: ManualWeather | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if self.start_hour == self.end_hour:
            raise ValueError("出门和返回时间不能相同")
        if self.location is None and self.manual is None:
            raise ValueError("请选择城市，或填写手动天气")
        return self


class WeatherSummary(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    source: Literal["live", "cache", "stale", "manual"]
    location_name: str
    timezone: str
    date: Date
    start_hour: int
    end_hour: int
    feels_min: float
    feels_max: float
    rain_probability: float = Field(ge=0, le=100)
    wind_kph: float = Field(ge=0, le=500)
    fetched_at: datetime | None
    warnings: list[str] = Field(default_factory=list)
