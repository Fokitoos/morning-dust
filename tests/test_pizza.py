import pytest


def test_pizza_calc_scales_flour_to_ball_count(client):
    two = client.get("/api/pizza-calc", params={"pizzas": 2, "hours_min": 24, "hours_max": 24}).json()
    four = client.get("/api/pizza-calc", params={"pizzas": 4, "hours_min": 24, "hours_max": 24}).json()

    def flour_grams(resp):
        return float(next(i["amount"].split()[0] for i in resp["ingredients"] if "flour" in i["label"]))

    assert flour_grams(four) == pytest.approx(2 * flour_grams(two), rel=0.01)


def test_pizza_calc_picks_schedule_by_rest_window(client):
    same_day = client.get("/api/pizza-calc", params={"pizzas": 2, "hours_min": 3, "hours_max": 4}).json()
    assert "Same-day" in same_day["schedule_label"]

    cold = client.get("/api/pizza-calc", params={"pizzas": 2, "hours_min": 24, "hours_max": 48}).json()
    assert "cold ferment" in cold["schedule_label"]


def test_pizza_calc_lievito_madre_uses_manufacturer_dosage(client):
    resp = client.get(
        "/api/pizza-calc", params={"pizzas": 2, "hours_min": 12, "hours_max": 12, "yeast": "lmr"}
    ).json()
    flour = float(next(i["amount"].split()[0] for i in resp["ingredients"] if "flour" in i["label"]))
    yeast = float(next(i["amount"].split()[0] for i in resp["ingredients"] if "adre" in i["label"]))
    # Molino Rossetto's own dosage: 35g per 500g flour (7%).
    assert yeast == pytest.approx(flour * 0.07, abs=1)
    assert "Natural leavening" in resp["schedule_label"]


def test_pizza_calc_rejects_out_of_range_pizza_count(client):
    assert client.get("/api/pizza-calc", params={"pizzas": 0}).status_code == 422
    assert client.get("/api/pizza-calc", params={"pizzas": 13}).status_code == 422
