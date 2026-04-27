import asyncio
import time
from typing import Dict, Optional
from exchange_client import ExchangeClient, OrderBook
from logger import setup_logger

logger = setup_logger("order_book_monitor")

class OrderBookMonitor:
    def __init__(self, client: ExchangeClient):
        self.client = client
        self.cache: Dict[str, OrderBook] = {}
        self.cache_ttl_ms = 100  # 100ms cache as per requirement

    async def get_latest_book(self, exchange: str, symbol: str) -> OrderBook:
        cache_key = f"{exchange}_{symbol}"
        now = time.time() * 1000
        
        if cache_key in self.cache:
            cached_book = self.cache[cache_key]
            # Check if cache is still valid
            if (now - cached_book.timestamp.timestamp() * 1000) < self.cache_ttl_ms:
                return cached_book
        
        # Fetch fresh data
        book = await self.client.get_order_book(exchange, symbol)
        self.cache[cache_key] = book
        return book

    async def start_monitoring(self, pairs: list[tuple[str, str]], interval: float = 1.0):
        """
        Background task to keep the cache warm (optional for Phase 1).
        """
        while True:
            tasks = [self.get_latest_book(exchange, symbol) for exchange, symbol in pairs]
            await asyncio.gather(*tasks)
            await asyncio.sleep(interval)
