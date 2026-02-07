"""Unified market parsing utilities for SunCheck bot.

Consolidates all question/title parsing logic from market_scanner and paper_trader.
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

import config


class MarketParser:
    """Parses Polymarket weather market questions and titles."""
    
    def __init__(self):
        self.intl_cities = config.cities.INTERNATIONAL_CITIES
        self.us_cities = config.cities.US_CITIES
        self.all_cities = self.intl_cities + self.us_cities
    
    def parse_market_title(self, title: str, city: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts Unit, Min, Max from market title.
        
        Example: "Will the highest temperature in Atlanta be between 46-47°F on January 29?"
        Returns: {"unit": "F", "min": 46.0, "max": 47.0}
        """
        title = title.lower().replace("–", "-")  # Normalize dashes
        
        # Determine Unit
        unit = self._detect_unit(title, city)
        
        # Parse range or single value
        val_min, val_max = self._parse_temperature_range(title)
        
        return {"unit": unit, "min": val_min, "max": val_max}
    
    def _detect_unit(self, title: str, city: Optional[str] = None) -> str:
        """Detect temperature unit from title or city."""
        title_lower = title.lower()
        
        # Explicit unit in title
        if "°c" in title_lower or "celsius" in title_lower:
            return "C"
        if "°f" in title_lower or "fahrenheit" in title_lower:
            return "F"
        
        # Infer from city
        if city:
            return config.get_unit_for_city(city)
        
        return "F"  # Default to Fahrenheit
    
    def _parse_temperature_range(self, title: str) -> Tuple[Optional[float], Optional[float]]:
        """Parse temperature range from title."""
        # Range: "46-47" or "46 - 47"
        range_match = re.search(r'(-?\d+)\s*-\s*(-?\d+)', title)
        if range_match:
            return float(range_match.group(1)), float(range_match.group(2))
        
        # Single value
        single_match = re.search(r'(-?\d+)', title)
        if single_match:
            val = float(single_match.group(1))
            return val, val
        
        return None, None
    
    def parse_question(self, question: str, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Full question parsing for trade analysis.
        
        Returns dict with: city, condition, threshold_val, event_date
        """
        city = None
        condition = None
        threshold_val = None
        event_date = None
        
        # Temperature patterns
        higher_pattern = r"highest temperature in (.+?)\s+be\s+(-?\d+).+?(?:higher|above|greater)"
        lower_pattern = r"highest temperature in (.+?)\s+be\s+(-?\d+).+?(?:below|lower|less)"
        range_pattern = r"highest temperature in (.+?)\s+be\s+between\s+(-?\d+)\s*-\s*(-?\d+)"
        exact_pattern = r"highest temperature in (.+?)\s+be\s+(-?\d+)(?:°?F|F|°?C|C)?(?:\s+on|\s*(\?|$))"
        
        higher_match = re.search(higher_pattern, question, re.IGNORECASE)
        lower_match = re.search(lower_pattern, question, re.IGNORECASE)
        range_match = re.search(range_pattern, question, re.IGNORECASE)
        exact_match = re.search(exact_pattern, question, re.IGNORECASE)
        
        if higher_match:
            city = higher_match.group(1).strip()
            threshold_val = int(higher_match.group(2))
            condition = "max_temp"
        elif lower_match:
            city = lower_match.group(1).strip()
            threshold_val = int(lower_match.group(2))
            condition = "max_temp_below"
        elif range_match:
            city = range_match.group(1).strip()
            low, high = int(range_match.group(2)), int(range_match.group(3))
            threshold_val = (low, high)
            condition = "temp_range"
        elif exact_match:
            city = exact_match.group(1).strip()
            val = int(exact_match.group(2))
            threshold_val = (val - 0.5, val + 0.5)
            condition = "temp_range"
        
        # Extract date if condition found
        if condition:
            date_match = re.search(r"on ([A-Z][a-z]+ \d{1,2})", question)
            if date_match:
                event_date = self._parse_friendly_date(date_match.group(1))
        
        # Check for rain/precipitation
        if not condition and ("rain" in question.lower() or "precipitation" in question.lower()):
            city_match = re.search(r"in ([A-Z][a-z\s]+)\??", question)
            if city_match:
                city = city_match.group(1).strip()
                condition = "rain"
                threshold_val = 0.5
        
        return {
            "city": city,
            "condition": condition,
            "threshold_val": threshold_val,
            "event_date": event_date
        }
    
    def _parse_friendly_date(self, date_text: str) -> Optional[str]:
        """Parse 'January 29' format to 'YYYY-MM-DD'."""
        try:
            year = datetime.now().year
            full_date_str = f"{date_text} {year}"
            dt = datetime.strptime(full_date_str, "%B %d %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None
    
    def extract_city_from_slug(self, slug: str) -> str:
        """
        Extract city name from market slug.
        
        Examples:
            "highest-temperature-in-london-on-february-6" -> "london"
            "highest-temperature-in-new-york-on-february-6" -> "new york"
        """
        slug_lower = slug.lower()
        
        # Pattern: highest-temperature-in-CITY-on-DATE
        if "highest-temperature-in-" in slug_lower:
            parts = slug_lower.split("-on-")[0].split("-in-")
            if len(parts) > 1:
                return parts[1].replace("-", " ")
        
        # Fallback: look for "-in-" pattern
        if "-in-" in slug_lower:
            parts = slug_lower.split("-in-")
            if len(parts) > 1:
                # Take first word after "in"
                return parts[1].split("-")[0]
        
        return "unknown"
    
    def parse_outcome_name(self, outcome_name: str, question: str = "", end_date: str = "") -> Tuple[Optional[float], Optional[float]]:
        """
        Parse outcome name to extract temperature range.
        
        Examples:
            "70-71" -> (70.0, 71.0)
            "76 or higher" -> (76.0, 150.0)
            "below 50" -> (-50.0, 50.0)
            "Yes" -> parsed from question
        """
        name = outcome_name.lower()
        
        # Range: "70-71" or "70 - 71"
        range_match = re.search(r'(-?\d+)\s*-\s*(-?\d+)', name)
        if range_match:
            return float(range_match.group(1)), float(range_match.group(2))
        
        # "X or higher" / "above X" / "greater than X"
        if any(word in name for word in ["higher", "above", "greater"]):
            comp_match = re.search(r'(-?\d+)', name)
            if comp_match:
                return float(comp_match.group(1)), config.weather.TEMP_UPPER_BOUND
        
        # "below X" / "lower than X" / "less than X"
        if any(word in name for word in ["below", "lower", "less"]):
            comp_match = re.search(r'(-?\d+)', name)
            if comp_match:
                return config.weather.TEMP_LOWER_BOUND, float(comp_match.group(1))
        
        # Exact value: "75"
        exact_match = re.search(r'(-?\d+)', name)
        if exact_match:
            val = float(exact_match.group(1))
            return val - 0.5, val + 0.5
        
        # Binary "Yes" - parse from question
        if name in ["yes", "yes!"]:
            parsed = self.parse_question(question, end_date)
            condition = parsed.get("condition")
            threshold = parsed.get("threshold_val")
            
            if condition == "max_temp" and threshold:
                return threshold - 0.5, threshold + 0.5
            elif condition == "max_temp_below" and threshold:
                return config.weather.TEMP_LOWER_BOUND, threshold
            elif condition == "temp_range" and isinstance(threshold, tuple):
                return threshold
            elif condition == "rain":
                return 0.5, 10.0
        
        return None, None
    
    def is_unit_consistent(self, city: str, unit: str, title: str = "") -> bool:
        """
        Check if temperature unit is consistent with city region.
        
        International cities should use Celsius, US cities should use Fahrenheit.
        """
        title_lower = title.lower()
        city_lower = city.lower()
        
        is_intl = (
            config.is_international_city(city) or 
            "celsius" in title_lower or 
            "°c" in title_lower
        )
        is_us = (
            config.is_us_city(city) or 
            "fahrenheit" in title_lower or 
            "°f" in title_lower
        )
        
        # Reject F markets for international cities (unless also US)
        if is_intl and unit == 'F' and not is_us:
            return False
        
        # Reject C markets for non-international cities
        if not is_intl and unit == 'C':
            return False
        
        return True


# Singleton instance for convenience
_parser = None


def get_parser() -> MarketParser:
    """Get singleton MarketParser instance."""
    global _parser
    if _parser is None:
        _parser = MarketParser()
    return _parser
