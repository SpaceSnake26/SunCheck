"""
Central configuration for SunCheck bot.
All magic numbers and hardcoded values should be defined here.
"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class TradingConfig:
    """Trading strategy thresholds and limits."""
    # Edge thresholds
    MIN_EDGE: float = 0.06  # Minimum edge to consider a trade (6%)
    HIGH_EDGE_THRESHOLD: float = 0.15  # Edge threshold for high confidence trades (15%)
    PROXIMITY_THRESHOLD: float = 0.15  # Max distance from bucket for proximity check
    
    # Price limits
    MAX_PRICE: float = 0.18  # Maximum price to buy (18 cents)
    MIN_PRICE: float = 0.01  # Minimum price (below this = no liquidity)
    SNIPE_MAX_PRICE: float = 0.10  # Max price for lottery snipes (10 cents)
    SNIPE_EDGE_MULTIPLIER: float = 2.5  # Model prob must be > price * this
    
    # Position sizing
    DEFAULT_BET_AMOUNT: float = 20.0  # Default bet size in USD
    AUTO_TRADE_EDGE_THRESHOLD: float = 0.70  # Edge threshold for auto-trading (70%)
    AUTO_TRADE_AMOUNT: float = 50.0  # Auto trade bet size
    
    # UI filter defaults
    DEFAULT_MIN_EDGE_FILTER: float = 0.05
    DEFAULT_MAX_SETTLE_DAYS: float = 5.0
    
    # CLOB price mismatch threshold
    CLOB_PRICE_MISMATCH_THRESHOLD: float = 0.4


@dataclass
class WeatherConfig:
    """Weather API and probability calculation settings."""
    # API URLs
    OPEN_METEO_URL: str = "https://api.open-meteo.com/v1/forecast"
    VISUAL_CROSSING_URL: str = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    NWS_POINTS_URL: str = "https://api.weather.gov/points"
    GEOCODING_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
    
    # API timeouts (seconds)
    API_TIMEOUT: int = 10
    
    # Probability calculation (CDF sigma parameters)
    SIGMA_BASE: float = 0.8  # Base sigma for uncertainty
    SIGMA_PER_DAY: float = 0.3  # Additional sigma per lead day
    
    # Cache settings
    CACHE_TTL_HOURS: int = 1  # Forecast cache TTL
    CACHE_HISTORICAL_TTL_HOURS: int = 24  # Historical data cache TTL
    
    # Temperature bounds for edge cases
    TEMP_UPPER_BOUND: float = 150.0  # Arbitrary high temp for "X or higher"
    TEMP_LOWER_BOUND: float = -50.0  # Arbitrary low temp for "below X"


@dataclass
class MarketConfig:
    """Polymarket API and market scanning settings."""
    # API URLs
    GAMMA_API_URL: str = "https://gamma-api.polymarket.com"
    CLOB_HOST: str = "https://clob.polymarket.com"
    DATA_API_URL: str = "https://data-api.polymarket.com"
    
    # Scanning limits
    DEFAULT_MARKET_LIMIT: int = 150
    EXTENDED_MARKET_LIMIT: int = 250  # For thorough scans
    CITY_QUERY_LIMIT: int = 50
    
    # Weather tag ID on Polymarket
    WEATHER_TAG_ID: int = 1002
    
    # Concurrent request settings
    MAX_WORKERS: int = 10
    REQUEST_TIMEOUT: int = 15
    MAX_RETRIES: int = 3
    RETRY_BACKOFF: int = 1
    
    # Minimum position value to display
    MIN_POSITION_VALUE: float = 0.10


@dataclass
class CityConfig:
    """City classification for unit detection."""
    # International cities (use Celsius)
    INTERNATIONAL_CITIES: List[str] = field(default_factory=lambda: [
        "london", "paris", "tokyo", "berlin", "madrid", "rome", 
        "dubai", "singapore", "toronto", "buenos-aires", "seoul"
    ])
    
    # US cities (use Fahrenheit)
    US_CITIES: List[str] = field(default_factory=lambda: [
        "miami", "new-york", "chicago", "seattle", "austin", 
        "los-angeles", "las-vegas", "atlanta", "boston", "dallas",
        "denver", "houston", "phoenix", "san-francisco"
    ])
    
    # Station coordinates for precise weather data
    STATION_MAP: dict = field(default_factory=lambda: {
        "chicago": {"lat": 41.9742, "lon": -87.9073, "code": "KORD"},
        "atlanta": {"lat": 33.6407, "lon": -84.4277, "code": "KATL"},
        "new-york": {"lat": 40.7831, "lon": -73.9712, "code": "KNYC"},
        "miami": {"lat": 25.7932, "lon": -80.2906, "code": "KMIA"},
        "seattle": {"lat": 47.4502, "lon": -122.3088, "code": "KSEA"},
        "london": {"lat": 51.4700, "lon": -0.4543, "code": "EGLL"},
        "paris": {"lat": 49.0097, "lon": 2.5479, "code": "LFPG"},
        "los-angeles": {"lat": 33.9416, "lon": -118.4085, "code": "KLAX"},
        "san-francisco": {"lat": 37.6213, "lon": -122.3790, "code": "KSFO"},
        "austin": {"lat": 30.1975, "lon": -97.6664, "code": "KAUS"},
        "boston": {"lat": 42.3601, "lon": -71.0589, "code": "KBOS"},
        "dallas": {"lat": 32.8998, "lon": -97.0403, "code": "KDFW"},
        "denver": {"lat": 39.8561, "lon": -104.6737, "code": "KDEN"},
        "houston": {"lat": 29.9902, "lon": -95.3368, "code": "KIAH"},
        "las-vegas": {"lat": 36.0840, "lon": -115.1537, "code": "KLAS"},
        "phoenix": {"lat": 33.4342, "lon": -112.0116, "code": "KPHX"},
        "tokyo": {"lat": 35.5523, "lon": 139.7797, "code": "RJTT"},
        "berlin": {"lat": 52.3667, "lon": 13.5033, "code": "EDDB"},
        "rome": {"lat": 41.8003, "lon": 12.2389, "code": "LIRF"},
        "madrid": {"lat": 40.4839, "lon": 3.5680, "code": "LEMD"},
        "toronto": {"lat": 43.6777, "lon": -79.6248, "code": "CYYZ"},
    })


@dataclass 
class AppConfig:
    """Application-level settings."""
    # Logging
    LOG_MAX_ENTRIES: int = 100
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    # Scheduler
    SCHEDULER_INTERVAL_SECONDS: int = 3600  # 1 hour
    
    # Portfolio
    INITIAL_PAPER_CASH: float = 1000.0
    PORTFOLIO_FILENAME: str = "portfolio.json"


# Global config instances
trading = TradingConfig()
weather = WeatherConfig()
market = MarketConfig()
cities = CityConfig()
app = AppConfig()


def is_international_city(city: str) -> bool:
    """Check if city uses Celsius (international) or Fahrenheit (US)."""
    city_lower = city.lower().replace(" ", "-")
    return any(ic in city_lower for ic in cities.INTERNATIONAL_CITIES)


def is_us_city(city: str) -> bool:
    """Check if city is in the US."""
    city_lower = city.lower().replace(" ", "-")
    return any(us in city_lower for us in cities.US_CITIES)


def get_unit_for_city(city: str) -> str:
    """Get the appropriate temperature unit for a city."""
    return "C" if is_international_city(city) else "F"
