"""Asks Claude for a per-serving nutrition estimate of a recipe.

There's no free, keyless food-composition API that copes with free-text
ingredient lines in several languages ("1 bndl. scallions", "½ kg spinach"),
so the estimate comes from the model with a structured-output schema
(app/schemas/nutrition.py::NutritionEstimate). The percentages of daily
intake are computed by us afterwards, not by the model.
"""

import anthropic

from app.schemas.nutrition import NutritionEstimate

MODEL = "claude-opus-5"

_SYSTEM = (
    "You are a registered dietitian estimating the nutrition of home recipes "
    "from their ingredient list, using standard food-composition data such as "
    "USDA FoodData Central. Work per serving: total the whole recipe, then "
    "divide by the number of servings given. Use sensible defaults for vague "
    "amounts (a bunch, a handful, to taste) and assume ingredients are as "
    "served (cooked weights, oil absorbed, drained where typical). Take extra "
    "care with the nutrients that matter on a plant-based diet: iron, vitamin "
    "B12, calcium, zinc, iodine, vitamin D, omega-3 ALA, folate, magnesium and "
    "selenium. Report 0 rather than guessing where a nutrient is genuinely "
    "absent (for example vitamin B12 in an unfortified vegan dish). Fill in "
    "every field of the schema with your best estimate."
)


class NutritionClientError(Exception):
    """The estimate couldn't be produced (no key, API error, refusal)."""


class NutritionClient:
    def __init__(self, api_key: str | None, timeout_s: float = 90.0) -> None:
        self._api_key = api_key
        self._timeout_s = timeout_s

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def estimate(self, title: str, servings: int, ingredients: list[str]) -> NutritionEstimate:
        if not self.configured:
            raise NutritionClientError(
                "Nutrition estimates need an Anthropic API key: set "
                "MORNING_DUST_ANTHROPIC_API_KEY in .env"
            )
        client = anthropic.Anthropic(api_key=self._api_key, timeout=self._timeout_s)
        lines = "\n".join(f"- {line}" for line in ingredients)
        prompt = (
            f"Recipe: {title}\nServings: {servings}\n\nIngredients:\n{lines}\n\n"
            "Estimate the nutrition per serving."
        )
        try:
            response = client.messages.parse(
                model=MODEL,
                max_tokens=4000,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=NutritionEstimate,
            )
        except anthropic.APIError as exc:
            raise NutritionClientError(str(exc)) from exc
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise NutritionClientError("The model didn't return an estimate")
        return response.parsed_output
