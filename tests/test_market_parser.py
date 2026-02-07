"""
Tests for market_parser module.
"""
import pytest
from market_parser import MarketParser, get_parser


class TestMarketParser:
    """Tests for MarketParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = MarketParser()
    
    def test_parse_market_title_range(self):
        """Test parsing temperature range from title."""
        title = "Will the highest temperature in Atlanta be between 46-47°F on January 29?"
        result = self.parser.parse_market_title(title)
        
        assert result["unit"] == "F"
        assert result["min"] == 46.0
        assert result["max"] == 47.0
    
    def test_parse_market_title_celsius(self):
        """Test parsing Celsius temperatures."""
        title = "Will the highest temperature in London be between 8-9°C on February 7?"
        result = self.parser.parse_market_title(title)
        
        assert result["unit"] == "C"
        assert result["min"] == 8.0
        assert result["max"] == 9.0
    
    def test_parse_market_title_with_city(self):
        """Test unit detection from city when not explicit in title."""
        title = "Will the highest temperature be between 8-9 on February 7?"
        result = self.parser.parse_market_title(title, city="London")
        
        assert result["unit"] == "C"  # London should default to Celsius
    
    def test_extract_city_from_slug(self):
        """Test city extraction from market slug."""
        assert self.parser.extract_city_from_slug("highest-temperature-in-london-on-february-6") == "london"
        assert self.parser.extract_city_from_slug("highest-temperature-in-new-york-on-february-6") == "new york"
        assert self.parser.extract_city_from_slug("random-slug") == "unknown"
    
    def test_parse_question_temp_range(self):
        """Test parsing question with temperature range."""
        question = "Will the highest temperature in Seattle be between 45-46°F on February 10?"
        result = self.parser.parse_question(question)
        
        assert result["city"] is not None
        assert result["condition"] == "temp_range"
        assert result["threshold_val"] == (45, 46)
    
    def test_parse_question_rain(self):
        """Test parsing rain question."""
        question = "Will it rain in Miami on February 10?"
        result = self.parser.parse_question(question)
        
        assert result["condition"] == "rain"
        assert result["threshold_val"] == 0.5
    
    def test_parse_outcome_range(self):
        """Test parsing outcome names to ranges."""
        assert self.parser.parse_outcome_name("70-71", "", "") == (70.0, 71.0)
        assert self.parser.parse_outcome_name("76 or higher", "", "")[0] == 76.0
        assert self.parser.parse_outcome_name("below 50", "", "")[1] == 50.0
    
    def test_is_unit_consistent(self):
        """Test unit consistency checking."""
        assert self.parser.is_unit_consistent("london", "C") == True
        assert self.parser.is_unit_consistent("london", "F") == False
        assert self.parser.is_unit_consistent("miami", "F") == True
        assert self.parser.is_unit_consistent("miami", "C") == False


class TestGetParser:
    """Tests for get_parser singleton function."""
    
    def test_returns_parser_instance(self):
        """Test that get_parser returns a MarketParser."""
        parser = get_parser()
        assert isinstance(parser, MarketParser)
    
    def test_returns_same_instance(self):
        """Test that get_parser returns the same instance."""
        parser1 = get_parser()
        parser2 = get_parser()
        assert parser1 is parser2
