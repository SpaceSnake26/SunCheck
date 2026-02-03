# ☀️ SunCheck: Intelligent Weather Arbitrage Bot

SunCheck is a sophisticated automated trading bot designed for **Polymarket weather enthusiasts**. It bridges the gap between raw meteorological data and prediction markets by identifying pricing inefficiencies in daily temperature and precipitation contracts.

## 🚀 Core Features

*   **Multi-Source Consensus**: Aggregates forecasts from **Open-Meteo**, **Visual Crossing**, and the **National Weather Service (NWS)**.
*   **Probabilistic Edge Detection**: Uses a Cumulative Distribution Function (CDF) model to calculate the "True Probability" ($P_{API}$) of a weather event and compares it against the market price ($P_{Market}$).
*   **Deep Market Scanning**: Concurrently scans Polymarket for daily weather contracts across 20+ major global cities (New York, London, Tokyo, etc.).
*   **Integrated Dashboard**: A sleek FastAPI-based web interface to track portfolio health, live logs, and actionable opportunities.
*   **Hybrid Execution**: Supports both safe **Paper Trading** for strategy validation and **Live Execution** via the Polymarket CLOB.

## 🛠️ Tech Stack

*   **Language**: Python 3.10+
*   **Web Framework**: FastAPI & Jinja2
*   **Trading Interface**: Polymarket SDK (Signer/Funder Proxy)
*   **Data Science**: Math-based CDF modeling for weather distributions
*   **Concurrency**: ThreadPool-based market scavenging

## 📊 The $P_{API}$ Formula
The bot calculates the expected probability of a specific temperature range by fitting forecast ensembles into a normal distribution curve with a dynamic σ (sigma) buffer. 
*   **Edge Found**: If $|P_{API} - P_{Market}| > 0.05$ (5% edge), the bot flags a high-conviction opportunity.
*   **Sniping**: Automatically identifies "Lotteries" where the market price is < $0.12 but the model suggests a significant EV (Expected Value) mismatch.

## 🛠️ Setup & Usage

1.  **Clone & Install**:
    ```bash
    git clone https://github.com/SpaceSnake26/SunCheck.git
    cd SunCheck
    pip install -r requirements.txt
    ```

2.  **Configure Environment**:
    Create a `src/.env` file with your Polymarket credentials:
    ```env
    POLY_ADDRESS="your_address"
    POLY_PRIVATE_KEY="your_private_key"
    VISUAL_CROSSING_KEY="optional_api_key"
    ```

3.  **Run the Server**:
    ```bash
    python -m uvicorn src.server:app --host 0.0.0.0 --port 8000
    ```

## ⚠️ Disclaimer
This bot is for educational and research purposes. Weather prediction markets are highly volatile. Use at your own risk.

---
*Built for the clouds, optimized for the gains.* 🗼🌩️
