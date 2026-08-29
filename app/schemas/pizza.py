"""Pizza dough calculator: pizzas × rest window × yeast type -> ingredients + method.

Pure computation, no storage — this mirrors the shape of the other API
responses so the frontend can stay a thin form, but there's no table behind
it because there's nothing to persist between requests.
"""

from typing import Literal

from pydantic import BaseModel, Field

YeastType = Literal["dry", "lmr"]


class PizzaIngredient(BaseModel):
    label: str
    amount: str


class PizzaCalcResponse(BaseModel):
    summary: str
    ingredients: list[PizzaIngredient]
    schedule_label: str
    steps: list[str]
    bake_note: str
    source_note: str


class PizzaCalcRequest(BaseModel):
    pizzas: int = Field(ge=1, le=12)
    hours_min: int = Field(ge=2, le=72)
    hours_max: int = Field(ge=2, le=72)
    yeast: YeastType = "dry"
