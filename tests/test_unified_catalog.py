from collections import Counter

from mordheim_combat_lab.candidate_catalog import (
    bands_for_categories, bands_for_category, load_bands,
)


def test_every_collection_is_loaded_through_the_same_runtime_contract():
    bands = load_bands()

    assert len(bands) == 83
    assert sum(len(band.profiles) for band in bands) == 540
    assert {collection for band in bands for collection in band.collections} == {
        "mordheimer", "trollheim",
    }
    assert all(band.categories for band in bands)
    assert all(band.sources for band in bands)


def test_single_category_selector_exposes_the_expected_catalogues():
    assert len(bands_for_category("all")) == 83
    assert len(bands_for_category("core")) == 6
    assert len(bands_for_category("1a")) == 7
    assert len(bands_for_category("1b")) == 23
    assert len(bands_for_category("1c")) == 13
    assert len(bands_for_category("trollheim")) == 34


def test_multiple_categories_return_their_union_without_duplicate_bands():
    selected = bands_for_categories(("core", "1a", "trollheim"))

    assert len(selected) == 47
    assert len({band.band_id for band in selected}) == 47
    assert {category for band in selected for category in band.categories} >= {
        "core", "1a", "trollheim",
    }


def test_overlapping_sources_are_explicit_variants_not_silent_overwrites():
    families = Counter(band.canonical_family for band in load_bands())
    variants = [band for band in load_bands() if families[band.canonical_family] > 1]

    assert len({band.canonical_family for band in variants}) == 21
    assert len(variants) == 42
    assert all(band.name.endswith(("— Mordheimer", "— Trollheim")) for band in variants)
    assert len({band.band_id for band in load_bands()}) == 83


def test_trollheim_profiles_keep_source_scoped_costs_and_legality():
    skaven = next(band for band in load_bands() if band.band_id == "trollheim-skaven")
    mordheimer = next(band for band in load_bands() if band.band_id == "skaven-clan-eshin")

    assert skaven.canonical_family == mordheimer.canonical_family
    assert skaven.collections == ("trollheim",)
    assert mordheimer.collections == ("mordheimer",)
    assert skaven.band_id != mordheimer.band_id
