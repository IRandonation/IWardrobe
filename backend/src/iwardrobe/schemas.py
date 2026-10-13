from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["top", "bottom", "outerwear", "dress", "shoes", "accessory"]
Status = Literal["available", "laundry", "archived"]
Season = Literal["all", "spring", "summer", "autumn", "winter"]


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    display_name: str


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


class GarmentInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: Category = "top"
    color: str = Field(default="未填写", max_length=40)
    season: Season = "all"
    material: str = Field(default="", max_length=120)
    care: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=1000)


class GarmentUpdate(GarmentInput):
    expected_version: int = Field(ge=1)
    status: Status = "available"
    favorite: bool = False


class VersionInput(BaseModel):
    expected_version: int = Field(ge=1)


class GarmentOut(GarmentInput):
    id: str
    status: Status
    favorite: bool
    version: int
    wear_count: int
    is_demo: bool
    asset_id: str | None
    image_url: str | None
    image_ready: bool
    created_at: datetime
    updated_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    asset_id: str
    kind: str
    status: str
    attempts: int
    error: str | None
    created_at: datetime


class ImportOut(BaseModel):
    imported: int
    message: str
