import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add workspace to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server import app

client = TestClient(app)


def test_facility_siting_endpoint():
    payload = {
        "facility_type": "hospital",
        "k": 2,
        "max_response_minutes": 8.0,
        "city_id": "bengaluru"
    }
    response = client.post("/api/impact/facility-siting", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "run_id" in data
    assert "recommendations" in data
    assert len(data["recommendations"]) == 2
    assert "before" in data
    assert "after" in data
    assert "worst_case_min" in data["before"]
    assert "worst_case_min" in data["after"]
    
    # Assert optimized worst-case travel time is no worse than baseline
    before_worst = data["before"]["worst_case_min"]
    after_worst = data["after"]["worst_case_min"]
    assert after_worst <= before_worst


def test_backbone_cost_endpoint():
    payload = {
        "facility_type": "hospital",
        "city_id": "bengaluru"
    }
    response = client.post("/api/impact/backbone-cost", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "run_id" in data
    assert "mst_length_km" in data
    assert "mst_cost_inr" in data
    assert "full_mesh_cost_inr" in data
    assert "savings_pct" in data
    
    # Assert cost savings metrics make sense
    assert data["mst_cost_inr"] <= data["full_mesh_cost_inr"]
    assert data["savings_pct"] >= 0.0


def test_transit_equity_endpoint():
    response = client.post("/api/impact/transit-equity?city_id=bengaluru")
    assert response.status_code == 200
    
    data = response.json()
    assert "run_id" in data
    assert "underserved_wards" in data
    assert len(data["underserved_wards"]) > 0
    
    # Check fields in the first underserved ward
    ward = data["underserved_wards"][0]
    assert "ward_id" in ward
    assert "ward_name" in ward
    assert "population" in ward
    assert "stop_count" in ward
    assert "classification" in ward


def test_report_generation():
    # First run a siting query to get a run_id
    payload = {
        "facility_type": "hospital",
        "k": 1,
        "max_response_minutes": 8.0,
        "city_id": "bengaluru"
    }
    response_siting = client.post("/api/impact/facility-siting", json=payload)
    run_id = response_siting.json()["run_id"]
    
    # Get report
    response_report = client.get(f"/api/impact/report/{run_id}")
    assert response_report.status_code == 200
    assert "text/html" in response_report.headers["content-type"]
    assert "Applied Decision-Support Report" in response_report.text


def test_ward_specific_impact():
    # Test siting specifically inside Koramangala (ward_1)
    payload_siting = {
        "facility_type": "hospital",
        "k": 2,
        "max_response_minutes": 8.0,
        "city_id": "bengaluru",
        "ward_id": "ward_1"
    }
    response_siting = client.post("/api/impact/facility-siting", json=payload_siting)
    assert response_siting.status_code == 200
    assert response_siting.json()["after"]["worst_case_min"] <= response_siting.json()["before"]["worst_case_min"]

    # Test backbone cost specifically inside Koramangala (ward_1)
    payload_backbone = {
        "facility_type": "hospital",
        "city_id": "bengaluru",
        "ward_id": "ward_1"
    }
    response_backbone = client.post("/api/impact/backbone-cost", json=payload_backbone)
    assert response_backbone.status_code == 200
    assert response_backbone.json()["mst_cost_inr"] <= response_backbone.json()["full_mesh_cost_inr"]

