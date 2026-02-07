"""
Pytest configuration and shared fixtures for SunCheck tests.
"""
import pytest
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def sample_market():
    """Sample market data for testing."""
    return {
        "id": "test-market-123",
        "question": "Will the highest temperature in Seattle be between 45-46°F on February 10?",
        "slug": "highest-temperature-in-seattle-on-february-10",
        "outcomes": ["Yes", "No"],
        "outcomePrices": ["0.15", "0.85"],
        "clobTokenIds": ["token-no-123", "token-yes-456"],
        "endDate": "2026-02-10T23:59:59Z"
    }


@pytest.fixture
def sample_signal():
    """Sample trading signal for testing."""
    return {
        "market_id": "test-market-123",
        "question": "Will the highest temperature in Seattle be between 45-46°F on February 10?",
        "city": "seattle",
        "true_prob": 0.35,
        "market_prob": 0.15,
        "edge": 0.20,
        "action": "BUY Yes",
        "outcome": "Yes",
        "source_probs": {"OpenMeteo": 0.35, "NWS": 0.33},
        "om_val": 45.5,
        "target_int": (45, 46),
        "legacy_pass": True
    }


@pytest.fixture
def sample_position():
    """Sample position data for testing."""
    return {
        "market_id": "test-market-123",
        "question": "Will the highest temperature in Seattle be between 45-46°F on February 10?",
        "city": "Seattle",
        "outcome": "Yes",
        "price": 0.15,
        "shares": 133.33,
        "amount_invested": 20.0,
        "edge": 0.20,
        "market_prob": 0.15,
        "true_prob": 0.35,
        "timestamp": "2026-02-07T10:00:00"
    }


@pytest.fixture
def mock_weather_data():
    """Mock weather forecast data."""
    return {
        "temp": 45.5,
        "precip": 0.0
    }
