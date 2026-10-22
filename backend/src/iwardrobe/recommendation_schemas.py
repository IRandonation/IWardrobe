from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .schemas import GarmentOut
from .weather_schemas import Location, WeatherInput, WeatherSummary

Occasion = Literal["casual", "work", "sport"]
Exposure = Literal["commute", "outdoor", "indoor"]
ThermalPreference = Literal["cold", "neutral", "warm"]
Comfort = Literal["cold", "comfortable", "hot"]


class RecommendationPreferences(BaseModel):
    location: Location | None = None
    start_hour: int = Field(default=8, ge=0, le=23)
    end_hour: int = Field(default=20, ge=0, le=24)
    occasion: Occasion = "casual"
    exposure: Exposure = "commute"
    thermal_preference: ThermalPreference = "neutral"

    @model_validator(mode="after")
    def ordered_hours(self):
        if self.start_hour == self.end_hour:
            raise ValueError("出门和返回时间不能相同")
        return self


class RecommendationInput(BaseModel):
    weather: WeatherInput
    occasion: Occasion = "casual"
    exposure: Exposure = "commute"
    thermal_preference: ThermalPreference = "neutral"


class OutfitFeedback(BaseModel):
    comfort: Comfort | None = None
    liked: bool | None = None


class SwapInput(BaseModel):
    garment_id: str


class OutfitOut(BaseModel):
    id: str
    items: list[GarmentOut]
    score: float
    reasons: list[str]
    warnings: list[str]
    complete: bool
    worn_at: datetime | None
    feedback: OutfitFeedback | None
    stale: bool


class RecommendationRunOut(BaseModel):
    id: str
    created_at: datetime
    weather: WeatherSummary
    occasion: Occasion
    exposure: Exposure
    thermal_preference: ThermalPreference
    outfits: list[OutfitOut]
    warnings: list[str]
    learning_note: str
