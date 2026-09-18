from fractions import Fraction

import pytest

from app.services.recipe_scale_service import (
    format_quantity,
    parse_servings,
    scale_ingredients,
    scale_line,
)


@pytest.mark.parametrize("text,expected", [
    ("4", 4), ("4 servings", 4), ("Serves 4-6", 4), ("makes 12 muffins", 12), ("", None), ("a few", None),
])
def test_parse_servings(text, expected):
    assert parse_servings(text) == expected


@pytest.mark.parametrize("line,factor,expected", [
    ("1 kg spinach", Fraction(3, 2), "1½ kg spinach"),
    ("1/2 cup olive oil", Fraction(1, 2), "¼ cup olive oil"),
    ("1 1/2 cups flour", Fraction(2), "3 cups flour"),
    ("1½ tsp salt", Fraction(2), "3 tsp salt"),
    ("½ lemon", Fraction(3), "1½ lemon"),
    ("2-3 cloves garlic", Fraction(2), "4–6 cloves garlic"),
    ("2 to 3 cloves garlic", Fraction(1, 2), "1–1½ cloves garlic"),
    ("1.5 l water", Fraction(1, 2), "0.75 l water"),
    ("2,5 dl milk", Fraction(2), "5 dl milk"),
    ("3 eggs", Fraction(1, 3), "1 eggs"),
])
def test_scale_line_rewrites_the_leading_quantity(line, factor, expected):
    result = scale_line(line, factor)
    assert result.scaled is True
    assert result.text == expected


@pytest.mark.parametrize("line", ["salt", "juice of 1 lemon", "a handful of parsley"])
def test_scale_line_leaves_unquantified_lines_alone(line):
    result = scale_line(line, Fraction(2))
    assert result.scaled is False
    assert result.text == line


def test_format_quantity_prefers_cook_friendly_fractions():
    assert format_quantity(Fraction(1, 3)) == "⅓"
    assert format_quantity(Fraction(7, 3)) == "2⅓"
    assert format_quantity(Fraction(2)) == "2"
    assert format_quantity(Fraction(17, 100)) == "0.17"


def test_scale_ingredients_reports_factor_and_bounds():
    scaled = scale_ingredients(["2 cups rice", "salt"], base_servings=4, servings=6)
    assert scaled.factor == 1.5
    assert [i.text for i in scaled.ingredients] == ["3 cups rice", "salt"]
    assert scale_ingredients(["1 egg"], 4, 0).servings == 1
