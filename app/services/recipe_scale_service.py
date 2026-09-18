"""Scale a recipe's ingredient lines to a different number of servings.

Ingredient lines are free text ("1 ½ cups flour", "2-3 cloves garlic",
"salt"), so scaling means: find the leading quantity (integer, decimal,
fraction, mixed number, unicode fraction, or a range of those), multiply it,
and write it back in the same style. Lines with no leading number are left
untouched and flagged, so the UI can show they didn't scale.
"""

import re
from fractions import Fraction

from app.schemas.nutrition import ScaledIngredient, ScaledRecipe

_UNICODE_FRACTIONS = {
    "¼": Fraction(1, 4), "½": Fraction(1, 2), "¾": Fraction(3, 4),
    "⅓": Fraction(1, 3), "⅔": Fraction(2, 3),
    "⅛": Fraction(1, 8), "⅜": Fraction(3, 8), "⅝": Fraction(5, 8), "⅞": Fraction(7, 8),
}
_FRACTION_GLYPHS = {v: k for k, v in _UNICODE_FRACTIONS.items()}

_NUM = r"(?:\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+[.,]\d+|\d+\s*[¼½¾⅓⅔⅛⅜⅝⅞]|\d+|[¼½¾⅓⅔⅛⅜⅝⅞])"
_LEADING_QTY = re.compile(
    rf"^\s*(?P<a>{_NUM})(?:\s*(?:-|–|to)\s*(?P<b>{_NUM}))?(?P<rest>.*)$", re.DOTALL
)
_SERVINGS_NUMBER = re.compile(r"\d+")


def parse_servings(text: str) -> int | None:
    """'4', '4 servings', 'Serves 4-6' -> 4. None when there's no number."""
    m = _SERVINGS_NUMBER.search(text or "")
    if not m:
        return None
    n = int(m.group())
    return n if n > 0 else None


def _to_fraction(token: str) -> Fraction:
    token = token.strip()
    if token in _UNICODE_FRACTIONS:
        return _UNICODE_FRACTIONS[token]
    if token[-1] in _UNICODE_FRACTIONS:  # "1½"
        return Fraction(int(token[:-1].strip())) + _UNICODE_FRACTIONS[token[-1]]
    parts = token.split()
    if len(parts) == 2 and "/" in parts[1]:  # "1 1/2"
        num, den = parts[1].split("/")
        return Fraction(int(parts[0])) + Fraction(int(num), int(den))
    if "/" in token:
        num, den = token.split("/")
        return Fraction(int(num), int(den))
    return Fraction(token.replace(",", "."))


def format_quantity(value: Fraction, decimal: bool = False) -> str:
    """Write a scaled amount the way a cook would: whole numbers stay whole,
    common fractions become glyphs (1½, ¾), anything else gets at most two
    decimals. `decimal` keeps the decimal style of an input like "1.5 l".
    """
    if value <= 0:
        return "0"
    whole = value.numerator // value.denominator
    frac = value - whole
    if frac == 0:
        return str(whole)
    if not decimal:
        for glyph_frac, glyph in _FRACTION_GLYPHS.items():
            if abs(frac - glyph_frac) <= Fraction(1, 50):
                return f"{whole}{glyph}" if whole else glyph
    rounded = round(float(value), 2 if value < 1 else 1)
    text = f"{rounded:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def scale_line(line: str, factor: Fraction) -> ScaledIngredient:
    m = _LEADING_QTY.match(line)
    if not m:
        return ScaledIngredient(text=line, scaled=False)
    decimal = any(c in m.group("a") for c in ".,")
    a = format_quantity(_to_fraction(m.group("a")) * factor, decimal)
    if m.group("b"):
        b = format_quantity(_to_fraction(m.group("b")) * factor, decimal)
        qty = f"{a}–{b}"
    else:
        qty = a
    rest = m.group("rest")
    if rest and not rest[0].isspace():
        rest = " " + rest
    return ScaledIngredient(text=(qty + rest).strip(), scaled=True)


def scale_ingredients(ingredients: list[str], base_servings: int, servings: int) -> ScaledRecipe:
    servings = max(1, servings)
    factor = Fraction(servings, base_servings)
    return ScaledRecipe(
        base_servings=base_servings,
        servings=servings,
        factor=float(factor),
        ingredients=[scale_line(line, factor) for line in ingredients],
    )
