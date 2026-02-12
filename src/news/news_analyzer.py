"""
Nieuws analyse module.
Monitort Bitcoin nieuws en triggert pauzes bij groot nieuws.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import asyncio
import logging

from src.config import settings


logger = logging.getLogger(__name__)


class NewsImpact(Enum):
    """Impact niveau van nieuws."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NewsItem:
    """Een nieuwsitem."""

    id: str
    title: str
    source: str
    url: str
    published_at: datetime

    # Analysis
    sentiment: Optional[str] = None  # "positive", "negative", "neutral"
    impact: NewsImpact = NewsImpact.LOW
    keywords_matched: list[str] = None

    # Market reaction (wordt later ingevuld)
    btc_price_at_publish: Optional[float] = None
    btc_price_after_5min: Optional[float] = None
    market_reaction: Optional[str] = None  # "as_expected", "opposite", "neutral"


class NewsAnalyzer:
    """
    Analyseert nieuws en bepaalt impact op trading.

    Verantwoordelijkheden:
    - Nieuws classificeren op impact
    - Pauze triggeren bij groot nieuws
    - Marktreactie loggen voor kennisdatabase
    """

    def __init__(self):
        self.major_keywords = settings.news.major_news_keywords
        self.pause_duration = settings.news.news_pause_duration_seconds

        # Recent nieuws cache (voorkom duplicaten)
        self._recent_news: dict[str, NewsItem] = {}
        self._cache_ttl = timedelta(hours=1)

        # Pause state
        self._is_paused = False
        self._pause_until: Optional[datetime] = None
        self._pause_trigger: Optional[NewsItem] = None

    def analyze_news(self, news_item: NewsItem) -> tuple[NewsImpact, list[str]]:
        """
        Analyseer een nieuwsitem en bepaal impact.

        Returns:
            (impact_level, matched_keywords)
        """
        title_lower = news_item.title.lower()
        matched = []

        for keyword in self.major_keywords:
            if keyword.lower() in title_lower:
                matched.append(keyword)

        # Bepaal impact op basis van aantal matches en specifieke keywords
        if any(kw in matched for kw in ["SEC", "ETF", "ban", "hack", "crash"]):
            impact = NewsImpact.CRITICAL
        elif len(matched) >= 2:
            impact = NewsImpact.HIGH
        elif len(matched) == 1:
            impact = NewsImpact.MEDIUM
        else:
            impact = NewsImpact.LOW

        news_item.impact = impact
        news_item.keywords_matched = matched

        return impact, matched

    def should_pause(self, news_item: NewsItem) -> bool:
        """
        Bepaal of trading gepauzeerd moet worden vanwege dit nieuws.

        Returns:
            True als pauze nodig is
        """
        # Skip als al gepauzeerd
        if self._is_paused:
            return False

        # Skip als we dit nieuws al gezien hebben
        if news_item.id in self._recent_news:
            return False

        # Analyseer
        impact, keywords = self.analyze_news(news_item)

        # Cache toevoegen
        self._recent_news[news_item.id] = news_item
        self._cleanup_cache()

        # Pause bij HIGH of CRITICAL impact
        should_pause = impact in [NewsImpact.HIGH, NewsImpact.CRITICAL]

        if should_pause:
            logger.warning(
                f"🚨 MAJOR NEWS DETECTED: {news_item.title}\n"
                f"   Impact: {impact.value}\n"
                f"   Keywords: {keywords}\n"
                f"   Source: {news_item.source}"
            )

        return should_pause

    def trigger_pause(self, news_item: NewsItem):
        """Trigger een nieuws-pause."""
        self._is_paused = True
        self._pause_until = datetime.utcnow() + timedelta(seconds=self.pause_duration)
        self._pause_trigger = news_item

        logger.info(
            f"⏸️ NEWS PAUSE TRIGGERED voor {self.pause_duration}s\n"
            f"   Trigger: {news_item.title}\n"
            f"   Hervat om: {self._pause_until}"
        )

    @property
    def is_paused(self) -> bool:
        """Check of er een nieuws-pause actief is."""
        if self._is_paused and datetime.utcnow() >= self._pause_until:
            self._end_pause()
        return self._is_paused

    def _end_pause(self):
        """Beëindig de pause en log marktreactie."""
        logger.info(f"▶️ NEWS PAUSE ENDED. Trigger was: {self._pause_trigger.title if self._pause_trigger else 'Unknown'}")

        self._is_paused = False
        self._pause_until = None
        self._pause_trigger = None

    def _cleanup_cache(self):
        """Verwijder oude items uit de cache."""
        cutoff = datetime.utcnow() - self._cache_ttl
        self._recent_news = {
            k: v for k, v in self._recent_news.items()
            if v.published_at > cutoff
        }

    async def record_market_reaction(
        self,
        news_item: NewsItem,
        btc_price_before: float,
        btc_price_after: float,
    ):
        """
        Registreer hoe de markt reageerde op nieuws.
        Dit wordt opgeslagen in de kennisdatabase.
        """
        news_item.btc_price_at_publish = btc_price_before
        news_item.btc_price_after_5min = btc_price_after

        price_change_pct = ((btc_price_after - btc_price_before) / btc_price_before) * 100

        # Bepaal of reactie was zoals verwacht
        if news_item.sentiment == "positive":
            if price_change_pct > 0.1:
                news_item.market_reaction = "as_expected"
            elif price_change_pct < -0.1:
                news_item.market_reaction = "opposite"
            else:
                news_item.market_reaction = "neutral"
        elif news_item.sentiment == "negative":
            if price_change_pct < -0.1:
                news_item.market_reaction = "as_expected"
            elif price_change_pct > 0.1:
                news_item.market_reaction = "opposite"
            else:
                news_item.market_reaction = "neutral"
        else:
            news_item.market_reaction = "neutral"

        logger.info(
            f"📊 Market reaction recorded:\n"
            f"   News: {news_item.title}\n"
            f"   Sentiment: {news_item.sentiment}\n"
            f"   Price change: {price_change_pct:+.2f}%\n"
            f"   Reaction: {news_item.market_reaction}"
        )

        return news_item
