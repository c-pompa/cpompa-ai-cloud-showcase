# ADR-0005: Single-tier pricing — $1/month plus usage top-ups

**Status:** Accepted — 2026-09-19
**Supersedes:** the $1–$5 tier ladder in `tiers.py` (business plan §3.7 item 3 as it stood)

## Context

The catalog shipped as a five-tier ladder ($1–$5/mo) with request allowances
(10k–250k) and a units table deliberately *not* emitted — units were metered and
priced but capped nowhere, so no deploy could start refusing traffic silently
(the 2026-09-17 decision recorded in `tiers.py`).

That shape had two problems:

1. **The request meter is the wrong currency.** Business plan §3.1 measured the
   request allowance as up to 805× underwater at the envelope our own agent
   runtime generates; the units ladder (§3.7) was built to replace it. With
   requests uncapped and units uncapped, the paid plans sold nothing bounded.
2. **Five tiers is a menu nobody asked for.** The product is early and the
   price-sensitive entry point is what matters; a ladder of near-identical
   tiers adds Stripe provisioning surface and console chrome without adding a
   decision the customer needs to make.

## Decision

1. **One paid plan.** `TIERS` in `src/cpompa_cloud/tiers.py` holds a single
   tier — Starter, **$1/month** (key `tier1` unchanged, so the existing Stripe
   price at the same amount is reused and the lookup key keeps resolving).
   No request cap: `monthly_requests: None` — with usage metered in units and
   extensible by purchase, a request cap would bind paying customers before
   their units budget does. Units are the only meter that matters on the sold
   plan.
2. **A $0.25 free-usage grant for every user.** `FREE_GRANT_CENTS = 25`,
   `FREE_GRANT_UNITS = 500` at the published rate ($1 = 2,000 units). The
   grant binds on **all** plans — `FREE_PLAN` and the paid tier both declare
   `monthly_units: 500` — and `tier_entry` now emits the field, so
   `PLAN_BY_PRICE=auto` carries it and `resolve_plan` fails closed while
   `UNIT_RATES` is unset (both stacks already set it).
3. **Usage beyond the grant is bought, not bundled.** "Add more money for
   usage" is a set of one-time Checkout SKUs (`TOPUPS`: $1 = 2,000 units,
   $5 = 10,000 — derived from the same `UNITS_PER_DOLLAR`, so the margin is
   flat no matter how spend splits between plan and top-ups):
   - `POST /billing/topup` validates the amount against the catalog (an
     unlisted amount 400s; the units are never derived from the request),
     resolves a provisioned lookup-key price, and creates a
     `mode="payment"` session whose metadata carries the units.
   - On `checkout.session.completed` (paid), `grant_topup()` records the
     purchase in `unit_topups` (unique on the Checkout session id) and
     increments `quota_windows.units_granted` in the **same transaction** —
     a Stripe webhook replay returns `False` and grants nothing twice.
   - `reserve_units` guards against `plan.monthly_units + units_granted`, so
     a top-up is *this month's* usage budget and resets with the window. Not
     a stored balance; a stored balance is a different product with
     expiration accounting we have not decided.
   - The $2–$5 Stripe prices are deactivated at rollout; subscription rows
     still holding them are migrated before deploy (no customer 402s for a
     plan that no longer exists).

## Consequences

- The old policy tests asserting "monthly_units must not bind" are inverted
  (`test_plan_auto.py`, `test_provision_prices.py`); the fail-closed direction
  on `UNIT_RATES` is now the asserted guarantee.
- Display surfaces (`/account`, `/usage`, operator console quotas) report the
  effective budget — plan allowance **plus** granted units — so a topped-up
  customer is never told they are out of units while requests still succeed.
- Annual billing (§3.7 item 6) is unchanged and still recommended; on a $1
  plan the Stripe fee ratio is the dominant cost line, as §3.2 measured.
- A future stored-balance top-up (non-expiring credits) would be an
  additive migration on top of `unit_topups`; nothing here depends on the
  month-scoped semantics except `reserve_units`'s window predicate.
