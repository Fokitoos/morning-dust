"""Turns a recipe URL or a block of pasted text into a RecipeDraft shaped
like the recipe book's own Recipe model (app/schemas/morning_dust.py).

Two extraction paths:

1. schema.org/Recipe JSON-LD — the structured data almost every recipe
   site embeds for Google's rich results. When present this is reliable:
   https://schema.org/Recipe
2. A plain-text heuristic fallback — looks for "Ingredients" / "Instructions"
   headers and reads the lines under each. Used for pasted text, and for
   pages that don't publish JSON-LD.

Nothing here talks to the network directly; that's RecipeScrapeClient's job,
injected so tests can fake it.
"""

import json
import re
from html import unescape
from html.parser import HTMLParser

from fastapi import Depends, HTTPException

from app.clients.recipe_scrape_client import RecipeFetchError, RecipeScrapeClient
from app.schemas.recipe_import import RecipeDraft, RecipeImportRequest

_INGREDIENT_HEADER = re.compile(r"^ingredients?\b", re.IGNORECASE)
_STEPS_HEADER = re.compile(r"^(instructions?|directions?|method|steps)\b", re.IGNORECASE)
# A line-leading bullet/number to strip: "-", "*", "•", "1.", "1)", "[ ] ".
_LEADING_MARKER = re.compile(r"^\s*(?:[-*•]|\[\s?[xX ]?\s?\]|\d+[.)])\s*")
_ISO_DURATION = re.compile(
    r"^P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?$", re.IGNORECASE
)


