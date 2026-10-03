# 03 — Pricing & Configurator

## Model

**Build-your-own plan: Core (by size) + modules + usage.** The owner pays only for what they
select and can add or remove modules anytime. Positioned as fair and transparent
("pay for what you use"), not as "cheap".

All prices below are **placeholders** from spec v1 for modelling — not a price list.

## Components

| Component | Key | Pricing | Notes |
|---|---|---|---|
| Core | `core` | By active clients tier: ≤100 ₪99 · ≤300 ₪149 · ≤1,000 ₪249 · 1,000+ custom | Required; this is the price floor |
| Client app | `client_app` | +₪49 | Branded experience in the shared app |
| CRM & leads | `crm` | +₪39 | |
| Advanced analytics | `analytics_pro` | +₪39 | Basic KPIs are in Core |
| AI Basic | `ai_basic` | +₪49 | Q&A + included AI credits |
| AI Pro | `ai_pro` | +₪119 | Actions + more credits |
| Finance agent | `agent_finance` | +₪69 | Requires `ai_basic` or `ai_pro` |
| Marketing agent | `agent_marketing` | +₪69 | Requires `ai_*` and `crm` |
| WhatsApp | `whatsapp` | Base + usage | Metered per message/conversation |
| Extra location | `location` | Per location | |
| Extra staff seats | `staff_seat` | Per seat above included | |

## Bundles (presets)

Per vertical, the questionnaire recommends one of ~3 presets (e.g. *Starter*, *Growing*,
*AI-powered*). The owner can then customize. Presets are just saved selections — billing
always works on the underlying line items.

## Usage meters

| Meter | Unit | Included in | Overage |
|---|---|---|---|
| `ai_credits` | Abstract credit (maps to model cost) | AI tiers | Per credit pack |
| `whatsapp_messages` | Message / conversation | WhatsApp module | Pass-through + margin |
| `email_sends` | Email | Core (generous) | Rare |
| `sms_sends` | SMS | — | Pass-through + margin |
| `storage_gb` | GB | Core (e.g. 5 GB) | Per GB |

Owners see credits, never tokens. Soft limit warnings at 80% and 100%; hard stop only for paid
overage that the owner has not enabled.

## Billing rules

- **Upgrade / add module:** immediate, prorated.
- **Downgrade / remove module:** at end of the current billing period.
- **Price versions:** prices are versioned; existing tenants keep their price version
  (grandfathering) until explicitly migrated.
- **Dependencies:** enforced by the configurator and the API (e.g. agents require an AI tier).
- **Annual plan:** discount for 12-month commitment.
- **Trial:** time-limited trial of the selected configuration.
- Platform billing (us → business) is completely separate from business payments (business → client).

## Margin guardrails

- Track actual cost per tenant (infra share, AI, messaging, payments) from day one.
- Each metered module must have positive gross margin at its included allowance.
- Model routing: cheap model for simple tasks, strong model only when needed.

## Second revenue stream (to explore)

Revenue share with a payment provider on processed volume — common in vertical SaaS and a way to
keep subscription prices low.
