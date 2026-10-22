"""Small, explicit outfit rules. Scores are ranking heuristics, not thermal measurements."""

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from itertools import product
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Garment, RecommendationRun, WearRecord, now, uid
from .recommendation_schemas import (
    OutfitFeedback,
    OutfitOut,
    RecommendationInput,
    RecommendationRunOut,
)
from .wardrobe import garment_output
from .weather_schemas import WeatherSummary

WARMTH = {"unknown": 1.8, "light": 1.0, "medium": 2.0, "warm": 3.0}
NEUTRALS = {"黑", "白", "灰", "米", "棕", "藏蓝", "black", "white", "gray", "grey", "beige", "navy"}
COLOR_NAMES = (
    ("黑", ("黑", "black")),
    ("白", ("白", "white")),
    ("灰", ("灰", "gray", "grey")),
    ("米", ("米", "beige", "cream")),
    ("棕", ("棕", "褐", "brown")),
    ("藏蓝", ("藏蓝", "navy")),
    ("蓝", ("蓝", "blue")),
    ("红", ("红", "red")),
    ("绿", ("绿", "green")),
    ("黄", ("黄", "yellow")),
    ("粉", ("粉", "pink")),
    ("紫", ("紫", "purple")),
    ("橙", ("橙", "orange")),
)


def color_family(color: str) -> str | None:
    normalized = color.strip().lower()
    for name, aliases in COLOR_NAMES:
        if any(alias in normalized for alias in aliases):
            return name
    return None


def role(garment: Garment) -> str:
    if garment.category == "outerwear" or (garment.category == "top" and garment.layer == "outer"):
        return "outer"
    if garment.category == "top" and garment.layer == "mid":
        return "mid"
    return garment.category


def learning(db: Session, user_id: str) -> dict:
    """Recalculate from current feedback, so edits and retries never double-count learning."""
    comfort: list[float] = []
    affinity: dict[str, list[int]] = defaultdict(list)
    likes = 0
    rows = db.scalars(select(RecommendationRun).where(RecommendationRun.user_id == user_id))
    for run in rows:
        for outfit in run.data["outfits"]:
            feedback = outfit.get("feedback")
            if not outfit.get("worn_at") or not feedback:
                continue
            if feedback.get("comfort") in {"cold", "comfortable", "hot"}:
                comfort.append({"cold": 1.0, "comfortable": 0.0, "hot": -1.0}[feedback["comfort"]])
            if feedback.get("liked") is not None:
                likes += 1
                value = 1 if feedback["liked"] else -1
                tags = set()
                for snapshot in outfit["snapshots"]:
                    family = color_family(snapshot["color"])
                    if family:
                        tags.add("color:" + family)
                    if snapshot["style"] != "unknown":
                        tags.add("style:" + snapshot["style"])
                for tag in tags:
                    affinity[tag].append(value)
    return {
        "thermal_adjustment": sum(comfort) / max(3, len(comfort)) * 0.6,
        "affinity": {tag: sum(values) / max(3, len(values)) for tag, values in affinity.items()},
        "note": f"已参考 {len(comfort)} 次冷热反馈、{likes} 次喜好反馈；"
        "冷热反馈只调整保暖倾向，喜好反馈只调整颜色和风格。",
    }


def recent_wears(db: Session, user_id: str) -> dict[str, datetime]:
    return dict(
        db.execute(
            select(WearRecord.garment_id, func.max(WearRecord.worn_at))
            .where(WearRecord.user_id == user_id, WearRecord.worn_at >= now() - timedelta(days=7))
            .group_by(WearRecord.garment_id)
        ).all()
    )


def target_warmth(temperature: float) -> float:
    return max(0.8, min(6.5, 1.0 + (29.0 - temperature) / 6.0))


def thermal_context(context: dict, weather: WeatherSummary, learned: dict) -> tuple[float, float]:
    # Indoor exposure still has an outdoor journey, but its cold-weather layers matter less.
    low, high = weather.feels_min, weather.feels_max
    if context["exposure"] == "indoor":
        low = 0.4 * low + 0.6 * 22
        high = 0.4 * high + 0.6 * 24
    shift = {"cold": 0.5, "neutral": 0.0, "warm": -0.5}[context["thermal_preference"]]
    shift += learned["thermal_adjustment"]
    return target_warmth(low) + shift, target_warmth(high) + shift


