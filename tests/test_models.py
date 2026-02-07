"""
Tests for models module.
"""
import pytest
from models import Market, Signal, Position, ForecastResult, PositionStatus


class TestMarket:
    """Tests for Market dataclass."""
    
    def test_from_dict(self, sample_market):
        """Test creating Market from dict."""
        market = Market.from_dict(sample_market)
        
        assert market.id == "test-market-123"
        assert market.question.startswith("Will the highest")
        assert market.slug == "highest-temperature-in-seattle-on-february-10"
        assert len(market.outcomes) == 2
    
    def test_yes_price(self, sample_market):
        """Test yes_price property."""
        market = Market.from_dict(sample_market)
        assert market.yes_price == 0.15
    
    def test_to_dict_roundtrip(self, sample_market):
        """Test that to_dict produces valid dict."""
        market = Market.from_dict(sample_market)
        result = market.to_dict()
        
        assert result["id"] == sample_market["id"]
        assert result["question"] == sample_market["question"]


class TestSignal:
    """Tests for Signal dataclass."""
    
    def test_from_dict(self, sample_signal):
        """Test creating Signal from dict."""
        signal = Signal.from_dict(sample_signal)
        
        assert signal.market_id == "test-market-123"
        assert signal.city == "seattle"
        assert signal.edge == 0.20
        assert signal.legacy_proximity_pass == True
    
    def test_to_dict_roundtrip(self, sample_signal):
        """Test that to_dict produces valid dict."""
        signal = Signal.from_dict(sample_signal)
        result = signal.to_dict()
        
        assert result["edge"] == sample_signal["edge"]
        assert result["city"] == sample_signal["city"]


class TestPosition:
    """Tests for Position dataclass."""
    
    def test_from_dict(self, sample_position):
        """Test creating Position from dict."""
        position = Position.from_dict(sample_position)
        
        assert position.market_id == "test-market-123"
        assert position.price == 0.15
        assert position.shares == 133.33
        assert position.status == PositionStatus.OPEN
    
    def test_status_parsing(self):
        """Test position status parsing."""
        data = {
            "market_id": "123",
            "question": "Test",
            "city": "Test",
            "outcome": "Yes",
            "price": 0.1,
            "shares": 10,
            "amount_invested": 1,
            "edge": 0.1,
            "status": "CLOSED"
        }
        position = Position.from_dict(data)
        assert position.status == PositionStatus.CLOSED


class TestForecastResult:
    """Tests for ForecastResult dataclass."""
    
    def test_empty_result(self):
        """Test creating empty forecast result."""
        result = ForecastResult.empty()
        
        assert result.consensus_prob == 0.0
        assert result.source_probs == {}
    
    def test_with_sources(self):
        """Test forecast result with source data."""
        result = ForecastResult(
            consensus_prob=0.35,
            source_probs={"OpenMeteo": 0.35, "NWS": 0.33}
        )
        
        assert result.consensus_prob == 0.35
        assert len(result.source_probs) == 2
