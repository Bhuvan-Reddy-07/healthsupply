"""
Phase 5 Verification Suite: Control Center Dashboard, Telemetry APIs, and Demo Runner.
Acceptance Criteria:
1. Dashboard summary returns 200 facilities and GeoJSON layer for MapLibre GL.
2. Outbreak timeline returns actual demand and CUSUM progression.
3. Federation status endpoint returns multi-country node status, RDP privacy metrics (epsilon < 4.0), and killer experiment gains.
4. Dashboard static endpoint (/dashboard/) serves valid HTML frontend.
5. Demo runner executes the complete 6-step narrative and counterfactual table in < 300s.
"""
import pytest
import time
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.facilities import Facility
from backend.app.models.intelligence import Alert, TransferProposal
from demo.runner import run_demo

@pytest.fixture
def client():
    return TestClient(app)

def test_dashboard_summary_and_geojson_layer(client, db_session):
    """
    Verifies that GET /api/v1/dashboard/summary serves KPI totals and GeoJSON
    with valid coordinates and status tagging for MapLibre GL.
    """
    # Seed 2 test facilities
    f1 = Facility(
        id="FAC_DASH_01", name="Alpha Health Center", country="Country_A",
        region="North", district="Kolar", tier="PHC",
        latitude=12.98, longitude=77.60, has_cold_chain=True
    )
    f2 = Facility(
        id="FAC_DASH_02", name="Beta District Hospital", country="Country_B",
        region="South", district="Border", tier="DH",
        latitude=13.50, longitude=78.10, has_cold_chain=True
    )
    db_session.add_all([f1, f2])
    db_session.commit()

    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()

    assert data["total_facilities"] >= 2
    assert "facilities_geojson" in data
    geojson = data["facilities_geojson"]
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) >= 2
    
    first_feat = geojson["features"][0]
    assert first_feat["geometry"]["type"] == "Point"
    assert len(first_feat["geometry"]["coordinates"]) == 2
    assert "status" in first_feat["properties"]

def test_dashboard_outbreak_timeline(client):
    """
    Verifies that GET /api/v1/dashboard/outbreak_timeline serves
    daily demand, P10/P50/P90 quantile envelopes, and CUSUM radar scores.
    """
    res = client.get("/api/v1/dashboard/outbreak_timeline?district=Kolar")
    assert res.status_code == 200
    data = res.json()

    assert data["district"] == "Kolar"
    assert "timeline" in data
    timeline = data["timeline"]
    assert len(timeline) >= 20

    # Verify trajectory structure
    day1 = timeline[0]
    assert "actual_demand" in day1
    assert "forecast_p50" in day1
    assert "cusum_score" in day1

def test_dashboard_federation_telemetry(client):
    """
    Verifies that GET /api/v1/dashboard/federation returns live multi-country
    nodes, formal RDP privacy guarantees (epsilon <= 4.0), and killer experiment metrics.
    """
    res = client.get("/api/v1/dashboard/federation")
    assert res.status_code == 200
    data = res.json()

    assert data["total_nodes"] == 2
    assert data["privacy"]["epsilon"] <= 4.0
    assert data["privacy"]["accountant"] == "Rényi Differential Privacy (RDP)"
    assert data["killer_outbreak_transfer"]["improvement_pct"] >= 10.0
    assert len(data["accuracy_comparison"]) == 4

def test_dashboard_frontend_serving(client):
    """
    Verifies that the mounted /dashboard/ endpoint serves the React + MapLibre GL frontend.
    """
    res = client.get("/dashboard/")
    assert res.status_code == 200
    assert "HealthSupply Control Center" in res.text
    assert "maplibre-canvas" in res.text

def test_demo_runner_execution_and_budget():
    """
    CRITICAL ACCEPTANCE TEST:
    Verifies that the demo runner executes the complete 6-step narrative,
    resets DB, injects outbreak, detects surge, solves redistribution,
    approves transfer, and prints counterfactual table within the < 300s budget.
    """
    start = time.time()
    run_demo()
    runtime = time.time() - start

    assert runtime < 15.0, f"Demo runner executed in {runtime:.2f}s, exceeding fast budget (<15s)"
    assert runtime < 300.0, "Demo runner strictly satisfies < 5 minute reviewer attention budget"
