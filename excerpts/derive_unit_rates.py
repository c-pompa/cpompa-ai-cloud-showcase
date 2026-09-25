#!/usr/bin/env python3
"""Derive the unit rate table from measured model speeds.

`ADR-0003` decides two things this script exists to serve:

* a **unit is a fixed retail quantum** -- 2,000 input + 256 output tokens on the
  anchor (small) model -- so the anchor shape must come out at exactly 1 unit;
* **rates go stale whenever the serving node changes**, and re-deriving them has to
  be part of the release rather than a follow-up.

So the table is *derived*, not typed: you measure each model's prefill and decode
speed (the same way `scripts/measure_batching.py` does), feed them in here, and paste
the result into `UNIT_RATES`. A rate table that cannot be regenerated from a
measurement is a rate table nobody will trust six months from now.

    python3 scripts/derive_unit_rates.py --speeds speeds.json
    python3 scripts/derive_unit_rates.py --speeds speeds.json --check-published

`speeds.json`:
    {"anchor": "small",
     "models": {"small": {"prefill_tok_s": 1600, "decode_tok_s": 89.7},
                "27B":   {"prefill_tok_s": 350,  "decode_tok_s": 11.2}}}

Why speeds and not dollars: dollars per token embed a GPU price that changes
independently of the model, so a re-measure after a node change would have to
re-derive the price too. Seconds per token is the measurement; the anchor
normalisation removes the need for any dollar figure at all.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

#: The anchor shape. `ADR-0003` §Decision-1 and business-plan §3.7 fix these two
#: numbers, and "1 unit" means this shape on the anchor model -- by construction.
BASE_INPUT_TOKENS = 2_000
BASE_OUTPUT_TOKENS = 256

#: The request shapes we price, with the measured cost of each (business-plan §3.7).
#: This is the *data* behind the published table: costs are measured inputs, the unit
#: counts are derived from the rates, and the table in the business plan is rendered
#: from both -- so the doc cannot disagree with the meter without a test failing.
SHAPES = [
    {"label": "small chat (600 / 250)", "model": "small", "prompt": 600, "output": 250,
     "cost_micro": 0.126},
    {"label": "small coding (8k / 800)", "model": "small", "prompt": 8_000, "output": 800,
     "cost_micro": 0.571},
    {"label": "27B chat (600 / 250)", "model": "27B", "prompt": 600, "output": 250,
     "cost_micro": 0.829},
    {"label": "27B coding (8k / 800)", "model": "27B", "prompt": 8_000, "output": 800,
     "cost_micro": 3.346},
    {"label": "27B agent (30k / 2k)", "model": "27B", "prompt": 30_000, "output": 2_000,
     "cost_micro": 9.505},
]

#: Markers around the generated table in the published document. Generated prose
#: needs a boundary that is unambiguous to a machine; without it a checker has to
#: guess which pipe-table in a 2,000-line document is the one it owns.
BEGIN_MARKER = "<!-- BEGIN GENERATED: unit table (scripts/derive_unit_rates.py) -->"
END_MARKER = "<!-- END GENERATED: unit table -->"


def render_table(table: dict, shapes: list[dict] | None = None) -> str:
    """The published unit table, rendered from the rates.

    Single source of truth: the rates come from a measurement, the shapes carry the
    measured cost of each request, and this renders both into the document. A table
    typed by hand into prose is a second source of truth, and two sources of truth
    for the same number is how a plan quotes 5 units for a request the meter charges
    6 for.
    """
    shapes = SHAPES if shapes is None else shapes
    lines = [
        BEGIN_MARKER,
        "| request | our cost, 1 stream | units charged |",
        "|---|---|---|",
    ]
    for shape in shapes:
        units = units_for(table, shape["model"], shape["prompt"], shape["output"])
        lines.append(f"| {shape['label']} | {shape['cost_micro']:.3f} m$ | **{units}** |")
    lines.append(END_MARKER)
    return "\n".join(lines)


def _generated_block(text: str) -> str | None:
    """The text between the markers, or None when they are absent."""
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1:
        return None
    return text[start : end + len(END_MARKER)]


def check_docs(table: dict, path: str) -> bool:
    """Does the document's generated block match the derivation?

    The gate. A rate re-derivation that does not update the published table fails
    here, which is the point: the alternative is a plan that quietly quotes numbers
    the meter does not use.
    """
    with open(path) as fh:
        text = fh.read()
    found = _generated_block(text)
    print(f"\nchecking {path}:")
    if found is None:
        print(f"  MISSING: no {BEGIN_MARKER} / {END_MARKER} block. The table cannot be")
        print("  verified, so it is free to drift -- restore the markers or generate it.")
        return False
    expected = render_table(table)
    if found.strip() == expected.strip():
        print("  matches the derivation")
        return True
    got_rows = [ln for ln in found.splitlines() if ln.startswith("| ") and " m$ " in ln]
    want_rows = [ln for ln in expected.splitlines() if ln.startswith("| ") and " m$ " in ln]
    print("  DRIFT — the document disagrees with the rates:")
    for got, want in zip(got_rows, want_rows):
        if got != want:
            print(f"    document: {got}")
            print(f"    derived : {want}")
    print("  Regenerate with: python3 scripts/derive_unit_rates.py --speeds <file> --emit-markdown")
    return False


def derive(speeds: dict) -> dict[str, dict[str, float]]:
    """Speeds -> ``{model: {"in": units/token, "out": units/token}}``.

    GPU seconds per token, normalised by the anchor shape's own GPU seconds. The
    anchor therefore lands on exactly 1.000 unit by construction, whatever the
    measured speeds turn out to be -- which is what makes a re-measure a one-line
    config change rather than a re-fit.
    """
    models = speeds.get("models") or {}
    anchor = speeds.get("anchor")
    if not anchor or anchor not in models:
        raise SystemExit(f"anchor model {anchor!r} is not in the measured models")
    anchor = str(anchor)

    def seconds_per_unit(model: str) -> tuple[float, float]:
        m = models[model]
        prefill, decode = float(m["prefill_tok_s"]), float(m["decode_tok_s"])
        if prefill <= 0 or decode <= 0:
            raise SystemExit(f"{model}: speeds must be positive")
        return 1.0 / prefill, 1.0 / decode

    a_in, a_out = seconds_per_unit(anchor)
    base_seconds = BASE_INPUT_TOKENS * a_in + BASE_OUTPUT_TOKENS * a_out

    table = {}
    for model in models:
        in_s, out_s = seconds_per_unit(model)
        table[model] = {"in": in_s / base_seconds, "out": out_s / base_seconds}
    return table


def units_for(table: dict, model: str, prompt: int, completion: int) -> int:
    return math.ceil(prompt * table[model]["in"] + completion * table[model]["out"])


#: The checked-in measurements the default table is derived from. Keeping them in the
#: repo is what makes the whole chain reproducible: speeds -> rates -> the published
#: table, every step regenerable, with a test that fails when the last one is stale.
DEFAULT_SPEEDS = pathlib.Path(__file__).resolve().parent / "unit_speeds.json"

#: The document whose generated unit table is gated against the derivation.
DEFAULT_DOC = pathlib.Path(__file__).resolve().parent.parent / "docs" / "business-plan.md"


def load_speeds(path: pathlib.Path) -> dict:
    with open(path) as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Derive the unit rate table from measured model speeds."
    )
    ap.add_argument("--speeds", default=str(DEFAULT_SPEEDS),
                    help="JSON file of measured speeds (default: the checked-in measurements)")
    ap.add_argument("--emit-markdown", action="store_true",
                    help="print the generated table for the published document")
    ap.add_argument("--check-docs", nargs="?", const=str(DEFAULT_DOC), default=None,
                    help="fail if the document's generated table drifts from the rates")
    ap.add_argument("--unit-price", type=float, default=0.000169,
                    help="$ cost of one unit, for the sanity print only")
    args = ap.parse_args()

    speeds = load_speeds(pathlib.Path(args.speeds))
    table = derive(speeds)

    anchor = speeds["anchor"]
    a = table[anchor]
    base_units = (BASE_INPUT_TOKENS * a["in"] + BASE_OUTPUT_TOKENS * a["out"])
    print(f"anchor: {anchor}  -> base shape = {base_units:.6f} units (must be 1.000000)")
    if abs(base_units - 1.0) > 1e-9:
        print("  ERROR: normalisation is wrong", file=sys.stderr)
        return 1

    if args.emit_markdown:
        # Just the block, so it can be pasted in or diffed against the document.
        print(render_table(table))
        return 0

    print(f"\nunit_rates (paste into UNIT_RATES):\n{json.dumps(table, indent=2)}")

    print("\nimplied rate ratios (measured speeds -> units per token):")
    for model, r in table.items():
        m = speeds["models"][model]
        print(f"  {model:<6} in:out = 1:{r['out'] / r['in']:.1f}x   "
              f"(measured prefill {m['prefill_tok_s']:g} / decode {m['decode_tok_s']:g} tok/s)")

    print("\npublished unit counts, rendered from these rates:")
    for shape in SHAPES:
        units = units_for(table, shape["model"], shape["prompt"], shape["output"])
        print(f"  {shape['label']:<24} {shape['cost_micro']:.3f} m$  ->  {units:>3} units")

    if args.check_docs:
        if not check_docs(table, args.check_docs):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
