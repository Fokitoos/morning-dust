"""Pizza dough calculator.

Dough math follows The Pizza Craft's Ooni recipe: 60% hydration, 2.5% salt,
0.3% instant yeast for a same-day bake or 0.15% for a cold ferment, sized to
250 g balls for 12" pizzas (Ooni Karu 12 and similar home ovens).
https://thepizzacraft.com/dough-and-fermentation/ooni-pizza-dough-recipe/

Lievito madre essiccato (Molino Rossetto) is dosed at the manufacturer's own
instruction — 35 g per 500 g flour (7%) — with the longer room-temperature
rise that a natural leaven needs instead of a fridge ferment.
https://www.molinorossetto.com/en/yeasts-thickeners-other/1727-lievito-madre-essiccato.html

All the tunable numbers live at the top of this file — change them here, not
in the compiled frontend.
"""

from app.schemas.pizza import PizzaCalcRequest, PizzaCalcResponse, PizzaIngredient

BALL_GRAMS = 250  # one 12" pizza
HYDRATION = 0.60  # water as a fraction of flour
SALT_PCT = 0.025  # salt as a fraction of flour
YEAST_PCT_SAME_DAY = 0.003  # instant dry yeast, same-day bake (<= 6h rest)
YEAST_PCT_COLD_FERMENT = 0.0015  # instant dry yeast, fridge rest (> 6h)
YEAST_PCT_LMR = 0.07  # lievito madre essiccato, Molino Rossetto's own dosage

BAKE_NOTE = (
    "Ooni Karu 12: preheat until the stone reads 400°C+ in the centre "
    "(infrared thermometer), and drop the flame to low just before launching. "
    "Launch off a semolina-dusted peel, turn the pizza 90° every 20–30 "
    "seconds, and pull it at 60–90 seconds when the crust shows leopard spots."
)
SOURCE_NOTE = (
    "Dough math: The Pizza Craft’s Ooni recipe (60% hydration, 2.5% salt). "
    "Lievito madre dosage: Molino Rossetto, 35 g per 500 g flour."
)


def _hours_label(lo: int, hi: int) -> str:
    return f"{lo} h" if lo == hi else f"{lo}–{hi} h"


def _ball_step(pizzas: int) -> str:
    unit = "ball" if pizzas == 1 else "balls"
    return f"Divide into {pizzas} {unit} of ~{BALL_GRAMS} g each and shape them tight."


def _schedule(pizzas: int, hours_min: int, hours_max: int, lmr: bool) -> tuple[str, list[str]]:
    hours = _hours_label(hours_min, hours_max)
    ball_step = _ball_step(pizzas)

    if lmr:
        label = f"Natural leavening — {hours} at room temperature"
        steps = [
            "Dissolve the lievito madre in the lukewarm water and let it sit "
            "10–15 minutes until it turns foamy and creamy.",
            "Add the flour, then the salt, and mix to a shaggy mass. Cover and rest 15 minutes.",
            "Knead 8–10 minutes until smooth and elastic; shape into one ball, cover.",
            f"Bulk rise {hours} in a warm, draft-free spot until well risen (roughly doubled).",
            f"{ball_step} Proof the balls, covered, 1–2 hours at room temperature.",
            "Stretch on semolina, top lightly, and launch.",
        ]
        return label, steps

    if hours_max <= 6:
        label = f"Same-day bake — {hours} total"
        steps = [
            "Combine the water, yeast and salt in a bowl; stir until dissolved.",
            "Add the flour and stir to a shaggy mass. Cover and rest 15 minutes (autolyse).",
            "Knead 8–10 minutes until smooth and elastic.",
            "Bulk ferment 1.5–2 hours at room temperature until roughly doubled.",
            f"{ball_step} Secondary rise 30–60 minutes, covered.",
            "Stretch on semolina, top lightly, and launch.",
        ]
        return label, steps

    if hours_max <= 18:
        label = f"Overnight cold ferment — {hours} in the fridge"
    else:
        label = (
            f"Classic cold ferment — {hours} in the fridge "
            "(sweet spot 36 h, don’t pass 72 h)"
        )
    steps = [
        "Combine the water, yeast and salt in a bowl; stir until dissolved.",
        "Add the flour and stir to a shaggy mass. Cover and rest 15 minutes (autolyse).",
        "Knead 8–10 minutes until smooth and elastic.",
        "Bulk ferment 30 minutes at room temperature.",
        f"{ball_step} Put them in a covered tray and cold ferment {hours} in the fridge.",
        "Take the tray out 2–4 hours before baking so the balls warm up and finish proofing.",
        "Stretch on semolina, top lightly, and launch.",
    ]
    return label, steps


def calculate(req: PizzaCalcRequest) -> PizzaCalcResponse:
    hours_min = min(req.hours_min, req.hours_max)
    hours_max = max(req.hours_min, req.hours_max)
    lmr = req.yeast == "lmr"

    dough_grams = req.pizzas * BALL_GRAMS
    yeast_pct = YEAST_PCT_LMR if lmr else (
        YEAST_PCT_SAME_DAY if hours_max <= 6 else YEAST_PCT_COLD_FERMENT
    )
    flour = dough_grams / (1 + HYDRATION + SALT_PCT + yeast_pct)

    yeast_label = "Lievito madre essiccato" if lmr else "Instant dry yeast"
    yeast_amount = f"{round(flour * yeast_pct)} g" if lmr else f"{flour * yeast_pct:.1f} g"

    ingredients = [
        PizzaIngredient(label='"00" flour', amount=f"{round(flour)} g"),
        PizzaIngredient(label="Water, lukewarm", amount=f"{round(flour * HYDRATION)} g"),
        PizzaIngredient(label="Fine sea salt", amount=f"{flour * SALT_PCT:.1f} g"),
        PizzaIngredient(label=yeast_label, amount=yeast_amount),
    ]

    schedule_label, steps = _schedule(req.pizzas, hours_min, hours_max, lmr)
    unit = "pizza" if req.pizzas == 1 else "pizzas"

    return PizzaCalcResponse(
        summary=f"{req.pizzas} {unit} × {BALL_GRAMS} g balls · {dough_grams} g dough · 60% hydration",
        ingredients=ingredients,
        schedule_label=schedule_label,
        steps=steps,
        bake_note=BAKE_NOTE,
        source_note=SOURCE_NOTE,
    )