def item_bonus(garment: Garment, context: dict, learned: dict, recent: dict) -> float:
    desired_style = {"casual": "casual", "work": "smart", "sport": "sport"}[context["occasion"]]
    score = 1.0 if garment.favorite else 0.0
    if garment.style == desired_style:
        score += 2.0
    elif garment.style != "unknown":
        score -= 0.5
    if garment.id in recent:
        score -= 1.5
    family = color_family(garment.color)
    score += learned["affinity"].get("color:" + (family or ""), 0) * 1.5
    score += learned["affinity"].get("style:" + garment.style, 0) * 1.5
    return score


def evaluate(
    items: list[Garment],
    context: dict,
    weather: WeatherSummary,
    learned: dict,
    recent: dict,
) -> dict | None:
    roles = {role(item) for item in items}
    missing = []
    if "dress" not in roles:
        if "top" not in roles:
            missing.append("上装")
        if "bottom" not in roles:
            missing.append("下装")
    if "shoes" not in roles:
        missing.append("鞋")
    complete = not missing
    main = [item for item in items if role(item) in {"top", "bottom", "dress"}]
    layers = [item for item in items if role(item) in {"mid", "outer"}]
    # Unknown upper layers must not override a known lack of leg coverage or insulation.
    # The current template has no separate thermal leggings to compensate for thin bottoms.
    if context["exposure"] != "indoor":
        lower_body = [item for item in main if role(item) in {"bottom", "dress"}]
        if weather.feels_min < 8 and any(item.bottom_length == "short" for item in lower_body):
            return None
        if weather.feels_min < 5 and any(item.warmth == "light" for item in lower_body):
            return None
    all_thermal = main + layers
    known = bool(all_thermal) and all(item.warmth != "unknown" for item in all_thermal)
    base = sum(
        WARMTH[item.warmth] * {"top": 0.65, "bottom": 0.35, "dress": 1.0}[role(item)]
        for item in main
    )
    base += sum(
        -0.15
        if item.sleeve_length in {"short", "sleeveless"}
        else 0.1
        if item.sleeve_length == "long"
        else 0
        for item in main
        if role(item) in {"top", "dress"}
    )
    base += sum(
        -0.15 if item.bottom_length == "short" else 0.1 if item.bottom_length == "long" else 0
        for item in main
        if role(item) in {"bottom", "dress"}
    )
    insulation = base + sum(
        WARMTH[item.warmth] * (0.65 if role(item) == "outer" else 0.45) for item in layers
    )
    cold_target, hot_target = thermal_context(context, weather, learned)
    # Weather suitability is checked before preferences. A favorite cannot rescue a clearly
    # unsuitable, fully-labelled summer outfit in cold weather or a thick base in heat.
    if ("dress" in roles or {"top", "bottom"} <= roles) and known:
        if insulation < cold_target - 2.0:
            return None
        if weather.feels_max >= 26 and base > hot_target + 1.3:
            return None
        if (
            weather.feels_min < 8
            and context["exposure"] != "indoor"
            and "outer" not in roles
            and insulation < cold_target - 0.6
        ):
            return None
    warnings = []
    if missing:
        warnings.append("缺少可穿的" + "、".join(missing) + "，这是一套待补全方案。")
    unknown = [item.name for item in all_thermal if item.warmth == "unknown"]
    if unknown:
        warnings.append("厚薄未确认：" + "、".join(unknown) + "；保暖判断仅作初步参考。")
    coverage_unknown = any(
        (role(item) in {"top", "dress"} and item.sleeve_length == "unknown")
        or (role(item) in {"bottom", "dress"} and item.bottom_length == "unknown")
        for item in main
    )
    if coverage_unknown:
        warnings.append("部分衣物袖长或下装长度未确认，请核对实际覆盖程度。")
    if any(item.layer == "unknown" for item in items if item.category in {"top", "outerwear"}):
        warnings.append("部分衣物的叠穿层次未确认，请核对内搭与外层是否合适。")
    if weather.feels_min < 5:
        warnings.append("低温天气请额外核对保暖配件和实际户外停留时长。")
    if weather.feels_max >= 32:
        warnings.append("高温天气请留意补水、防晒及实际体感。")
    if insulation < cold_target - 0.8:
        warnings.append("低温时段可能偏冷，请确认厚薄或补充保暖层。")
    if base > hot_target + 0.8:
        warnings.append("高温时段内搭可能偏热，请结合室内环境调整。")
    weather_penalty = abs(insulation - cold_target) * 8 + max(0, base - hot_target) * 6
    reasons = [f"按出行时段体感 {weather.feels_min:g}–{weather.feels_max:g}℃ 选择搭配。"]
    if layers:
        reasons.append("采用可脱叠穿，进入室内或升温时可减去外层。")
    if weather.rain_probability >= 40:
        exposed = [item for item in items if role(item) in {"outer", "shoes"}]
        if not exposed or any(item.rain_protection == "unknown" for item in exposed):
            warnings.append("有降雨可能，外层或鞋的防雨属性未确认；请带伞并确认鞋履。")
        if any(item.rain_protection == "no" for item in exposed):
            warnings.append("当前外层或鞋不防雨，请准备雨具或替换单品。")
            weather_penalty += 5
        if exposed and all(item.rain_protection == "yes" for item in exposed):
            reasons.append("已优先考虑标记为防雨的外层和鞋。")
    if weather.wind_kph >= 25:
        outers = [item for item in items if role(item) == "outer"]
        if not outers or any(item.wind_protection != "yes" for item in outers):
            warnings.append("风较大，当前外层的防风能力需要确认。")
            weather_penalty += 4
        else:
            reasons.append("外层已标记为防风。")
    families = {family for item in items if (family := color_family(item.color))}
    accents = families - NEUTRALS
    if len(accents) <= 1 and families:
        color_bonus = 4
        reasons.append("以基础色或同色系为主，减少配色冲突。")
    else:
        color_bonus = max(-3, 3 - len(accents))
    if len(families) == 0:
        warnings.append("颜色信息不足，尚未判断配色。")
    desired_style = {"casual": "casual", "work": "smart", "sport": "sport"}[context["occasion"]]
    if any(item.style == desired_style for item in items):
        reasons.append("优先选择与你本次场合相符的风格标签。")
    if any(item.favorite for item in items):
        reasons.append("结合了收藏偏好。")
    if items and not any(item.id in recent for item in items):
        reasons.append("这组衣物近 7 天没有穿着记录。")
    if any(item.style == "unknown" for item in items):
        warnings.append("部分衣物风格未确认，场合适用性仍需自行核对。")
    score = 85 - weather_penalty + color_bonus
    score += sum(item_bonus(item, context, learned, recent) for item in items) / max(1, len(items))
    score -= len(missing) * 15
    return {
        "score": round(max(0, min(100, score)), 1),
        "reasons": reasons,
        "warnings": warnings,
        "complete": complete,
    }


