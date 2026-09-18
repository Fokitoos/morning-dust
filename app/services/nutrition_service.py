"""Per-serving nutrition for a recipe: ask the model for absolute amounts,
then express each micronutrient as a share of the daily reference intake.

The reference intakes are the NIH/ODS Dietary Reference Intakes for adults
19-50, taking the higher of the female/male values where they differ (so
iron uses the 18 mg figure) — the more demanding target is the safer one to
plan a plant-based diet around. Change RDA below to retune; the label in
RDA_BASIS is shown in the UI so the basis is never hidden.
"""

import time

from fastapi import Depends, HTTPException

from app.clients.nutrition_client import NutritionClient, NutritionClientError
from app.config import settings
from app.schemas.morning_dust import Recipe
from app.schemas.nutrition import Micronutrient, NutritionEstimate, NutritionInfo
from app.services.recipe_scale_service import parse_servings

RDA_BASIS = "NIH Dietary Reference Intakes, adults 19–50 (higher of female/male)"

# key -> (label, unit, daily reference intake)
RDA: dict[str, tuple[str, str, float]] = {
    "iron_mg": ("Iron", "mg", 18.0),
    "vitamin_b12_ug": ("Vitamin B12", "µg", 2.4),
    "calcium_mg": ("Calcium", "mg", 1000.0),
    "zinc_mg": ("Zinc", "mg", 11.0),
    "iodine_ug": ("Iodine", "µg", 150.0),
    "vitamin_d_ug": ("Vitamin D", "µg", 15.0),
    "omega3_ala_g": ("Omega-3 (ALA)", "g", 1.6),
    "folate_ug": ("Folate", "µg", 400.0),
    "magnesium_mg": ("Magnesium", "mg", 400.0),
    "selenium_ug": ("Selenium", "µg", 55.0),
}


def to_nutrition_info(estimate: NutritionEstimate, servings: int) -> NutritionInfo:
    micros = []
    raw = estimate.micronutrients.model_dump()
    for key, (label, unit, rda) in RDA.items():
        amount = max(0.0, float(raw.get(key, 0) or 0))
        micros.append(Micronutrient(
            key=key, label=label, unit=unit, rda=rda,
            amount=round(amount, 2), rda_pct=round(amount / rda * 100),
        ))
    return NutritionInfo(
        calories_kcal=round(max(0.0, estimate.calories_kcal)),
        protein_g=round(max(0.0, estimate.protein_g), 1),
        carbs_g=round(max(0.0, estimate.carbs_g), 1),
        fat_g=round(max(0.0, estimate.fat_g), 1),
        fiber_g=round(max(0.0, estimate.fiber_g), 1),
        micronutrients=micros,
        assumptions=estimate.assumptions.strip(),
        confidence=estimate.confidence if estimate.confidence in ("low", "medium", "high") else "medium",
        servings=servings,
        rda_basis=RDA_BASIS,
        estimated_at=int(time.time() * 1000),
    )


class NutritionService:
    def __init__(self, client: NutritionClient) -> None:
        self._client = client

    def estimate_for(self, recipe: Recipe) -> NutritionInfo:
        if not recipe.ingredients:
            raise HTTPException(status_code=422, detail="This recipe has no ingredients to analyse")
        if not self._client.configured:
            raise HTTPException(
                status_code=503,
                detail="Nutrition estimates need an Anthropic API key — set "
                       "MORNING_DUST_ANTHROPIC_API_KEY in .env and restart.",
            )
        servings = parse_servings(recipe.servings) or 1
        try:
            estimate = self._client.estimate(recipe.title, servings, recipe.ingredients)
        except NutritionClientError as exc:
            raise HTTPException(status_code=502, detail=f"Couldn't estimate nutrition: {exc}") from exc
        return to_nutrition_info(estimate, servings)


def get_nutrition_client() -> NutritionClient:
    return NutritionClient(api_key=settings.anthropic_api_key)


def get_nutrition_service(
    client: NutritionClient = Depends(get_nutrition_client),
) -> NutritionService:
    return NutritionService(client)
