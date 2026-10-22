from datetime import date

from sqlalchemy import select

from iwardrobe.db import SessionLocal
from iwardrobe.models import WearRecord


def add_garment(client, category, name=None, **changes):
    response = client.post(
        "/api/garments",
        json={"name": name or category, "category": category, **changes},
    )
    assert response.status_code == 201, response.text
    return response.json()


def update_garment(client, garment, **changes):
    # Intentionally use the pre-recommendations payload to exercise old clients.
    payload = {
        key: garment[key]
        for key in (
            "name",
            "category",
            "color",
            "season",
            "material",
            "care",
            "notes",
            "status",
            "favorite",
        )
    }
    response = client.patch(
        f"/api/garments/{garment['id']}",
        json={**payload, "expected_version": garment["version"], **changes},
    )
    assert response.status_code == 200, response.text
    return response.json()


def wardrobe(client):
    return [
        add_garment(
            client,
            "top",
            warmth="light",
            layer="base",
            sleeve_length="long",
            style="casual",
            color="白色",
        ),
        add_garment(
            client,
            "bottom",
            warmth="light",
            bottom_length="long",
            style="casual",
            color="深蓝色",
        ),
        add_garment(client, "shoes", warmth="light", style="casual", color="白色"),
    ]


def recommend(client, **weather):
    response = client.post(
        "/api/recommendations",
        json={
            "weather": {
                "location": None,
                "date": date.today().isoformat(),
                "start_hour": 8,
                "end_hour": 20,
                "manual": {
                    "feels_min": 18,
                    "feels_max": 24,
                    "rain_probability": 0,
                    "wind_kph": 0,
                    **weather,
                },
            },
            "occasion": "casual",
            "exposure": "commute",
            "thermal_preference": "neutral",
        },
    )
    assert response.status_code in (200, 201), response.text
    return response.json()


def item_ids(outfit):
    return {item["id"] for item in outfit["items"]}


def endpoint(run, outfit, action):
    return f"/api/recommendations/{run['id']}/outfits/{outfit['id']}/{action}"


