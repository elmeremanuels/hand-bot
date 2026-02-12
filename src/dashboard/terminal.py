"""
Terminal dashboard using Rich library.
Displays live bot statistics, positions, and market data.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich import box

logger = logging.getLogger(__name__)


class TerminalDashboard:
    """
    Live terminal dashboard for the trading bot.
    
    Features:
    - Real-time bot statistics
    - Open positions table
    - Recent trade history
    - Market scanner status
    - Performance metrics
    """

    def __init__(self):
        """Initialize the terminal dashboard."""
        self.console = Console()
        self.live: Optional[Live] = None
        
        # Dashboard data
        self.bot_stats = {
            "uptime": timedelta(0),
            "scans": 0,
            "signals": 0,
            "trades": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "balance": 0.0,
        }
        
        self.open_positions: List[Dict] = []
        self.recent_trades: List[Dict] = []
        self.markets_found: List[Dict] = []
        
        self.trading_mode = "📝 Paper Trading"
        self.safety_limits = {
            "max_position": 5.0,
            "max_positions": 3,
            "confidence_range": "80-95%",
        }

    def start(self):
        """Start the live dashboard."""
        logger.info("🖥️  Starting terminal dashboard...")
        self.live = Live(
            self._build_layout(),
            console=self.console,
            screen=False,
            refresh_per_second=1,
        )
        self.live.start()

    def stop(self):
        """Stop the live dashboard."""
        if self.live:
            self.live.stop()
            logger.info("Dashboard stopped")

    def update_stats(self, stats: Dict):
        """Update bot statistics."""
        self.bot_stats.update(stats)
        if self.live:
            self.live.update(self._build_layout())

    def update_positions(self, positions: List[Dict]):
        """Update open positions."""
        self.open_positions = positions
        if self.live:
            self.live.update(self._build_layout())

    def add_trade(self, trade: Dict):
        """Add a trade to recent history."""
        self.recent_trades.insert(0, trade)
        # Keep only last 5 trades
        self.recent_trades = self.recent_trades[:5]
        if self.live:
            self.live.update(self._build_layout())

    def update_markets(self, markets: List[Dict]):
        """Update markets found."""
        self.markets_found = markets[:5]  # Keep only top 5
        if self.live:
            self.live.update(self._build_layout())

    def _build_layout(self) -> Layout:
        """Build the dashboard layout."""
        layout = Layout()
        
        # Split into header and body
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        
        # Header
        layout["header"].update(self._build_header())
        
        # Body split into left and right
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        
        layout["body"]["left"].split_column(
            Layout(name="stats", size=10),
            Layout(name="positions"),
        )
        
        layout["body"]["right"].split_column(
            Layout(name="markets", size=12),
            Layout(name="trades"),
        )
        
        # Fill sections
        layout["body"]["left"]["stats"].update(self._build_stats_panel())
        layout["body"]["left"]["positions"].update(self._build_positions_panel())
        layout["body"]["right"]["markets"].update(self._build_markets_panel())
        layout["body"]["right"]["trades"].update(self._build_trades_panel())
        
        # Footer
        layout["footer"].update(self._build_footer())
        
        return layout

    def _build_header(self) -> Panel:
        """Build header panel."""
        text = Text()
        text.append("🤖 ", style="bold cyan")
        text.append("Polymarket Trading Bot", style="bold white")
        text.append(f" | {self.trading_mode}", style="bold yellow")
        text.append(f" | Balance: ${self.bot_stats.get('balance', 0):.2f}", style="bold green")
        
        return Panel(
            text,
            style="bold white on blue",
            box=box.HEAVY,
        )

    def _build_stats_panel(self) -> Panel:
        """Build statistics panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white", justify="right")
        
        stats = self.bot_stats
        
        table.add_row("⏱️  Uptime", str(stats.get("uptime", timedelta(0))))
        table.add_row("🔍 Scans", str(stats.get("scans", 0)))
        table.add_row("🎯 Signals", str(stats.get("signals", 0)))
        table.add_row("📊 Trades", str(stats.get("trades", 0)))
        
        win_rate = stats.get("win_rate", 0.0)
        win_rate_style = "green" if win_rate > 0.5 else "red"
        table.add_row("✅ Win Rate", f"[{win_rate_style}]{win_rate:.1%}[/{win_rate_style}]")
        
        pnl = stats.get("total_pnl", 0.0)
        pnl_style = "green" if pnl > 0 else "red"
        table.add_row("💰 Total PnL", f"[{pnl_style}]${pnl:+.2f}[/{pnl_style}]")
        
        return Panel(
            table,
            title="[bold cyan]📈 Statistics[/bold cyan]",
            border_style="cyan",
        )

    def _build_positions_panel(self) -> Panel:
        """Build open positions panel."""
        if not self.open_positions:
            return Panel(
                Text("No open positions", style="dim italic", justify="center"),
                title="[bold yellow]📊 Open Positions[/bold yellow]",
                border_style="yellow",
            )
        
        table = Table(box=box.SIMPLE)
        table.add_column("Side", style="cyan")
        table.add_column("Price", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("Time", style="dim")
        
        for pos in self.open_positions[:5]:
            side_emoji = "📈" if pos.get("side") == "up" else "📉"
            table.add_row(
                f"{side_emoji} {pos.get('side', 'unknown').upper()}",
                f"${pos.get('price', 0):.3f}",
                f"${pos.get('size', 0):.2f}",
                pos.get("time", ""),
            )
        
        return Panel(
            table,
            title="[bold yellow]📊 Open Positions[/bold yellow]",
            border_style="yellow",
        )

    def _build_markets_panel(self) -> Panel:
        """Build markets found panel."""
        if not self.markets_found:
            return Panel(
                Text("Scanning for markets...", style="dim italic", justify="center"),
                title="[bold magenta]🔍 Markets Found[/bold magenta]",
                border_style="magenta",
            )
        
        table = Table(box=box.SIMPLE)
        table.add_column("Asset", style="cyan")
        table.add_column("Up", justify="right", style="green")
        table.add_column("Down", justify="right", style="red")
        table.add_column("Time", style="dim")
        
        for market in self.markets_found:
            table.add_row(
                market.get("asset", "BTC")[:3].upper(),
                f"{market.get('up_prob', 0):.1%}",
                f"{market.get('down_prob', 0):.1%}",
                market.get("time_remaining", ""),
            )
        
        return Panel(
            table,
            title="[bold magenta]🔍 Markets Found[/bold magenta]",
            border_style="magenta",
        )

    def _build_trades_panel(self) -> Panel:
        """Build recent trades panel."""
        if not self.recent_trades:
            return Panel(
                Text("No trades yet", style="dim italic", justify="center"),
                title="[bold green]💵 Recent Trades[/bold green]",
                border_style="green",
            )
        
        table = Table(box=box.SIMPLE)
        table.add_column("Side", style="cyan")
        table.add_column("PnL", justify="right")
        table.add_column("Edge", justify="right")
        table.add_column("Status", style="dim")
        
        for trade in self.recent_trades:
            side_emoji = "📈" if trade.get("side") == "up" else "📉"
            pnl = trade.get("pnl", 0)
            pnl_style = "green" if pnl > 0 else "red"
            
            table.add_row(
                f"{side_emoji} {trade.get('side', 'unknown').upper()}",
                f"[{pnl_style}]${pnl:+.2f}[/{pnl_style}]",
                f"{trade.get('edge', 0):.1%}",
                trade.get("status", "open"),
            )
        
        return Panel(
            table,
            title="[bold green]💵 Recent Trades[/bold green]",
            border_style="green",
        )

    def _build_footer(self) -> Panel:
        """Build footer panel."""
        limits = self.safety_limits
        text = Text()
        text.append("🛡️  Safety Limits: ", style="bold yellow")
        text.append(f"Max ${limits['max_position']:.0f}/trade ", style="white")
        text.append(f"| {limits['max_positions']} positions ", style="white")
        text.append(f"| Confidence: {limits['confidence_range']}", style="white")
        text.append(" | Press Ctrl+C to stop", style="dim italic")
        
        return Panel(
            text,
            style="white on dark_blue",
            box=box.HEAVY,
        )

    def print_welcome(self):
        """Print welcome message."""
        self.console.clear()
        self.console.print("\n")
        self.console.print("=" * 60, style="bold cyan")
        self.console.print("🤖  POLYMARKET TRADING BOT", style="bold white", justify="center")
        self.console.print("=" * 60, style="bold cyan")
        self.console.print(f"\nMode: {self.trading_mode}", style="bold yellow")
        self.console.print(f"Safety: Max ${self.safety_limits['max_position']:.0f} per trade, {self.safety_limits['max_positions']} positions max", style="white")
        self.console.print(f"Confidence: {self.safety_limits['confidence_range']}", style="white")
        self.console.print("\n🚀 Starting bot...\n", style="bold green")


# Standalone function for simple dashboard
def print_trade_alert(side: str, size: float, price: float, edge: float, confidence: float):
    """Print a trade alert to console."""
    console = Console()
    
    side_emoji = "📈" if side == "up" else "📉"
    side_color = "green" if side == "up" else "red"
    
    panel = Panel(
        f"[bold]{side_emoji} {side.upper()} Trade Signal[/bold]\n\n"
        f"Size: ${size:.2f}\n"
        f"Entry: ${price:.3f}\n"
        f"Expected Edge: {edge:.1%}\n"
        f"Confidence: {confidence:.1%}",
        title="🎯 Trade Opportunity",
        border_style=side_color,
        style=f"on {side_color}",
    )
    
    console.print(panel)
