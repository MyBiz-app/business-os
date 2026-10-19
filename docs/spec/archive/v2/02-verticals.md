# 02 — Verticals

## Principle

The core models generic concepts. A **vertical pack** is configuration layered on top — never
`if vertical == "barbershop"` branches in business logic.

| Core concept | Meaning |
|---|---|
| Client | Anyone the business serves |
| Service | Something the business offers (class type, haircut, treatment) |
| Session | A scheduled occurrence of a service with a capacity (1 = appointment, N = class) |
| Resource | Room, chair, equipment |
| Plan | Something a client buys: recurring membership, punch card, single visit, package |
| Entitlement | A client's purchased plan, with credits / validity / freeze state |

## What a vertical pack contains

```yaml
key: fitness_studio
terminology:            # translation keys overridden per vertical
  client: { en: Member, he: מתאמן }
  session: { en: Class, he: שיעור }
  staff: { en: Trainer, he: מאמן }
default_services: [...]  # e.g. Pilates Reformer, HIIT, Personal Training
default_plans: [...]     # e.g. Monthly unlimited, 10-class card
default_roles: [...]
custom_fields: [...]     # e.g. injuries, goals
required_forms: [health_declaration]
recommended_modules: [core, client_app, crm]
dashboard_kpis: [occupancy, active_members, churn, no_show_rate]
onboarding_questions: [...]
```

## Planned packs

| Pack | Booking style | Notable needs | Phase |
|---|---|---|---|
| Fitness studio / gym / pilates | Classes (N) + PT (1) | Health declaration, punch cards, freeze, waitlist | Prototype |
| Barbershop / salon | Appointments (1) per staff | Staff availability, service duration, deposits, no-show fee | After MVP |
| Private tutor / coach | Appointments + packages | Packages, online sessions | Later |
| Private clinic (non-medical first, e.g. cosmetics) | Appointments | Intake forms | Later |
| Medical clinic | Appointments | Medical records, stricter privacy | Deferred |
