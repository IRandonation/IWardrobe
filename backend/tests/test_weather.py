from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from iwardrobe import weather
from iwardrobe.weather_schemas import Location, ManualWeather, WeatherInput, WeatherSummary

NOW = datetime(2026, 10, 22, 2, tzinfo=timezone.utc)
CITY = Location(label="上海", latitude=31.23, longitude=121.47, timezone="Asia/Shanghai")


def request(**changes):
    return WeatherInput(location=CITY, date=date(2026, 10, 22), **changes)


def hours_payload(query, temperature=20):
    start, end = weather.wearing_window(query)
    stamps = []
    cursor = start
    while cursor < end:
        stamps.append(int(cursor.timestamp()))
        cursor += timedelta(hours=1)
    return {
        "hourly": {
            "time": stamps,
            "apparent_temperature": [temperature] * len(stamps),
            "precipitation_probability": [30] * len(stamps),
            "wind_speed_10m": [12] * len(stamps),
        }
    }


@pytest.fixture
def weather_cache(monkeypatch):
    cache = {}
    monkeypatch.setattr(weather, "utc_now", lambda: NOW)
    monkeypatch.setattr(weather, "read_cache", cache.get)
    monkeypatch.setattr(weather, "write_cache", lambda key, value: cache.update({key: value}))
    return cache


def test_manual_weather_is_explicit_and_never_calls_provider(monkeypatch):
    def unexpected(*args):
        pytest.fail("Manual weather must not fetch a provider")

    monkeypatch.setattr(weather, "fetch_json", unexpected)
    result = weather.forecast(
        WeatherInput(
            date=date(2026, 10, 22),
            manual=ManualWeather(feels_min=10, feels_max=22),
        )
    )
    assert result.source == "manual" and result.fetched_at is None
    assert result.timezone == "Asia/Shanghai" and result.warnings
    assert (result.feels_min, result.feels_max) == (10, 22)


def test_hourly_summary_uses_only_wearing_window_and_caches(monkeypatch, weather_cache):
    query = request(start_hour=8, end_hour=10)
    payload = hours_payload(query)
    payload["hourly"]["time"].insert(0, int(NOW.timestamp()) - 4 * 3600)
    payload["hourly"]["apparent_temperature"] = [-30, 17, 24]
    payload["hourly"]["precipitation_probability"] = [100, 20, 50]
    payload["hourly"]["wind_speed_10m"] = [90, 10, 16]
    calls = []

    def fetch(url, params):
        calls.append(params)
        return payload

    monkeypatch.setattr(weather, "fetch_json", fetch)
    result = weather.forecast(query)
    assert result.source == "live"
    assert (result.feels_min, result.feels_max, result.rain_probability, result.wind_kph) == (
        17,
        24,
        50,
        16,
    )
    assert calls[0]["timezone"] == "Asia/Shanghai"
    assert weather.forecast(query).source == "cache"
    assert len(calls) == 1


def test_midnight_and_half_hour_timezone_keep_complete_hourly_window():
    city = Location(label="Delhi", latitude=28.6, longitude=77.2, timezone="Asia/Kolkata")
    query = WeatherInput(location=city, date=date(2026, 10, 22), start_hour=22, end_hour=2)
    start, end = weather.wearing_window(query)
    assert end - start == timedelta(hours=4)
    assert start.minute == 30
    assert weather.parse_forecast(hours_payload(query), query).feels_min == 20


def test_dst_uses_real_elapsed_hours_and_rejects_nonexistent_hour():
    city = Location(label="New York", latitude=40.7, longitude=-74, timezone="America/New_York")
    query = WeatherInput(location=city, date=date(2026, 11, 1), start_hour=0, end_hour=24)
    start, end = weather.wearing_window(query)
    assert end - start == timedelta(hours=25)
    assert weather.parse_forecast(hours_payload(query), query).feels_max == 20
    with pytest.raises(HTTPException) as error:
        weather.wearing_window(
            WeatherInput(
                location=city,
                date=date(2026, 3, 8),
                start_hour=2,
                end_hour=4,
            )
        )
    assert error.value.status_code == 422


def test_failed_refresh_has_bounded_and_labeled_stale_fallback(monkeypatch, weather_cache):
    query = request()
    cached = weather.parse_forecast(hours_payload(query), query)
    cached.fetched_at = NOW - timedelta(hours=2)
    weather_cache[weather.cache_key(query)] = cached

    def fail(*args):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(weather, "fetch_json", fail)
    result = weather.forecast(query)
    assert result.source == "stale" and result.warnings
    assert result.fetched_at == cached.fetched_at
    cached.fetched_at = NOW - timedelta(hours=7)
    with pytest.raises(HTTPException) as error:
        weather.forecast(query)
    assert error.value.status_code == 503


@pytest.mark.parametrize("problem", ["missing", "null", "nan"])
def test_invalid_hourly_data_is_not_reported_as_a_valid_forecast(
    monkeypatch,
    weather_cache,
    problem,
):
    query = request()
    payload = hours_payload(query)
    if problem == "missing":
        for values in payload["hourly"].values():
            values.pop()
    else:
        payload["hourly"]["apparent_temperature"][0] = None if problem == "null" else float("nan")
    monkeypatch.setattr(weather, "fetch_json", lambda *args: payload)
    with pytest.raises(HTTPException) as error:
        weather.forecast(query)
    assert error.value.status_code == 503


def test_weather_inputs_reject_invalid_ranges():
    with pytest.raises(ValidationError):
        ManualWeather(feels_min=30, feels_max=10)
    with pytest.raises(ValidationError):
        ManualWeather(feels_min=10, feels_max=20, rain_probability=101)
    with pytest.raises(ValidationError):
        request(start_hour=8, end_hour=8)
    with pytest.raises(ValidationError):
        Location(label="Unknown", latitude=0, longitude=0, timezone="invalid/zone")
    with pytest.raises(ValidationError):
        WeatherSummary.model_validate({"source": "live", "feels_min": float("nan")})


def test_geocoding_requires_login_and_returns_city_timezone(client, authenticated, monkeypatch):
    monkeypatch.setattr(
        weather,
        "fetch_json",
        lambda *args: {
            "results": [
                {
                    "name": "上海",
                    "country": "中国",
                    "latitude": 31.23,
                    "longitude": 121.47,
                    "timezone": "Asia/Shanghai",
                },
                {"name": "无时区", "latitude": 0, "longitude": 0},
            ]
        },
    )
    result = authenticated.get("/api/weather/locations?q=上海")
    assert result.status_code == 200
    assert len(result.json()) == 1
    assert result.json()[0]["timezone"] == "Asia/Shanghai"
    authenticated.post("/api/auth/logout")
    assert client.get("/api/weather/locations?q=上海").status_code == 401