def available_garments(db: Session, user_id: str) -> list[Garment]:
    return list(
        db.scalars(
            select(Garment)
            .where(Garment.user_id == user_id, Garment.status == "available")
            .order_by(Garment.id)
        )
    )


def candidate_outfits(
    garments: list[Garment],
    context: dict,
    weather: WeatherSummary,
    learned: dict,
    recent: dict,
) -> list[tuple[list[Garment], dict]]:
    cold_target, hot_target = thermal_context(context, weather, learned)
    groups: dict[str, list[Garment]] = defaultdict(list)
    for item in garments:
        if role(item) != "accessory":
            groups[role(item)].append(item)
    for category, values in groups.items():
        factor = 0.65 if category == "outer" else 0.45 if category == "mid" else 1.0
        target = max(0.8, cold_target - hot_target) if category in {"outer", "mid"} else hot_target
        # Bound each pool while retaining items suitable for the weather before style bonuses.
        values.sort(
            key=lambda item: (
                abs(WARMTH[item.warmth] * factor - min(3, target)) * 5
                - item_bonus(item, context, learned, recent),
                item.id,
            )
        )
        groups[category] = values[: 4 if category in {"outer", "mid"} else 8]
    shoes = groups["shoes"] or [None]
    bases = []
    if groups["top"] or groups["bottom"] or not groups["dress"]:
        bases.extend(product(groups["top"] or [None], groups["bottom"] or [None], shoes))
    if groups["dress"]:
        bases.extend(product(groups["dress"], shoes))
    overlays = list(product([None, *groups["mid"]], [None, *groups["outer"]]))
    candidates = []
    seen = set()
    for base, extra in product(bases, overlays):
        items = [item for item in (*base, *extra) if item is not None]
        identity = tuple(sorted(item.id for item in items))
        if not items or identity in seen:
            continue
        seen.add(identity)
        result = evaluate(items, context, weather, learned, recent)
        if result:
            candidates.append((items, result))
    candidates.sort(
        key=lambda row: (
            -int(row[1]["complete"]),
            -row[1]["score"],
            tuple(item.id for item in row[0]),
        )
    )
    chosen = []
    for items, result in candidates:
        ids = {item.id for item in items}
        # Do not use the second/third card merely to add/remove the very same outer layer.
        main_ids = {item.id for item in items if role(item) not in {"outer", "mid"}}
        if any(
            main_ids == {item.id for item in selected if role(item) not in {"outer", "mid"}}
            for selected, _ in chosen
        ):
            continue
        if any(
            len(ids & {item.id for item in selected}) / max(len(ids), len(selected)) > 0.75
            for selected, _ in chosen
        ):
            continue
        chosen.append((items, result))
        if len(chosen) == 3:
            break
    return chosen


