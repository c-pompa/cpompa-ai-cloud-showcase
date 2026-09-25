# cpompa-ai-cloud — showcase

A multi-tenant AI agent hosting platform: an OpenAI-compatible, unit-metered inference
endpoint, subscription billing, API-key management, and hosted agents — running on
owned hardware. This repository is a **curated public showcase** of the private
control-plane repo; it contains no secrets and no tenant data.

## What it does

- **`/v1/chat/completions`** — OpenAI-compatible endpoint, metered in *units*.
  1 unit = 2k input + 256 output tokens on a small model — the measured serving cost
  of one chat turn. Rates are generated from measured hardware speed
  (`excerpts/derive_unit_rates.py`) and a CI test (`tests/test_units_meter.py`)
  fails if the published table drifts from what the meter charges.
- **Plans & billing** — single-tier pricing (ADR-0005): $1/mo Starter with a 500-unit
  free grant; usage beyond the grant via top-ups at $1 = 2,000 units. Stripe
  (test mode) webhooks drive entitlements; unknown prices fail closed.
- **Hosted agents** — per-seat cloud agents with tools, streaming SSE turns, and logs.
- **Fleet** — node pairing (mTLS) for bring-your-own-hardware; model routing across
  quantized local serving with mixture-of-agents pooling.

## Highlights in this repo

| file | what it shows |
|---|---|
| [`docs/adr-0005-single-tier-pricing.md`](docs/adr-0005-single-tier-pricing.md) | the unit economics: measured costs, margin across request shapes, why usage top-ups |
| [`docs/diagram-system-context.md`](docs/diagram-system-context.md) | system-context C4 diagram (mermaid) |
| [`ci-pipeline.yml`](ci-pipeline.yml) | the full GitLab CI pipeline: ruff, pytest, gitleaks secrets-scan, checkov config-scan, pip-audit, trivy image-scan, SHA-pinned deploys |
| [`excerpts/derive_unit_rates.py`](excerpts/derive_unit_rates.py) | rate derivation from measured hardware speeds — the meter follows cost |

## Why units instead of requests?

A chat user makes one call per message; an agent task makes 30–100 LLM requests for
one thing the user did once. Metering the *call* charges customers for our
implementation detail. The unit is the honest atom: it maps to what a request
actually costs, weighted by model size and context — so margin is near-flat
(~71–75%) across every request shape and model mix is a priced decision, never a
silent loss.

## Stack

FastAPI · PostgreSQL (+ alembic) · Redis · Docker (non-root, SHA-pinned deploys) ·
Stripe (test mode) · GitLab CI with a four-stage security gate.
