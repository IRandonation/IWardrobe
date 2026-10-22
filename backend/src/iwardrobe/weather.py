"""Open-Meteo hourly weather, bounded cache, and explicit manual fallback."""

import hashlib
import json
import math
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from redis import Redis, RedisError

from .config import settings
from .weather_schemas import Location, WeatherInput, WeatherSummary

FRESH_SECONDS = 3600
STALE_SECONDS = 21600


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def fetch_json(url: str, params: dict) -> dict:
    with httpx.Client(timeout=httpx.Timeout(8.0, connect=4.0)) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def search_locations(query: str) -> list[Location]:
    if len(query.strip()) < 2:
        raise HTTPException(422, "请输入至少两个字符的城市名")
    try:
        payload = fetch_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": query.strip(), "count": 8, "language": "zh", "format": "json"},
        )
        results = []
        for item in payload.get("results", []):
            parts = list(
                dict.fromkeys(
                    str(item[key]) for key in ("name", "admin1", "country") if item.get(key)
                )
            )
            # Some geocoder entries have no timezone and cannot define a local wearing day.
            if not item.get("timezone"):
                continue
            results.append(
                Location(
                    label=" · ".join(parts),
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                    timezone=item["timezone"],
                )
            )
        return results
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(503, "城市搜索暂时不可用，可稍后重试或先使用手动天气") from exc


def wearing_window(request: WeatherInput) -> tuple[datetime, datetime]:
    zone = ZoneInfo(request.location.timezone if request.location else "Asia/Shanghai")
    start = datetime.combine(request.date, time(request.start_hour), zone)
    end_day = request.date
    if request.end_hour <= request.start_hour or request.end_hour == 24:
        end_day += timedelta(days=1)
    end = datetime.combine(end_day, time(request.end_hour % 24), zone)
    for value in (start, end):
        if value.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != (
            value.replace(tzinfo=None)
        ):
            raise HTTPException(422, "所选时刻在该城市的夏令时切换中不存在，请调整时间")
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def cache_key(request: WeatherInput) -> str:
    encoded = json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
    return "iwardrobe:weather:v1:" + hashlib.sha256(encoded).hexdigest()


def read_cache(key: str) -> WeatherSummary | None:
    try:
        with Redis.from_url(
            settings().redis_url,
            socket_timeout=1,
            socket_connect_timeout=1,
        ) as redis:
            value = redis.get(key)
        return WeatherSummary.model_validate_json(value) if value else None
    except (RedisError, ValidationError):
        return None


def write_cache(key: str, summary: WeatherSummary) -> None:
    try:
        with Redis.from_url(
            settings().redis_url,
            socket_timeout=1,
            socket_connect_timeout=1,
        ) as redis:
            redis.setex(key, STALE_SECONDS, summary.model_dump_json())
    except RedisError:
        # A cache outage must not make a valid provider response unusable.
        pass


def parse_forecast(payload: dict, request: WeatherInput) -> WeatherSummary:
    start, end = wearing_window(request)
    hourly = payload["hourly"]
    records = {}
    for index, stamp in enumerate(hourly["time"]):
        instant = datetime.fromtimestamp(stamp, timezone.utc)
        if start <= instant < end:
            row = tuple(
                float(hourly[key][index])
                for key in (
                    "apparent_temperature",
                    "precipitation_probability",
                    "wind_speed_10m",
                )
            )
            if not all(math.isfinite(value) for value in row) or not (
                -100 <= row[0] <= 80 and 0 <= row[1] <= 100 and 0 <= row[2] <= 500
            ):
                raise ValueError("Invalid hourly weather value")
            records[instant] = row
    expected = [
        start + timedelta(hours=i) for i in range(int((end - start).total_seconds() / 3600))
    ]
    if not expected or any(instant not in records for instant in expected):
        raise ValueError("Incomplete hourly weather coverage")
    values = [records[instant] for instant in expected]
    return WeatherSummary(
        source="live",
        location_name=request.location.label,
        timezone=request.location.timezone,
        date=request.date,
        start_hour=request.start_hour,
        end_hour=request.end_hour,
        feels_min=round(min(row[0] for row in values), 1),
        feels_max=round(max(row[0] for row in values), 1),
        rain_probability=max(row[1] for row in values),
        wind_kph=round(max(row[2] for row in values), 1),
        fetched_at=utc_now(),
    )


def forecast(request: WeatherInput) -> WeatherSummary:
    if request.manual is not None:
        wearing_window(request)
        return WeatherSummary(
            source="manual",
            location_name=request.location.label if request.location else "手动天气",
            timezone=request.location.timezone if request.location else "Asia/Shanghai",
            date=request.date,
            start_hour=request.start_hour,
            end_hour=request.end_hour,
            **request.manual.model_dump(),
            fetched_at=None,
            warnings=["本次使用手动填写的天气条件，不是实时预报"],
        )
    start, end = wearing_window(request)
    local_today = utc_now().astimezone(ZoneInfo(request.location.timezone)).date()
    if not local_today <= request.date <= local_today + timedelta(days=6):
        raise HTTPException(422, "实时预报支持该城市的今天起 7 天内，请调整日期或使用手动天气")
    key = cache_key(request)
    cached = read_cache(key)
    age = (
        (utc_now() - cached.fetched_at).total_seconds()
        if (cached and cached.fetched_at and cached.fetched_at.tzinfo is not None)
        else float("inf")
    )
    if 0 <= age <= FRESH_SECONDS:
        return cached.model_copy(update={"source": "cache"})
    try:
        payload = fetch_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": request.location.latitude,
                "longitude": request.location.longitude,
                "hourly": "apparent_temperature,precipitation_probability,wind_speed_10m",
                "timezone": request.location.timezone,
                "timeformat": "unixtime",
                "wind_speed_unit": "kmh",
                "start_date": request.date.isoformat(),
                "end_date": end.astimezone(ZoneInfo(request.location.timezone)).date().isoformat(),
            },
        )
        summary = parse_forecast(payload, request)
        write_cache(key, summary)
        return summary
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        if cached and 0 <= age <= STALE_SECONDS:
            return cached.model_copy(
                update={
                    "source": "stale",
                    "warnings": ["天气刷新失败，使用 6 小时内的旧预报，请留意天气变化"],
                }
            )
        raise HTTPException(503, "天气服务暂时不可用，请稍后重试或切换手动天气") from exc
