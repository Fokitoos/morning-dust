"""Recipe importer: a URL or pasted block of text in, a saved recipe out.

The parser produces a RecipeDraft; the router stores it through the normal
RecipeStore and answers with the persisted Recipe plus the parser's
warnings, so the UI can open the new recipe and flag what to double-check."""

from pydantic import BaseModel, Field

from app.schemas.morning_dust import Recipe


class RecipeImportRequest(BaseModel):
    url: str = ""
    text: str = ""


class RecipeDraft(BaseModel):
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    servings: str = ""
    time: str = ""
    photo: str = ""
    ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    notes: str = ""
    source_url: str = ""
    # Fields the parser couldn't confidently fill in, e.g. "servings",
    # "steps" — the editor can flag these so the user knows to check them.
    warnings: list[str] = Field(default_factory=list)


class RecipeImportResult(BaseModel):
    recipe: Recipe
    source_url: str = ""
    warnings: list[str] = Field(default_factory=list)
