# Weather Arbitrage Scanner

A modular bot to scan Polymarket weather markets, compute probabilities using a Normal CDF model based on Open-Meteo forecasts, and identify trading opportunities with a 15% pricing edge.

## Setup

1. Install dependencies:
   ```bash
   pip install requests pyyaml
   ```

2. Configure `config.yaml` with your bankroll and optional Telegram credentials.

3. Run the scanner:
   ```bash
   python src/scanner.py
   ```

4. Run the backtester:
   ```bash
   python src/backtester.py
   ```

## Modules

- `polymarket_client.py`: Gamma API interactions.
- `openmeteo_client.py`: Forecast data with 1-hour caching.
- `market_parser.py`: Regex-based question parsing.
- `probability_model.py`: Normal Distribution CDF probability logic.
- `storage.py`: JSONL logging and report saving.
- `notifier.py`: Console and optional Telegram alerts.
- `backtester.py`: Historical performance analysis.

## Risk Management

- **Edge Threshold**: 15% minimum edge required for OPPORTUNITY.
- **Bet Sizing**: Capped at `bankroll * 0.15 * 0.03`.
- **Limits**: 1 trade per city/day; max 15% total bankroll risk.
