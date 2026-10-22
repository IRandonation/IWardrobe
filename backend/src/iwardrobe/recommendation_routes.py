from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .identity import current_user
from .models import RecommendationPreference, RecommendationRun, User
from .recommendation_schemas import (
    OutfitFeedback,
    RecommendationInput,
    RecommendationPreferences,
    RecommendationRunOut,
    SwapInput,
)
from .recommendations import (
    create_run,
    owned_run,
    run_output,
    save_feedback,
    swap_item,
    wear_outfit,
)
from .weather import forecast

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])
Db = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(current_user)]


@router.get("/preferences", response_model=RecommendationPreferences)
def get_preferences(user: Actor, db: Db):
    row = db.get(RecommendationPreference, user.id)
    return (
        RecommendationPreferences.model_validate(row.data) if row else RecommendationPreferences()
    )


@router.put("/preferences", response_model=RecommendationPreferences)
def put_preferences(payload: RecommendationPreferences, user: Actor, db: Db):
    # Serializing first writes also prevents duplicate preference rows for a new account.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = db.get(RecommendationPreference, user.id)
    if row:
        row.data = payload.model_dump(mode="json")
    else:
        db.add(RecommendationPreference(user_id=user.id, data=payload.model_dump(mode="json")))
    db.commit()
    return payload


@router.post("", response_model=RecommendationRunOut, status_code=201)
def recommend(payload: RecommendationInput, user: Actor, db: Db):
    weather = forecast(payload.weather)
    return run_output(db, create_run(db, user.id, payload, weather))


@router.get("/latest", response_model=RecommendationRunOut | None)
def latest(user: Actor, db: Db):
    row = db.scalar(
        select(RecommendationRun)
        .where(RecommendationRun.user_id == user.id)
        .order_by(RecommendationRun.created_at.desc(), RecommendationRun.id.desc())
        .limit(1)
    )
    return run_output(db, row) if row else None


@router.get("/{run_id}", response_model=RecommendationRunOut)
def get_run(run_id: str, user: Actor, db: Db):
    return run_output(db, owned_run(db, user.id, run_id))


@router.post("/{run_id}/outfits/{outfit_id}/swap", response_model=RecommendationRunOut)
def swap(run_id: str, outfit_id: str, payload: SwapInput, user: Actor, db: Db):
    return run_output(db, swap_item(db, user.id, run_id, outfit_id, payload.garment_id))


@router.post("/{run_id}/outfits/{outfit_id}/wear", response_model=RecommendationRunOut)
def wear(run_id: str, outfit_id: str, user: Actor, db: Db):
    return run_output(db, wear_outfit(db, user.id, run_id, outfit_id))


@router.put("/{run_id}/outfits/{outfit_id}/feedback", response_model=RecommendationRunOut)
def feedback(run_id: str, outfit_id: str, payload: OutfitFeedback, user: Actor, db: Db):
    return run_output(db, save_feedback(db, user.id, run_id, outfit_id, payload))
