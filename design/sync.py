#!/usr/bin/env python3
"""Sync the design source in and out of the compiled dashboard.

`app/static/index.html` is a self-extracting bundle: the real UI source (the
<x-dc> markup plus the component script) is stored inside it, JSON-encoded, in
a <script type="__bundler/template"> tag. Hand-editing that encoded blob is
miserable and easy to corrupt, so this script moves the source in and out of
it:

    python design/sync.py extract   # bundle  -> design/morning-dust.dc.html
    python design/sync.py inject    # design/morning-dust.dc.html -> bundle

Typical loop: `extract` once, edit the .dc.html (or paste in a fresh export
from the Claude Design project), then `inject` and commit both files.

Only the <x-dc>...</script> region is exchanged. The bundle's surrounding
shell, asset manifest and font/runtime UUID placeholders are left untouched,
so the compiled file keeps working exactly as before.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "app" / "static" / "index.html"
SOURCE = ROOT / "design" / "morning-dust.dc.html"

TEMPLATE_TAG = re.compile(r'(<script type="__bundler/template">)(.*?)(</script>)', re.S)

HEADER = """<!--
  morning-dust design source, recovered from app/static/index.html.

  This is the <x-dc> markup + component script exactly as it exists in the
  deployed dashboard. Paste it into the Claude Design project ("hearth") to
  bring that project back in sync after code-side edits.

  Six bare UUID references remain below (one <script src> for the Design
  runtime, and four woff2 font files for Caprasimo/Figtree). Those are
  placeholders the bundler substitutes at compile time; they are NOT part of
  the authored source and are not resolvable outside the bundle.

  Edit this file, then run `python design/sync.py inject` to write it back
  into the compiled bundle. Do not hand-edit the bundle.
-->
"""


def _template() -> tuple[str, re.Match]:
    """The bundle text and the match around its JSON-encoded template."""
    bundle = BUNDLE.read_text(encoding="utf-8")
    match = TEMPLATE_TAG.search(bundle)
    if match is None:
        sys.exit(f"error: no __bundler/template tag found in {BUNDLE}")
    return bundle, match


def _source_span(text: str) -> tuple[int, int]:
    """Bounds of the authored <x-dc>...</script> region inside `text`.

    The opening tag is matched at the start of a line so that a prose mention
    of it inside the header comment cannot be picked up as the real start.
    """
    open_tag = re.search(r"^<x-dc>", text, re.M)
    if open_tag is None or "</script>" not in text:
        sys.exit("error: could not locate the <x-dc> source region")
    return open_tag.start(), text.rindex("</script>") + len("</script>")


def extract() -> None:
    _, match = _template()
    template = json.loads(match.group(2))
    start, end = _source_span(template)
    SOURCE.write_text(HEADER + template[start:end] + "\n", encoding="utf-8")
    print(f"extracted {end - start} chars -> {SOURCE.relative_to(ROOT)}")


def inject() -> None:
    bundle, match = _template()
    template = json.loads(match.group(2))
    start, end = _source_span(template)

    source = SOURCE.read_text(encoding="utf-8")
    # Drop the header comment; keep only the authored region.
    src_start, src_end = _source_span(source)
    updated = template[:start] + source[src_start:src_end] + template[end:]

    if updated == template:
        print("no changes — bundle already matches the design source")
        return

    # Escape "</" so the encoded string can never terminate the <script> tag.
    encoded = json.dumps(updated, ensure_ascii=False).replace("</", "<\\u002F")
    if json.loads(encoded) != updated:
        sys.exit("error: re-encoding the template did not round-trip; aborting")

    BUNDLE.write_text(bundle[: match.start(2)] + encoded + bundle[match.end(2) :], encoding="utf-8")
    print(f"injected {src_end - src_start} chars -> {BUNDLE.relative_to(ROOT)}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "extract":
        extract()
    elif action == "inject":
        inject()
    else:
        sys.exit(__doc__)