def stored_outfit(
    db: Session, items: list[Garment], result: dict, outfit_id: str | None = None
) -> dict:
    return {
        "id": outfit_id or uid(),
        "snapshots": [garment_output(db, item).model_dump(mode="json") for item in items],
        **result,
        "worn_at": None,
        "feedback": None,
    }


def create_run(
    db: Session,
    user_id: str,
    payload: RecommendationInput,
    weather: WeatherSummary,
) -> RecommendationRun:
    context = payload.model_dump(exclude={"weather"})
    garments = available_garments(db, user_id)
    learned = learning(db, user_id)
    candidates = candidate_outfits(garments, context, weather, learned, recent_wears(db, user_id))
    warnings = [*weather.warnings, "保暖与配色由本地规则估计，请结合实际衣物和个人体感确认。"]
    if payload.exposure == "indoor":
        warnings.append("主要室内活动按常见室温估计；空调环境可通过冷热反馈逐渐调整。")
    if not candidates:
        warnings.append("暂无适合本次条件的可穿组合，请补充衣物或核对衣物标签。")
    elif len(candidates) < 3:
        warnings.append(f"当前衣橱可提供 {len(candidates)} 套有差异的方案。")
    row = RecommendationRun(
        user_id=user_id,
        data={
            **context,
            "weather": weather.model_dump(mode="json"),
            "outfits": [stored_outfit(db, items, result) for items, result in candidates],
            "warnings": warnings,
        },
    )
    db.add(row)
    db.commit()
    return row


