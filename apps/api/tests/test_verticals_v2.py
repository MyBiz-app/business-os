from app.catalog.verticals import CATALOG
from app.catalog.verticals_v2 import (
    BUSINESS_TYPES,
    DOMAINS,
    RESOURCE_TYPES,
    SERVICE_MODELS,
    default_activities,
    successors_of,
)


def test_catalog_v2_has_the_sizes_the_spec_describes() -> None:
    assert len(DOMAINS) == 12
    assert len(BUSINESS_TYPES) >= 70
    assert len(RESOURCE_TYPES) >= 25


def test_every_reference_resolves() -> None:
    for t in BUSINESS_TYPES.values():
        assert t["domain"] in DOMAINS or t.get("custom"), t["key"]
        for activity in t["activities"]:
            assert activity["model"] in SERVICE_MODELS, f"{t['key']}.{activity['key']}"
            if "resource_type" in activity:
                assert activity["resource_type"] in RESOURCE_TYPES, f"{t['key']}.{activity['key']}"
        for seed in t["resources"]:
            assert seed["type"] in RESOURCE_TYPES, t["key"]
        for other in t["common_combos"]:
            assert other in BUSINESS_TYPES, f"{t['key']} combo {other}"


def test_every_v1_key_has_a_successor() -> None:
    for key, pack in CATALOG.items():
        if pack.parent is None:
            assert any(key in d["replaces"] for d in DOMAINS.values()) or any(
                key in t.get("replaces", ()) for t in BUSINESS_TYPES.values()
            ), key
        else:
            assert successors_of(key), key
    assert {t["key"] for t in successors_of("padel_tennis")} == {"tennis_club", "padel_club"}


def test_tennis_club_starts_without_padel() -> None:
    assert [r["type"] for r in BUSINESS_TYPES["tennis_club"]["resources"]] == ["tennis_court"]
    assert {a["resource_type"] for a in default_activities("tennis_club")} == {"tennis_court"}
    assert BUSINESS_TYPES["padel_club"]["activities"][0]["duration_minutes"] == 90
