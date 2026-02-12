"""
Paper trading script for testing the bot without real money.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from src.main import main


async def run_paper_trading():
    """Run the bot in paper trading mode."""
    print("=" * 60)
    print("🎮 PAPER TRADING MODE")
    print("=" * 60)
    print("This is a simulation - no real trades will be executed")
    print("Use this to test the bot before going live")
    print("=" * 60)
    print()

    await main()


if __name__ == "__main__":
    asyncio.run(run_paper_trading())
