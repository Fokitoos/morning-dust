"""Servings scaling and per-serving nutrition for the recipe book.

NutritionEstimate is exactly what the model is asked to return (absolute
amounts per serving). NutritionInfo is what gets stored on the recipe: the
same numbers plus each micronutrient's share of the daily reference intake,
computed server-side from the table in nutrition_service.py so the
percentages are ours, not the model's.
"""

from pydantic import BaseModel, Field


# ---- servings scaling ----

class ScaledIngredient(BaseModel):
    text: str
    scaled: bool  # False when the line had no leading quantity to scale


class ScaledRecipe(BaseModel):
    base_servings: int
    servings: int
    factor: float
    ingredients: list[ScaledIngredient]


# ---- nutrition ----

class MicronutrientEstimate(BaseModel):
    iron_mg: float = 0
    vitamin_b12_ug: float = 0
    calcium_mg: float = 0
    zinc_mg: float = 0
    iodine_ug: float = 0
    vitamin_d_ug: float = 0
    omega3_ala_g: float = 0
    folate_ug: float = 0
    magnesium_mg: float = 0
    selenium_ug: float = 0


class NutritionEstimate(BaseModel):
    """Per serving. This is the structured output the model fills in."""
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float = 0
    micronutrients: MicronutrientEstimate
    assumptions: str = Field(
        default="",
        description="One or two sentences on what was assumed: unclear amounts, cooked vs raw, etc.",
    )
    confidence: str = Field(default="medium", description="low, medium or high")


class Micronutrient(BaseModel):
    key: str
    label: str
    amount: float
    unit: str
    rda: float
    rda_pct: float


class NutritionInfo(BaseModel):
    """What the recipe book stores and shows: per serving."""
    calories_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float
    micronutrients: list[Micronutrient]
    assumptions: str = ""
    confidence: str = "medium"
    servings: int
    rda_basis: str
    estimated_at: int  # epoch ms