def owned_run(db: Session, user_id: str, run_id: str, lock: bool = False) -> RecommendationRun:
    query = select(RecommendationRun).where(
        RecommendationRun.id == run_id, RecommendationRun.user_id == user_id
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise HTTPException(404, "搭配记录不存在")
    return row


def find_outfit(data: dict, outfit_id: str) -> dict:
    outfit = next((item for item in data["outfits"] if item["id"] == outfit_id), None)
    if not outfit:
        raise HTTPException(404, "搭配方案不存在")
    return outfit


def is_stale(outfit: dict, garments: dict[str, Garment]) -> bool:
    if outfit["worn_at"]:
        return False
    return any(
        (item := garments.get(snapshot["id"])) is None
        or item.status != "available"
        or item.version != snapshot["version"]
        for snapshot in outfit["snapshots"]
    )


def run_output(db: Session, row: RecommendationRun) -> RecommendationRunOut:
    ids = {snapshot["id"] for outfit in row.data["outfits"] for snapshot in outfit["snapshots"]}
    garments = {
        item.id: item
        for item in db.scalars(
            select(Garment).where(Garment.user_id == row.user_id, Garment.id.in_(ids))
        )
    }
    outfits = []
    for outfit in row.data["outfits"]:
        # Worn outfits retain the labels used for their feedback. Unworn cards show current
        # photos/details but become stale if any original item has changed or disappeared.
        display = (
            outfit["snapshots"]
            if outfit["worn_at"]
            else [
                garment_output(db, garments[snapshot["id"]])
                for snapshot in outfit["snapshots"]
                if snapshot["id"] in garments
            ]
        )
        outfits.append(
            OutfitOut(
                **{key: value for key, value in outfit.items() if key != "snapshots"},
                items=display,
                stale=is_stale(outfit, garments),
            )
        )
    return RecommendationRunOut(
        id=row.id,
        created_at=row.created_at,
        **{key: value for key, value in row.data.items() if key != "outfits"},
        outfits=outfits,
        learning_note=learning(db, row.user_id)["note"],
    )


def swap_item(
    db: Session, user_id: str, run_id: str, outfit_id: str, garment_id: str
) -> RecommendationRun:
    row = owned_run(db, user_id, run_id, lock=True)
    data = deepcopy(row.data)
    outfit = find_outfit(data, outfit_id)
    if outfit["worn_at"]:
        raise HTTPException(409, "已穿过的搭配保留原记录，请生成新搭配")
    garments = available_garments(db, user_id)
    by_id = {item.id: item for item in garments}
    if is_stale(outfit, by_id):
        raise HTTPException(409, "衣物已变更，请重新生成搭配")
    ids = [snapshot["id"] for snapshot in outfit["snapshots"]]
    if garment_id not in ids:
        raise HTTPException(404, "该衣物不在当前搭配中")
    current = by_id[garment_id]
    weather = WeatherSummary.model_validate(data["weather"])
    learned, recent = learning(db, user_id), recent_wears(db, user_id)
    alternatives = []
    for item in garments:
        if item.id in ids or role(item) != role(current):
            continue
        items = [item if existing == garment_id else by_id[existing] for existing in ids]
        result = evaluate(items, data, weather, learned, recent)
        if result:
            alternatives.append((items, result))
    if not alternatives:
        raise HTTPException(409, "没有符合本次条件的同类可穿替换项")
    alternatives.sort(key=lambda candidate: -candidate[1]["score"])
    index = data["outfits"].index(outfit)
    data["outfits"][index] = stored_outfit(db, *alternatives[0], outfit_id=outfit_id)
    row.data = data
    db.commit()
    return row


def wear_outfit(db: Session, user_id: str, run_id: str, outfit_id: str) -> RecommendationRun:
    row = owned_run(db, user_id, run_id, lock=True)
    data = deepcopy(row.data)
    outfit = find_outfit(data, outfit_id)
    if outfit["worn_at"]:
        return row
    weather = WeatherSummary.model_validate(data["weather"])
    if weather.date != now().astimezone(ZoneInfo(weather.timezone)).date():
        raise HTTPException(409, "只能将当地今天的搭配标记为已穿，请生成今天的搭配")
    ids = [snapshot["id"] for snapshot in outfit["snapshots"]]
    garments = {
        item.id: item
        for item in db.scalars(
            select(Garment)
            .where(Garment.user_id == user_id, Garment.id.in_(ids))
            .order_by(Garment.id)
            .with_for_update()
        )
    }
    if is_stale(outfit, garments):
        raise HTTPException(409, "衣物状态或信息已变更，请重新生成搭配")
    if not outfit["complete"]:
        raise HTTPException(409, "当前搭配缺少必要单品，请补全衣橱后重新生成")
    timestamp = now()
    for garment in garments.values():
        db.add(WearRecord(user_id=user_id, garment_id=garment.id, worn_at=timestamp))
        garment.wear_count += 1
        garment.version += 1
        garment.updated_at = timestamp
    outfit["worn_at"] = timestamp.isoformat()
    row.data = data
    db.commit()
    return row


def save_feedback(
    db: Session,
    user_id: str,
    run_id: str,
    outfit_id: str,
    payload: OutfitFeedback,
) -> RecommendationRun:
    row = owned_run(db, user_id, run_id, lock=True)
    data = deepcopy(row.data)
    outfit = find_outfit(data, outfit_id)
    if not outfit["worn_at"]:
        raise HTTPException(409, "请先记录实际穿着，再提交体感或喜好反馈")
    outfit["feedback"] = payload.model_dump()
    row.data = data
    db.commit()
    return row
