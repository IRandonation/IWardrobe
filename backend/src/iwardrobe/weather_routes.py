from typing import Annotated

from fastapi import APIRouter, Depends, Query

from .identity import current_user
from .models import User
from .weather import search_locations
from .weather_schemas import Location

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/locations", response_model=list[Location])
def locations(
    user: Annotated[User, Depends(current_user)],
    q: str = Query(min_length=2, max_length=80),
):
    return search_locations(q)
