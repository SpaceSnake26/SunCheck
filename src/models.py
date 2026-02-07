"""
Data models for SunCheck bot.

Provides typed dataclasses for core data structures used throughout the application.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


class TradeOutcome(Enum):
    """Possible trade outcomes."""
    YES = "YES"
    NO = "NO"


class PositionStatus(Enum):
    """Position lifecycle status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PENDING = "PENDING"


class ConditionType(Enum):
    """Weather condition types for market analysis."""
    MAX_TEMP = "max_temp"
    MAX_TEMP_BELOW = "max_temp_below"
    TEMP_RANGE = "temp_range"
    RAIN = "rain"


@dataclass
class Market:
    """Represents a Polymarket weather market."""
    id: str
    question: str
    slug: str
    outcomes: List[str]
    outcome_prices: List[float]
    clob_token_ids: List[str]
    end_date: Optional[str] = None
    
    @property
    def yes_price(self) -> float:
        """Get YES outcome price (typically index 0 or 1)."""
        if self.outcome_prices and len(self.outcome_prices) > 0:
            return self.outcome_prices[0]
        return 0.0
    
    @property
    def no_price(self) -> float:
        """Get NO outcome price."""
        if self.outcome_prices and len(self.outcome_prices) > 1:
            return self.outcome_prices[1]
        return 1.0 - self.yes_price
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Market":
        """Create Market from API response dict."""
        import json
        
        outcomes = data.get('outcomes', [])
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except:
                outcomes = []
        
        prices = data.get('outcomePrices', [])
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except:
                prices = []
        prices = [float(p) for p in prices] if prices else []
        
        token_ids = data.get('clobTokenIds', [])
        if isinstance(token_ids, str):
            try:
                token_ids = json.loads(token_ids)
            except:
                token_ids = []
        
        return cls(
            id=data.get('id', ''),
            question=data.get('question', ''),
            slug=data.get('slug', ''),
            outcomes=outcomes,
            outcome_prices=prices,
            clob_token_ids=token_ids,
            end_date=data.get('endDate')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            'id': self.id,
            'question': self.question,
            'slug': self.slug,
            'outcomes': self.outcomes,
            'outcomePrices': self.outcome_prices,
            'clobTokenIds': self.clob_token_ids,
            'endDate': self.end_date
        }


@dataclass
class Signal:
    """Trading signal generated from market analysis."""
    market_id: str
    question: str
    city: str
    true_prob: float
    market_prob: float
    edge: float
    action: str
    outcome: str
    source_probs: Dict[str, float] = field(default_factory=dict)
    om_val: Optional[float] = None
    target_range: Optional[Tuple[float, float]] = None
    legacy_proximity_pass: bool = False
    ev: float = 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        """Create Signal from dict."""
        target_int = data.get('target_int')
        target_range = tuple(target_int) if target_int else None
        
        return cls(
            market_id=data.get('market_id', ''),
            question=data.get('question', ''),
            city=data.get('city', ''),
            true_prob=data.get('true_prob', 0.0),
            market_prob=data.get('market_prob', 0.0),
            edge=data.get('edge', 0.0),
            action=data.get('action', ''),
            outcome=data.get('outcome', ''),
            source_probs=data.get('source_probs', {}),
            om_val=data.get('om_val'),
            target_range=target_range,
            legacy_proximity_pass=data.get('legacy_pass', False),
            ev=data.get('ev', 0.0)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            'market_id': self.market_id,
            'question': self.question,
            'city': self.city,
            'true_prob': self.true_prob,
            'market_prob': self.market_prob,
            'edge': self.edge,
            'action': self.action,
            'outcome': self.outcome,
            'source_probs': self.source_probs,
            'om_val': self.om_val,
            'target_int': self.target_range,
            'legacy_pass': self.legacy_proximity_pass,
            'ev': self.ev
        }