def wear(client, run, outfit):
    response = client.post(endpoint(run, outfit, "wear"))
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_wardrobe_has_no_invented_outfits(authenticated):
    assert authenticated.get("/api/recommendations/latest").json() is None
    run = recommend(authenticated)
    assert run["outfits"] == []
    assert run["warnings"]
    latest = authenticated.get("/api/recommendations/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == run["id"]


def test_recommendations_use_only_the_owners_available_garments(authenticated, bob):
    available = wardrobe(authenticated)
    laundry = add_garment(authenticated, "top", "待洗上装")
    update_garment(authenticated, laundry, status="laundry")
    archived = add_garment(authenticated, "dress", "已收纳连衣裙")
    update_garment(authenticated, archived, status="archived")
    wardrobe(bob)

    run = recommend(authenticated)
    assert len(run["outfits"]) == 1
    outfit = run["outfits"][0]
    assert item_ids(outfit) == {item["id"] for item in available}
    assert outfit["complete"]
    assert all(item["status"] == "available" for item in outfit["items"])
    assert bob.get("/api/recommendations/latest").json() is None
    assert bob.get(f"/api/recommendations/{run['id']}").status_code == 404
    for action in ("wear", "swap"):
        payload = {"garment_id": available[0]["id"]} if action == "swap" else None
        assert bob.post(endpoint(run, outfit, action), json=payload).status_code == 404
    assert bob.put(endpoint(run, outfit, "feedback"), json={"comfort": "cold"}).status_code == 404


def test_templates_are_complete_and_do_not_mix_dress_with_separates(authenticated):
    wardrobe(authenticated)
    add_garment(authenticated, "dress", warmth="light", sleeve_length="long")
    run = recommend(authenticated)
    categories = [{item["category"] for item in outfit["items"]} for outfit in run["outfits"]]
    assert {"top", "bottom", "shoes"} in categories
    assert {"dress", "shoes"} in categories
    assert all(outfit["complete"] for outfit in run["outfits"])
    assert all(len(item_ids(outfit)) == len(outfit["items"]) for outfit in run["outfits"])
    assert len(run["outfits"]) <= 3


def test_missing_shoes_is_explicit_and_incomplete_outfit_cannot_be_worn(authenticated):
    add_garment(authenticated, "top", warmth="light", layer="base")
    add_garment(authenticated, "bottom", warmth="light")
    run = recommend(authenticated)
    assert run["outfits"]
    for outfit in run["outfits"]:
        assert not outfit["complete"]
        assert "鞋" in " ".join(run["warnings"] + outfit["warnings"])
        assert authenticated.post(endpoint(run, outfit, "wear")).status_code == 409
    assert all(item["wear_count"] == 0 for item in authenticated.get("/api/garments").json())


def test_small_wardrobe_returns_only_distinct_available_combinations(authenticated):
    wardrobe(authenticated)
    add_garment(
        authenticated,
        "top",
        "另一件上装",
        warmth="light",
        layer="base",
        sleeve_length="long",
        color="灰色",
    )
    run = recommend(authenticated)
    signatures = {frozenset(item_ids(outfit)) for outfit in run["outfits"]}
    assert len(run["outfits"]) == 2
    assert len(signatures) == len(run["outfits"])


def test_cold_weather_requires_warm_layer_when_available(authenticated):
    add_garment(authenticated, "top", warmth="medium", layer="base", sleeve_length="long")
    add_garment(authenticated, "bottom", warmth="medium", bottom_length="long")
    add_garment(authenticated, "shoes", warmth="medium")
    coat = add_garment(
        authenticated,
        "outerwear",
        warmth="warm",
        layer="outer",
        sleeve_length="long",
        wind_protection="yes",
    )
    run = recommend(authenticated, feels_min=9, feels_max=14)
    assert run["outfits"]
    assert all(coat["id"] in item_ids(outfit) for outfit in run["outfits"])


def test_unknown_upper_layers_do_not_allow_known_short_bottoms_in_cold(authenticated):
    add_garment(authenticated, "top", layer="base", sleeve_length="long")
    add_garment(authenticated, "outerwear", layer="outer")
    add_garment(authenticated, "shoes")
    shorts = add_garment(authenticated, "bottom", warmth="warm", bottom_length="short")
    trousers = add_garment(authenticated, "bottom", warmth="warm", bottom_length="long")

    run = recommend(authenticated, feels_min=2, feels_max=7)

    assert run["outfits"]
    assert all(trousers["id"] in item_ids(outfit) for outfit in run["outfits"])
    assert all(shorts["id"] not in item_ids(outfit) for outfit in run["outfits"])


def test_thick_upper_layers_do_not_compensate_for_known_thin_bottoms_in_cold(authenticated):
    add_garment(authenticated, "top", warmth="warm", layer="base", sleeve_length="long")
    add_garment(authenticated, "top", warmth="warm", layer="mid")
    add_garment(authenticated, "outerwear", warmth="warm", layer="outer")
    add_garment(authenticated, "shoes", warmth="warm")
    thin = add_garment(authenticated, "bottom", warmth="light", bottom_length="long")
    warm = add_garment(authenticated, "bottom", warmth="warm", bottom_length="long")

    run = recommend(authenticated, feels_min=0, feels_max=4)

    assert run["outfits"]
    assert all(warm["id"] in item_ids(outfit) for outfit in run["outfits"])
    assert all(thin["id"] not in item_ids(outfit) for outfit in run["outfits"])


def test_rain_does_not_turn_unknown_protection_into_a_claim(authenticated):
    wardrobe(authenticated)
    run = recommend(authenticated, rain_probability=90)
    assert run["outfits"]
    for outfit in run["outfits"]:
        assert "防雨属性未确认" in " ".join(run["warnings"] + outfit["warnings"])


def test_swap_changes_one_piece_and_keeps_the_rest(authenticated, bob):
    wardrobe(authenticated)
    alternative = add_garment(
        authenticated,
        "top",
        "可替换上装",
        warmth="light",
        layer="base",
        sleeve_length="long",
    )
    foreign = add_garment(bob, "top", "其他账户的上装", warmth="light", layer="base")
    dirty = add_garment(authenticated, "top", "待洗替换候选", warmth="light", layer="base")
    update_garment(authenticated, dirty, status="laundry")
    run = recommend(authenticated)
    original = run["outfits"][0]
    target = next(item for item in original["items"] if item["category"] == "top")
    response = authenticated.post(
        endpoint(run, original, "swap"), json={"garment_id": target["id"]}
    )
    assert response.status_code == 200, response.text
    updated = next(item for item in response.json()["outfits"] if item["id"] == original["id"])
    assert item_ids(updated) - item_ids(original)
    assert item_ids(original) - item_ids(updated) == {target["id"]}
    assert len(item_ids(updated)) == len(updated["items"]) == len(original["items"])
    assert not {foreign["id"], dirty["id"]} & item_ids(updated)
    assert alternative["id"] in item_ids(updated) | item_ids(original)
    assert updated["complete"]
    rejected = authenticated.post(
        endpoint(run, updated, "swap"), json={"garment_id": foreign["id"]}
    )
    assert rejected.status_code in (404, 422)


def test_swap_without_a_valid_replacement_leaves_the_run_unchanged(authenticated):
    items = wardrobe(authenticated)
    run = recommend(authenticated)
    outfit = run["outfits"][0]
    response = authenticated.post(
        endpoint(run, outfit, "swap"), json={"garment_id": items[0]["id"]}
    )
    assert response.status_code == 409
    saved = authenticated.get(f"/api/recommendations/{run['id']}").json()
    assert item_ids(saved["outfits"][0]) == item_ids(outfit)


def test_confirming_outfit_wear_is_atomic_and_idempotent(authenticated):
    wardrobe(authenticated)
    run = recommend(authenticated)
    outfit = run["outfits"][0]
    first = wear(authenticated, run, outfit)
    second = wear(authenticated, run, outfit)
    assert first["outfits"][0]["worn_at"]
    assert second["outfits"][0]["worn_at"] == first["outfits"][0]["worn_at"]
    assert all(item["wear_count"] == 1 for item in authenticated.get("/api/garments").json())
    with SessionLocal() as db:
        recorded = db.scalars(select(WearRecord)).all()
        assert len(recorded) == len(outfit["items"])
        assert {record.garment_id for record in recorded} == item_ids(outfit)
    assert (
        authenticated.post(
            endpoint(run, outfit, "swap"), json={"garment_id": outfit["items"][0]["id"]}
        ).status_code
        == 409
    )


def test_changed_garment_invalidates_whole_outfit_without_partial_wear(authenticated):
    items = wardrobe(authenticated)
    run = recommend(authenticated)
    outfit = run["outfits"][0]
    update_garment(authenticated, items[-1], status="laundry")
    saved = authenticated.get(f"/api/recommendations/{run['id']}").json()
    assert saved["outfits"][0]["stale"]
    assert authenticated.post(endpoint(run, outfit, "wear")).status_code == 409
    assert all(item["wear_count"] == 0 for item in authenticated.get("/api/garments").json())
    with SessionLocal() as db:
        assert db.scalars(select(WearRecord)).all() == []


def test_version_change_alone_also_rejects_old_recommendation(authenticated):
    items = wardrobe(authenticated)
    run = recommend(authenticated)
    outfit = run["outfits"][0]
    update_garment(authenticated, items[0], notes="已重新确认衣物信息")
    assert authenticated.post(endpoint(run, outfit, "wear")).status_code == 409
    assert all(item["wear_count"] == 0 for item in authenticated.get("/api/garments").json())


def test_wearing_one_run_makes_another_snapshot_stale(authenticated):
    wardrobe(authenticated)
    first = recommend(authenticated)
    second = recommend(authenticated)
    wear(authenticated, first, first["outfits"][0])
    refreshed = authenticated.get(f"/api/recommendations/{second['id']}").json()
    assert refreshed["outfits"][0]["stale"]
    assert authenticated.post(endpoint(second, second["outfits"][0], "wear")).status_code == 409


def test_feedback_requires_wear_and_replacing_feedback_does_not_double_learn(authenticated):
    wardrobe(authenticated)
    run = recommend(authenticated)
    outfit = run["outfits"][0]
    url = endpoint(run, outfit, "feedback")
    cold = {"comfort": "cold", "liked": None}
    assert authenticated.put(url, json=cold).status_code == 409
    wear(authenticated, run, outfit)

    assert authenticated.put(url, json=cold).status_code == 200
    learned = recommend(authenticated)
    assert "1 次冷热反馈、0 次喜好反馈" in learned["learning_note"]
    assert authenticated.put(url, json=cold).status_code == 200
    repeated = recommend(authenticated)
    assert repeated["learning_note"] == learned["learning_note"]

    assert authenticated.put(url, json={"comfort": "cold", "liked": True}).status_code == 200
    both = recommend(authenticated)
    assert "1 次冷热反馈、1 次喜好反馈" in both["learning_note"]
    assert authenticated.put(url, json={"comfort": None, "liked": True}).status_code == 200
    liked_only = recommend(authenticated)
    assert "0 次冷热反馈、1 次喜好反馈" in liked_only["learning_note"]
    saved = authenticated.get(f"/api/recommendations/{run['id']}").json()
    assert saved["outfits"][0]["feedback"] == {"comfort": None, "liked": True}
    assert authenticated.get("/api/recommendations/preferences").json()["thermal_preference"] == (
        "neutral"
    )


def test_preferences_are_persisted_per_user(authenticated, bob):
    url = "/api/recommendations/preferences"
    bob_initial = bob.get(url).json()
    preference = {
        "location": {
            "label": "上海",
            "latitude": 31.23,
            "longitude": 121.47,
            "timezone": "Asia/Shanghai",
        },
        "start_hour": 9,
        "end_hour": 18,
        "occasion": "work",
        "exposure": "indoor",
        "thermal_preference": "cold",
    }
    saved = authenticated.put(url, json=preference)
    assert saved.status_code == 200, saved.text
    assert authenticated.get(url).json() == preference
    assert bob.get(url).json() == bob_initial


def test_old_garment_update_payload_preserves_new_tags(authenticated):
    tags = {
        "warmth": "warm",
        "layer": "outer",
        "sleeve_length": "long",
        "bottom_length": "long",
        "style": "smart",
        "rain_protection": "yes",
        "wind_protection": "no",
    }
    garment = add_garment(authenticated, "outerwear", **tags)
    updated = update_garment(authenticated, garment, notes="旧版页面修改备注")
    assert {key: updated[key] for key in tags} == tags
    cleared = update_garment(authenticated, updated, warmth="unknown")
    assert cleared["warmth"] == "unknown"
    assert {key: cleared[key] for key in tags if key != "warmth"} == {
        key: value for key, value in tags.items() if key != "warmth"
    }
