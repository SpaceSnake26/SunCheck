from market_scanner import MarketScanner
from weather_engine import WeatherEngine
from paper_trader import PaperTrader
from rich.console import Console
from rich.table import Table
import time
from portfolio import PortfolioManager

def main():
    console = Console()
    console.print("[bold blue]Starting Polymarket Weather Bot (Paper Trader)...[/bold blue]")

    scanner = MarketScanner()
    weather = WeatherEngine()
    trader = PaperTrader(weather)
    portfolio = PortfolioManager()

    console.print("[yellow]Scanning for Weather markets...[/yellow]")
    markets = scanner.get_weather_markets()
    
    if not markets:
        console.print("[red]No active weather markets found (after deep scan).[/red]")
        return

    console.print(f"[green]Found {len(markets)} markets. Analyzing...[/green]")
    
    all_signals = []
    headers = ["Question", "City", "True Prob", "Market Prob", "Edge", "Action"]

    # Analysis Loop
    for market in markets:
        time.sleep(0.1)
        signal = trader.analyze_market(market)
        if signal:
            all_signals.append(signal)
            console.print(f"Accepted: {market['question']}")
            
            # --- Auto-Trade Logic ---
            edge = signal['edge']
            if abs(edge) >= 0.70:
                outcome = "YES" if edge > 0 else "NO"
                # For NO bets, price is 1 - market_prob? 
                # Polymarket 'NO' shares are effectively buying Yes @ current price to sell? 
                # Or buying 'NO' shares.
                # Simplification: We track "BUY_YES" at market_prob, "BUY_NO" at (1 - market_prob).
                
                trade_price = signal['market_prob'] if outcome == "YES" else (1.0 - signal['market_prob'])
                trade_amount = 50.00 # Fixed bet size
                
                if portfolio.execute_trade(market, outcome, trade_price, trade_amount, edge):
                    console.print(f"[bold green]>>> EXECUTED TRADE: {outcome} on {signal['city']} (Edge {edge:.2f})[/bold green]")
                else:
                    console.print(f"[bold red]>>> FAILED TRADE: Insufficient Funds for {signal['city']}[/bold red]")
            # ------------------------
            
        else:
            # If debug prints are enabled in paper_trader, they show up.
            # We also change this message to be less confusing if it was just logged by trader.
            console.print(f"[dim]Skipped: {market['question']} (Analysis returned None)[/dim]")

    # Function to print table
    def print_table(signals, threshold_edge, title):
        table = Table(title=title)
        for h in headers:
            table.add_column(h)
        
        count = 0
        for s in signals:
            # Show if edge > threshold OR if it's a manual review in the base scan
            is_manual = s['action'] == "MANUAL_REVIEW"
            if abs(s['edge']) >= threshold_edge or (is_manual and threshold_edge == 0):
                edge_style = "green" if s['edge'] > 0 else "red"
                action_style = "bold green" if "BUY" in s['action'] else "dim"
                
                table.add_row(
                    str(s['question'])[:50] + "...", # Truncate long questions
                    s['city'],
                    f"{s['true_prob']:.2f}" if isinstance(s['true_prob'], float) else "N/A",
                    f"{s['market_prob']:.2f}",
                    f"[{edge_style}]{s['edge']:.2f}[/{edge_style}]" if isinstance(s['edge'], float) else "N/A",
                    f"[{action_style}]{s['action']}[/{action_style}]"
                )
                count += 1
        
        if count > 0:
            console.print(table)
        else:
            console.print(f"[dim]No opportunities > {int(threshold_edge*100)}% found.[/dim]")

    # Scan 1: All Analyzed Markets (User Request: Show everything analyzed)
    # Threshold 0.0 shows everything including HOLDs
    print_table(all_signals, 0.0, "Scan Results: All Analyzed Markets")

    # Scan 2: > 15% Edge (Actionable)
    print_table(all_signals, 0.15, "Actionable Opportunities (> 15% Edge)")
    
    # Check for settlements
    console.print("[yellow]Checking for settled positions...[/yellow]")
    settled = portfolio.settle_positions(trader)
    if settled > 0:
        console.print(f"[green]Settled {settled} positions.[/green]")

    # Portfolio Status
    status = portfolio.get_status()
    p_table = Table(title="Portfolio Status")
    p_table.add_column("Cash")
    p_table.add_column("Invested")
    p_table.add_column("Total Value")
    p_table.add_column("Active Positions")
    p_table.add_row(
        f"${status['cash']:.2f}",
        f"${status['invested']:.2f}",
        f"${status['total_value']:.2f}",
        str(status['positions_count'])
    )
    console.print(p_table)

if __name__ == "__main__":
    main()