@dataclass
class Position:
    """Represents a trading position (open or closed)."""
    market_id: str
    question: str
    city: str
    outcome: str
    price: float
    shares: float
    amount_invested: float
    edge: float
    market_prob: float = 0.0
    true_prob: float = 0.0
    status: PositionStatus = PositionStatus.OPEN
    is_live: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    result: Optional[str] = None
    settled_date: Optional[str] = None
    payout: float = 0.0
    end_date: Optional[str] = None
    cur_value: Optional[float] = None
    cur_price: Optional[float] = None
    pnl: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create Position from dict."""
        status_str = data.get('status', 'OPEN')
        try:
            status = PositionStatus(status_str)
        except ValueError:
            status = PositionStatus.OPEN
        
        return cls(
            market_id=data.get('market_id', ''),
            question=data.get('question', ''),
            city=data.get('city', 'Unknown'),
            outcome=data.get('outcome', ''),
            price=float(data.get('price', 0)),
            shares=float(data.get('shares', 0)),
            amount_invested=float(data.get('amount_invested', 0)),
            edge=float(data.get('edge', 0)),
            market_prob=float(data.get('market_prob', 0)),
            true_prob=float(data.get('true_prob', 0)),
            status=status,
            is_live=data.get('is_live', False),
            timestamp=data.get('timestamp', datetime.now().isoformat()),
            result=data.get('result'),
            settled_date=data.get('settled_date'),
            payout=float(data.get('payout', 0)),
            end_date=data.get('endDate'),
            cur_value=data.get('cur_value'),
            cur_price=data.get('cur_price'),
            pnl=data.get('pnl')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            'market_id': self.market_id,
            'question': self.question,
            'city': self.city,
            'outcome': self.outcome,
            'price': self.price,
            'shares': self.shares,
            'amount_invested': self.amount_invested,
            'edge': self.edge,
            'market_prob': self.market_prob,
            'true_prob': self.true_prob,
            'status': self.status.value if isinstance(self.status, PositionStatus) else self.status,
            'is_live': self.is_live,
            'timestamp': self.timestamp,
            'result': self.result,
            'settled_date': self.settled_date,
            'payout': self.payout,
            'endDate': self.end_date,
            'cur_value': self.cur_value,
            'cur_price': self.cur_price,
            'pnl': self.pnl
        }


@dataclass
class Forecast:
    """Weather forecast data from a single source."""
    source: str
    temp: Optional[float] = None
    precip: Optional[float] = None
    probability: Optional[float] = None
    raw_value: Optional[float] = None
    
    def is_valid(self) -> bool:
        """Check if forecast has valid data."""
        return self.temp is not None


@dataclass
class ForecastResult:
    """Aggregated forecast result from multiple sources."""
    consensus_prob: float
    source_probs: Dict[str, float]
    raw_values: Dict[str, float] = field(default_factory=dict)
    forecasts: List[Forecast] = field(default_factory=list)
    
    @classmethod
    def empty(cls) -> "ForecastResult":
        """Create empty result."""
        return cls(consensus_prob=0.0, source_probs={})


@dataclass
class TradeProposal:
    """A proposed trade awaiting approval."""
    id: str
    market: Dict[str, Any]  # Raw market dict for compatibility
    signal: Dict[str, Any]  # Raw signal dict for compatibility
    outcome: str
    price: float
    edge: float
    ev: float
    delta_api: Optional[float] = None
    is_snipe: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    settles_in_hours: str = "?"
    settles_in_days: float = 999.0
    
    @property
    def market_id(self) -> str:
        """Get market ID from embedded market dict."""
        return self.market.get('id', '')
    
    @property
    def city(self) -> str:
        """Get city from embedded signal dict."""
        return self.signal.get('city', 'Unknown')
    
    @property
    def question(self) -> str:
        """Get question from embedded signal dict."""
        return self.signal.get('question', '')


@dataclass
class PortfolioStatus:
    """Current portfolio status summary."""
    cash: float
    invested: float
    total_value: float
    positions_count: int
    active_positions: List[Position] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CLOBPrice:
    """CLOB order book price data."""
    price: float  # Best ask (buy price)
    bid: float    # Best bid
    mid: float    # Mid price
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Optional["CLOBPrice"]:
        """Create from API response."""
        if not data:
            return None
        return cls(
            price=data.get('price', 0.0),
            bid=data.get('bid', 0.0),
            mid=data.get('mid', 0.0)
        )
