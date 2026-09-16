from app.providers.crime_precincts import CrimePrecinctProvider

# Real Cape Town landmarks, used to prove the committed precinct geometry
# actually resolves locations rather than merely parsing.
CBD = (-33.9249, 18.4241)            # Cape Town CBD
KHAYELITSHA = (-34.0363, 18.6774)    # Khayelitsha
SEA_POINT = (-33.9145, 18.3861)      # Sea Point promenade
LONDON = (51.5072, -0.1276)          # far outside the dataset


def test_dataset_is_present_and_described():
    provider = CrimePrecinctProvider()
    assert provider.available
    meta = provider.metadata
    assert meta["municipality"] == "CPT"
    assert meta["precinct_count"] >= 50
    assert meta["window"]  # e.g. "2024-10 to 2025-09"
    assert "Carjacking" in meta["categories"]


def test_known_locations_resolve_to_the_right_precinct():
    provider = CrimePrecinctProvider()
    assert provider.precinct_at(*CBD)["name"] == "Cape Town Central"
    assert provider.precinct_at(*SEA_POINT)["name"] == "Sea Point"
    khayelitsha = provider.precinct_at(*KHAYELITSHA)
    assert khayelitsha is not None
    # The Khayelitsha area is covered by several adjacent precincts.
    assert "Khayelitsha" in khayelitsha["name"] or khayelitsha["name"] in {
        "Harare", "Makhaza", "Lingelethu-West",
    }


def test_points_outside_the_municipality_fall_back_to_the_previous_default():
    provider = CrimePrecinctProvider(default_baseline=8.0)
    assert provider.precinct_at(*LONDON) is None
    assert provider.baseline_at(*LONDON) == 8.0


def test_geometry_is_not_degenerate():
    """A simplification bug once collapsed every ring to two identical
    vertices while still producing a plausible-looking file."""
    provider = CrimePrecinctProvider()
    for precinct in provider.layer():
        vertices = sum(len(ring) for ring in precinct["rings"])
        assert vertices >= 4, f"{precinct['name']} has degenerate geometry"


def test_baselines_span_the_configured_range_without_clustering():
    provider = CrimePrecinctProvider()
    baselines = [p["crime_baseline"] for p in provider.layer()]
    assert min(baselines) >= 4.0 and max(baselines) <= 26.0
    # Percentile mapping should spread values, not pile them at one end.
    assert max(baselines) - min(baselines) > 10
    midband = [b for b in baselines if 10 < b < 20]
    assert len(midband) >= len(baselines) // 5


def test_route_summary_lists_precincts_worst_first():
    provider = CrimePrecinctProvider()
    geometry = [CBD, (-33.95, 18.47), (-33.98, 18.55), KHAYELITSHA]
    summary = provider.summarise_route(geometry)
    assert summary["precincts"], "route through Cape Town should match precincts"
    scores = [p["crime_baseline"] for p in summary["precincts"]]
    assert scores == sorted(scores, reverse=True)
    assert summary["worst"] == summary["precincts"][0]["name"]


def test_empty_route_and_missing_data_are_handled():
    provider = CrimePrecinctProvider()
    assert provider.summarise_route([])["precincts"] == []
    assert provider.summarise_route([])["worst"] is None
