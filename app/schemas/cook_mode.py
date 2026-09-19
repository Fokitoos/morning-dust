"""Cook mode: steps annotated with tappable timers."""

from pydantic import BaseModel, Field


class CookTimer(BaseModel):
    label: str  # "20 min", "1 h 30 min", "10 min – 15 min"
    seconds: int  # what the timer is set to (the longer end of a range)
    phrase: str  # the words it was read from, e.g. "for 20 minutes"


class CookStep(BaseModel):
    index: int
    text: str
    timers: list[CookTimer] = Field(default_factory=list)


class CookMode(BaseModel):
    recipe_id: int
    title: str
    servings: int | None
    ingredients: list[str]
    steps: list[CookStep]
