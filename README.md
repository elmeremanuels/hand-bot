# Polymarket Bitcoin Up/Down Trading Bot

Een geautomatiseerde trading bot die 24/7 handelt op Polymarket's "Bitcoin Up or Down" korte-termijn markets, gebaseerd op een bewezen strategie met >74% win rate.

## Kernprincipe

De bot exploiteert het feit dat Polymarket's prijzen (odds) zeer accuraat zijn. Wanneer de markt >80% confidence toont en Bitcoin duidelijk boven/onder de target staat, is de kans op winst statistisch hoger dan verlies.

## Tech Stack

- **Python 3.11+**
- **Polymarket Python SDK** (`py-clob-client`)
- **PostgreSQL** (kennisdatabase)
- **WebSocket** (real-time data)
- **FastAPI** (dashboard API)
- **React** (dashboard frontend - TODO)

## Features

### Core Trading

- **Smart Entry Criteria**: Alleen traden bij >80% confidence, 1-3 minuten resterende tijd, en >$30 spread
- **Risk Management**: Max 5% van balance per trade, automatische pause na 3 consecutive losses
- **Profit Lock**: Optionele early exit bij 92%+ probability voor risicoreductie

### News Integration

- **Real-time Monitoring**: Monitort CryptoNews, CoinFeeds, en Twitter voor major Bitcoin nieuws
- **Auto-Pause**: Pauzeer trading voor 5 minuten bij groot nieuws (SEC, ETF, hack, etc.)
- **Market Reaction Learning**: Slaat op hoe de markt reageerde op nieuws voor toekomstige beslissingen

### Knowledge Base

- **Pattern Learning**: Onthoudt welke patronen werken en welke niet
- **News Impact Tracking**: Leert van historische nieuwsimpact
- **Rule Performance**: Analyseert welke regels het beste presteren

### Dashboard (TODO)

- Real-time bot status en P&L
- Trade history met filtering
- Profit Lock toggle
- News feed met impact analysis
- Knowledge base inzichten

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone <repo-url>
cd hand-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

