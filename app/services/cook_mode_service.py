"""Cook mode: the recipe's steps with any durations spotted in the text,
so the UI can offer a one-tap timer ("simmer for 20 minutes" -> 20 min).

Only explicit durations count. A range ("10–15 minutes") becomes one timer
set to the longer end, labelled with the range so the cook knows to check
early. Numbers that aren't durations (350°F, 2 cloves) are ignored.
"""

import re

from app.schemas.cook_mode import CookStep, CookTimer

_UNIT_SECONDS = {
    "second": 1, "seconds": 1, "sec": 1, "secs": 1, "s": 1,
    "minute": 60, "minutes": 60, "min": 60, "mins": 60, "m": 60,
    "hour": 3600, "hours": 3600, "hr": 3600, "hrs": 3600, "h": 3600,
}
_NUM = r"(?:\d+\s*[½¼¾]|\d+(?:[.,]\d+)?|½|¼|¾|an?|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|forty|forty-five|fifty|sixty|ninety|half an?|quarter of an?)"
_UNIT = r"(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|[smh])"
_WORD_NUM = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "forty-five": 45, "fifty": 50, "sixty": 60, "ninety": 90,
    "half a": 0.5, "half an": 0.5, "quarter of a": 0.25, "quarter of an": 0.25,
    "½": 0.5, "¼": 0.25, "¾": 0.75,
}

# "1 hour 30 minutes" / "1h30" / "1 ½ hours" / "20 minutes" / "10–15 minutes" / "10 to 15 min"
_DURATION = re.compile(
    rf"(?<![\w.])(?P<a>{_NUM})(?:\s*(?:-|–|to|or)\s*(?P<b>{_NUM}))?\s*(?P<u>{_UNIT})\b"
    rf"(?:\s*(?:and\s*)?(?P<a2>\d+(?:[.,]\d+)?|½|¼|¾)\s*(?P<u2>{_UNIT})\b)?",
    re.IGNORECASE,
)


def _num(token: str) -> float:
    t = token.lower().strip()
    if t in _WORD_NUM:
        return _WORD_NUM[t]
    if t[-1] in "½¼¾":  # "1½"
        return float(t[:-1].strip() or 0) + _WORD_NUM[t[-1]]
    return float(t.replace(",", "."))


def _seconds(amount: float, unit: str) -> int:
    return round(amount * _UNIT_SECONDS[unit.lower()])


def _label(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} h")
    if m:
        parts.append(f"{m} min")
    if s and not h:
        parts.append(f"{s} s")
    return " ".join(parts) or "0 s"


def find_timers(text: str) -> list[CookTimer]:
    timers: list[CookTimer] = []
    for m in _DURATION.finditer(text):
        unit = m.group("u")
        # A bare letter unit ("5 m") is only trusted when glued to a digit,
        # otherwise "2 m" in "2 medium onions" would look like a timer.
        if len(unit) == 1 and not (m.group("a").isdigit() and len(m.group(0).split()) == 1):
            continue
        try:
            lo = _seconds(_num(m.group("a")), unit)
            hi = _seconds(_num(m.group("b")), unit) if m.group("b") else lo
        except (KeyError, ValueError):
            continue
        extra = 0
        if m.group("a2") and m.group("u2"):
            extra = _seconds(_num(m.group("a2")), m.group("u2"))
        lo, hi = lo + extra, hi + extra
        if hi <= 0 or hi > 24 * 3600:
            continue
        label = _label(hi) if lo == hi else f"{_label(lo)} – {_label(hi)}"
        timers.append(CookTimer(label=label, seconds=hi, phrase=m.group(0).strip()))
    return timers


def cook_steps(steps: list[str]) -> list[CookStep]:
    return [CookStep(index=i, text=t, timers=find_timers(t)) for i, t in enumerate(steps)]
