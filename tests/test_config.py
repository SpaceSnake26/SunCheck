"""
Tests for config module.
"""
import pytest
import config


class TestTradingConfig:
    """Tests for trading configuration."""
    
    def test_default_values(self):
        """Test that default trading values are reasonable."""
        assert config.trading.MIN_EDGE == 0.06
        assert config.trading.MAX_PRICE == 0.18
        assert config.trading.DEFAULT_BET_AMOUNT == 20.0
    
    def test_thresholds_are_valid_percentages(self):
        """Test that percentage thresholds are between 0 and 1."""
        assert 0 <= config.trading.MIN_EDGE <= 1
        assert 0 <= config.trading.MAX_PRICE <= 1
        assert 0 <= config.trading.HIGH_EDGE_THRESHOLD <= 1


class TestCityConfig:
    """Tests for city configuration."""
    
    def test_international_cities_exist(self):
        """Test that international cities list is populated."""
        assert len(config.cities.INTERNATIONAL_CITIES) > 0
        assert "london" in config.cities.INTERNATIONAL_CITIES
        assert "tokyo" in config.cities.INTERNATIONAL_CITIES
    
    def test_us_cities_exist(self):
        """Test that US cities list is populated."""
        assert len(config.cities.US_CITIES) > 0
        assert "miami" in config.cities.US_CITIES
        assert "seattle" in config.cities.US_CITIES
    
    def test_station_map_has_coordinates(self):
        """Test that station map has valid coordinates."""
        for city, data in config.cities.STATION_MAP.items():
            assert "lat" in data
            assert "lon" in data
            assert -90 <= data["lat"] <= 90
            assert -180 <= data["lon"] <= 180


class TestCityHelpers:
    """Tests for city helper functions."""
    
    def test_is_international_city(self):
        """Test international city detection."""
        assert config.is_international_city("london") == True
        assert config.is_international_city("London") == True
        assert config.is_international_city("miami") == False
    
    def test_is_us_city(self):
        """Test US city detection."""
        assert config.is_us_city("miami") == True
        assert config.is_us_city("Miami") == True
        assert config.is_us_city("london") == False
    
    def test_get_unit_for_city(self):
        """Test unit detection for cities."""
        assert config.get_unit_for_city("london") == "C"
        assert config.get_unit_for_city("tokyo") == "C"
        assert config.get_unit_for_city("miami") == "F"
        assert config.get_unit_for_city("seattle") == "F"


class TestWeatherConfig:
    """Tests for weather API configuration."""
    
    def test_api_urls_are_valid(self):
        """Test that API URLs start with https."""
        assert config.weather.OPEN_METEO_URL.startswith("https://")
        assert config.weather.VISUAL_CROSSING_URL.startswith("https://")
    
    def test_timeouts_are_reasonable(self):
        """Test that timeout values are reasonable."""
        assert 1 <= config.weather.API_TIMEOUT <= 60
    
    def test_sigma_values_are_positive(self):
        """Test that sigma values are positive."""
        assert config.weather.SIGMA_BASE > 0
        assert config.weather.SIGMA_PER_DAY > 0