```bash
# Install PostgreSQL if needed
# macOS: brew install postgresql
# Ubuntu: sudo apt-get install postgresql

# Create database
createdb polymarket_bot

# Run migrations (TODO)
# alembic upgrade head
```

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# IMPORTANT: Get your Polymarket private key from your wallet
nano .env
```

Required configuration:
- `POLYMARKET_PRIVATE_KEY`: Your wallet private key
- `POLYMARKET_FUNDER_ADDRESS`: Your wallet address
- `DATABASE_URL`: PostgreSQL connection string

Optional but recommended:
- News API keys (CryptoNews, CoinFeeds, Twitter)
- Telegram bot for notifications

### 4. Run in Paper Trading Mode

```bash
# ALWAYS start in paper trading mode for testing
PAPER_TRADING=true python src/main.py
```

## Project Structure

```
hand-bot/
├── src/
│   ├── config.py              # Configuration management
│   ├── main.py                # Entry point
│   ├── core/
│   │   ├── strategy.py        # Trading strategy logic
│   │   └── risk_manager.py    # Risk & position management
│   ├── news/
│   │   └── news_analyzer.py   # News monitoring & analysis
│   ├── database/
│   │   └── models.py          # SQLAlchemy models
│   └── dashboard/
│       └── api.py             # FastAPI dashboard
├── tests/                     # Unit tests (TODO)
├── logs/                      # Application logs
└── requirements.txt           # Python dependencies
```

## Trading Strategy

### Entry Criteria (All must be true)

1. **Market Confidence** >= 80%
2. **Time Remaining**: Between 1-3 minutes
3. **Price Spread**: Bitcoin >= $30 above/below target
4. **Consistency Check**: Price direction matches odds direction
5. **No News Pause**: No major news in last 5 minutes
6. **Risk Limits**: Not exceeded max consecutive losses

### Exit Criteria

- **Default**: Hold until market expiry
- **Profit Lock** (optional): Sell early if probability reaches 92%+

### Risk Management

- **Position Size**: Max 5% of balance per trade
- **Loss Limit**: Pause after 3 consecutive losses for 30 minutes
- **Balance Growth**: Recalculate position sizes after every 25% growth

## Configuration

All settings can be configured via environment variables or `.env` file:

### Trading Settings

```bash
MIN_CONFIDENCE=0.80              # Minimum confidence to enter (50-99%)
MIN_TIME_REMAINING_SECONDS=60    # Minimum time left (30+)
MAX_TIME_REMAINING_SECONDS=180   # Maximum time left (≤300)
MIN_SPREAD_ABOVE_TARGET_USD=30.0 # Minimum price spread ($10+)
MAX_POSITION_PCT=0.05            # Max position size (1-20% of balance)
PROFIT_LOCK_ENABLED=true         # Enable profit lock
PROFIT_LOCK_THRESHOLD=0.92       # Profit lock threshold (85-99%)
```

### News Settings

```bash
PAUSE_ON_MAJOR_NEWS=true
NEWS_PAUSE_DURATION_SECONDS=300  # 5 minutes
```

## Development Status

### ✅ Completed

- Core project structure
- Configuration management
- Trading strategy logic
- Risk management
- News analyzer
- Database models
- Dashboard API skeleton

### 🚧 TODO

- [ ] Polymarket client integration
- [ ] Market scanner implementation
- [ ] Order executor
- [ ] WebSocket price feed
- [ ] News API integrations (CryptoNews, CoinFeeds, Twitter)
- [ ] Database repository layer
- [ ] Dashboard frontend (React)
- [ ] Unit tests
- [ ] Integration tests
- [ ] Backtesting framework
- [ ] Docker deployment

## Safety & Security

### Critical Warnings

1. **NEVER commit your private key to git**
2. **ALWAYS start with paper trading mode**
3. **Geographic restrictions**: Polymarket may not be available in all countries
4. **This is NOT financial advice**: Use at your own risk
5. **Only trade with money you can afford to lose**

### Best Practices

- Test thoroughly in paper trading mode (minimum 100 trades)
- Start with small position sizes
- Monitor the bot closely for the first few days
- Set up Telegram notifications
- Review daily statistics regularly
- Keep your dependencies updated

## Testing

```bash
# Run all tests (TODO)
pytest tests/ -v

# Run with coverage (TODO)
pytest tests/ --cov=src --cov-report=html

# Run specific test file (TODO)
pytest tests/test_strategy.py -v
```

## Deployment (TODO)

```bash
# Using Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f bot

# Stop
docker-compose down
```

## Monitoring

Logs are written to:
- Console (stdout)
- `logs/bot_YYYYMMDD.log`

Use the dashboard (when implemented) to monitor:
- Real-time P&L
- Win rate
- Current positions
- Recent trades
- News events

## Contributing

This is a personal trading bot project. Feel free to fork and adapt for your own use.

## Disclaimer

This bot is provided as-is for educational purposes. Cryptocurrency trading involves substantial risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built with [py-clob-client](https://github.com/Polymarket/py-clob-client)
- Inspired by the Polymarket trading community

## Support

For issues or questions:
1. Check the logs in `logs/`
2. Review configuration in `.env`
3. Ensure all dependencies are installed
4. Verify Polymarket API is accessible

## Roadmap

### Phase 1: Core Infrastructure (Current)
- ✅ Project structure
- ✅ Configuration
- ✅ Core modules

### Phase 2: Integration (Next)
- Polymarket API integration
- Market scanning
- Order execution

### Phase 3: Intelligence
- News monitoring
- Knowledge base
- Pattern learning

### Phase 4: Dashboard
- React frontend
- Real-time updates
- Settings management

### Phase 5: Production
- Docker deployment
- Monitoring & alerts
- Performance optimization