class _TextStripper(HTMLParser):
    """Minimal HTML → plain text: drops tags, keeps block-ish line breaks."""

    _BLOCK_TAGS = {
        "p", "div", "li", "br", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
        "section", "article", "ul", "ol", "table",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def strip_html(html: str) -> str:
    stripper = _TextStripper()
    stripper.feed(html)
    return stripper.text()


def _iso_duration_to_label(value: str) -> str:
    m = _ISO_DURATION.match(value.strip())
    if not m:
        return ""
    hours, minutes = m.group(1), m.group(2)
    parts = []
    if hours:
        parts.append(f"{int(hours)} h")
    if minutes:
        parts.append(f"{int(minutes)} min")
    return " ".join(parts)


def _find_ld_recipes(node) -> list[dict]:
    """Recursively hunt a parsed JSON-LD document for Recipe objects,
    unwrapping @graph and list nesting along the way."""
    found: list[dict] = []
    if isinstance(node, dict):
        types = node.get("@type")
        types = [types] if isinstance(types, str) else (types or [])
        if any(str(t).lower() == "recipe" for t in types):
            found.append(node)
        for value in node.values():
            found.extend(_find_ld_recipes(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_ld_recipes(item))
    return found


def _extract_ld_json_blocks(html: str) -> list[dict]:
    blocks = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.IGNORECASE | re.DOTALL,
    ):
        raw = unescape(match.group(1).strip())
        try:
            blocks.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return blocks


def _text_of(value) -> str:
    if isinstance(value, str):
        return strip_html(value).strip()
    if isinstance(value, dict):
        return _text_of(value.get("text") or value.get("name") or "")
    return ""


def _flatten_instructions(value) -> list[str]:
    """recipeInstructions can be a single string, a newline/HTML blob, a
    list[str], or a list of HowToStep/HowToSection dicts (possibly nested)."""
    if value is None:
        return []
    if isinstance(value, str):
        text = strip_html(value)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines if lines else ([text.strip()] if text.strip() else [])
    if isinstance(value, dict):
        items = value.get("itemListElement")
        if items:
            return _flatten_instructions(items)
        return [t] if (t := _text_of(value)) else []
    if isinstance(value, list):
        steps: list[str] = []
        for item in value:
            if isinstance(item, dict) and item.get("itemListElement"):
                steps.extend(_flatten_instructions(item["itemListElement"]))
            else:
                t = _text_of(item)
                if t:
                    steps.append(t)
        return steps
    return []


def _image_url(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("url", "") or ""
    if isinstance(value, list) and value:
        return _image_url(value[0])
    return ""


def _yield_label(value) -> str:
    if isinstance(value, list) and value:
        value = value[0]
    if value is None:
        return ""
    return strip_html(str(value)).strip()


def _tags_from_ld(recipe: dict) -> list[str]:
    tags: list[str] = []
    keywords = recipe.get("keywords")
    if isinstance(keywords, str):
        tags.extend(k.strip() for k in keywords.split(",") if k.strip())
    elif isinstance(keywords, list):
        tags.extend(str(k).strip() for k in keywords if str(k).strip())
    for key in ("recipeCategory", "recipeCuisine"):
        val = recipe.get(key)
        if isinstance(val, str) and val.strip():
            tags.append(val.strip())
        elif isinstance(val, list):
            tags.extend(str(v).strip() for v in val if str(v).strip())
    # De-dupe, keep order, cap so an over-tagged page doesn't flood the form.
    seen: set[str] = set()
    out = []
    for t in tags:
        # Some sites (argiro.gr) publish keywords in ALL CAPS; the tag chips
        # look shouty, so normalise those to lower case.
        if t.isupper():
            t = t.lower()
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out[:8]


def _draft_from_ld_recipe(recipe: dict, source_url: str) -> RecipeDraft:
    warnings: list[str] = []

    title = strip_html(str(recipe.get("name", ""))).strip()
    if not title:
        warnings.append("title")

    ingredients = [
        strip_html(str(i)).strip()
        for i in (recipe.get("recipeIngredient") or recipe.get("ingredients") or [])
        if strip_html(str(i)).strip()
    ]
    if not ingredients:
        warnings.append("ingredients")

    steps = _flatten_instructions(recipe.get("recipeInstructions"))
    if not steps:
        warnings.append("steps")

    time_label = ""
    total_time = recipe.get("totalTime")
    if isinstance(total_time, str):
        time_label = _iso_duration_to_label(total_time)
    if not time_label:
        prep = recipe.get("prepTime")
        cook = recipe.get("cookTime")
        prep_label = _iso_duration_to_label(prep) if isinstance(prep, str) else ""
        cook_label = _iso_duration_to_label(cook) if isinstance(cook, str) else ""
        if prep_label and cook_label:
            time_label = f"{prep_label} prep + {cook_label} cook"
        else:
            time_label = prep_label or cook_label

    return RecipeDraft(
        title=title or "Imported recipe",
        tags=_tags_from_ld(recipe),
        servings=_yield_label(recipe.get("recipeYield")),
        time=time_label,
        photo=_image_url(recipe.get("image")),
        ingredients=ingredients,
        steps=steps,
        notes=strip_html(str(recipe.get("description", ""))).strip()[:2000],
        source_url=source_url,
        warnings=warnings,
    )


def _parse_free_text(text: str, source_url: str = "") -> RecipeDraft:
    """Heuristic fallback for pasted text or a page with no JSON-LD Recipe:
    look for "Ingredients" / "Instructions" headers and read what's under
    each. Best-effort — always returns *something*, and flags what it had
    to guess at via `warnings`."""
    lines = [ln.strip() for ln in text.splitlines()]
    warnings: list[str] = []

    ing_start = next((i for i, ln in enumerate(lines) if _INGREDIENT_HEADER.match(ln)), None)
    step_start = next((i for i, ln in enumerate(lines) if _STEPS_HEADER.match(ln)), None)

    def _section(start_after: int | None, end: int | None) -> list[str]:
        if start_after is None:
            return []
        out = []
        for ln in lines[start_after + 1:end]:
            ln = _LEADING_MARKER.sub("", ln).strip()
            if ln:
                out.append(ln)
        return out

    ends = sorted(v for v in (ing_start, step_start) if v is not None)

    if ing_start is not None:
        ing_end = step_start if (step_start is not None and step_start > ing_start) else (
            next((e for e in ends if e > ing_start), None)
        )
        ingredients = _section(ing_start, ing_end)
    else:
        ingredients = []
        warnings.append("ingredients")

    if step_start is not None:
        step_end = ing_start if (ing_start is not None and ing_start > step_start) else None
        steps = _section(step_start, step_end)
    else:
        steps = []
        warnings.append("steps")

    # Title: first non-empty line that isn't itself a header we recognised.
    header_idxs = {i for i in (ing_start, step_start) if i is not None}
    title = ""
    for i, ln in enumerate(lines):
        if ln and i not in header_idxs:
            title = ln
            break
    if not title:
        warnings.append("title")

    return RecipeDraft(
        title=title or "Imported recipe",
        ingredients=ingredients,
        steps=steps,
        source_url=source_url,
        warnings=warnings,
    )


class RecipeImportService:
    def __init__(self, client: RecipeScrapeClient) -> None:
        self._client = client

    def import_recipe(self, req: RecipeImportRequest) -> RecipeDraft:
        url = req.url.strip()
        text = req.text.strip()
        if not url and not text:
            raise HTTPException(status_code=422, detail="Provide a recipe URL or pasted text")

        if url:
            try:
                html = self._client.fetch_html(url)
            except RecipeFetchError as exc:
                raise HTTPException(
                    status_code=502, detail=f"Couldn't fetch that page: {exc}"
                ) from exc
            for block in _extract_ld_json_blocks(html):
                recipes = _find_ld_recipes(block)
                if recipes:
                    return _draft_from_ld_recipe(recipes[0], url)
            # No structured data — fall back to reading the stripped text.
            draft = _parse_free_text(strip_html(html), url)
            draft.warnings = list(set(draft.warnings + ["no_structured_data"]))
            return draft

        return _parse_free_text(text)


def get_recipe_scrape_client() -> RecipeScrapeClient:
    return RecipeScrapeClient()


def get_recipe_import_service(
    client: RecipeScrapeClient = Depends(get_recipe_scrape_client),
) -> RecipeImportService:
    return RecipeImportService(client)
