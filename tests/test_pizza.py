import pytest

from app.schemas.pizza import PizzaCalcRequest
from app.services.pizza_service import calculate


# ---- unit tests on the service itself ----

def _grams(resp, label_fragment):
    item = next(i for i in resp.ingredients if label_fragment in i.label.lower())
    return float(item.amount.split()[0])


def test_calculate_ingredients_sum_to_total_dough_weight():
    resp = calculate(PizzaCalcRequest(pizzas=3, hours_min=24, hours_max=24))
    total = sum(float(i.amount.split()[0]) for i in resp.ingredients)
    assert total == pytest.approx(3 * 250, abs=2)  # rounding only


def test_calculate_swaps_an_inverted_hour_window():
    resp = calculate(PizzaCalcRequest(pizzas=2, hours_min=48, hours_max=24))
    assert "24–48 h" in resp.schedule_label


def test_calculate_schedule_boundaries():
    label = lambda lo, hi: calculate(
        PizzaCalcRequest(pizzas=2, hours_min=lo, hours_max=hi)
    ).schedule_label
    assert "Same-day" in label(2, 6)
    assert "Overnight" in label(7, 18)
    assert "Classic cold ferment" in label(19, 48)


def test_calculate_same_day_uses_double_the_cold_ferment_yeast():
    same_day = calculate(PizzaCalcRequest(pizzas=4, hours_min=3, hours_max=4))
    cold = calculate(PizzaCalcRequest(pizzas=4, hours_min=24, hours_max=24))
    assert _grams(same_day, "yeast") == pytest.approx(2 * _grams(cold, "yeast"), abs=0.15)


def test_calculate_singular_wording_for_one_pizza():
    resp = calculate(PizzaCalcRequest(pizzas=1, hours_min=3, hours_max=4))
    assert resp.summary.startswith("1 pizza ×")
    assert any("1 ball of" in step for step in resp.steps)


def test_calculate_steps_mention_the_requested_rest_window():
    resp = calculate(PizzaCalcRequest(pizzas=2, hours_min=20, hours_max=40))
    assert any("20–40 h" in step for step in resp.steps)


def test_calculate_lmr_switches_both_ingredient_and_method():
    resp = calculate(PizzaCalcRequest(pizzas=2, hours_min=8, hours_max=12, yeast="lmr"))
    assert any("madre" in i.label.lower() for i in resp.ingredients)
    assert not any("instant" in i.label.lower() for i in resp.ingredients)
    assert "Dissolve the lievito madre" in resp.steps[0]


# ---- API round-trip tests ----

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
