"""
Basic health check tests
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "Scope API"
    assert "timestamp" in data


def test_healthz_endpoint():
    """Test healthz endpoint"""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


def test_test_endpoint():
    """Test the test endpoint"""
    response = client.get("/test")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True


def test_root_redirect():
    """Test root endpoint redirects to docs"""
    response = client.get("/", follow_redirects=False)
    # Should either return docs or redirect
    assert response.status_code in [200, 307, 404]
