import asyncio
import aiohttp
import time
import hmac
import hashlib
import base64
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple, Dict, Optional
from logger import setup_logger
from config import (
    BINANCE_API_KEY, BINANCE_API_SECRET,
    KRAKEN_API_KEY, KRAKEN_API_SECRET,
    PAPER_TRADING
)

logger = setup_logger("exchange_client")

@dataclass
class OrderBook:
    exchange: str
    symbol: str
    timestamp: datetime
    bids: List[Tuple[float, float]]  # (price, quantity)
    asks: List[Tuple[float, float]]
    best_bid: float
    best_ask: float

@dataclass
class OrderResult:
    order_id: str
    exchange: str
    side: str                  # 'buy' or 'sell'
    quantity: float
    price: float
    status: str                # 'open', 'filled', 'partially_filled', 'cancelled', 'rejected'
    filled_quantity: float
    timestamp: datetime

@dataclass
class Trade:
    exchange: str
    symbol: str
    price: float
    quantity: float
    side: str
    timestamp: datetime

class ExchangeClient:
    def __init__(self):
        self.binance_base_url = "https://api.binance.com"
        self.kraken_base_url = "https://api.kraken.com"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_binance_signature(self, params: Dict) -> str:
        query_string = urllib.parse.urlencode(params)
        return hmac.new(
            BINANCE_API_SECRET.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _get_kraken_signature(self, urlpath: str, data: Dict) -> str:
        post_data = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + post_data).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        signature = hmac.new(
            base64.b64decode(KRAKEN_API_SECRET),
            message,
            hashlib.sha512
        )
        return base64.b64encode(signature.digest()).decode()

    async def get_order_book(self, exchange: str, symbol: str, limit: int = 20) -> OrderBook:
        if exchange.lower() == "binance":
            url = f"{self.binance_base_url}/api/v3/depth"
            params = {"symbol": symbol, "limit": limit}
            async with self.session.get(url, params=params) as resp:
                data = await resp.json()
                bids = [(float(b[0]), float(b[1])) for b in data['bids']]
                asks = [(float(a[0]), float(a[1])) for a in data['asks']]
                return OrderBook(
                    exchange="Binance",
                    symbol=symbol,
                    timestamp=datetime.now(),
                    bids=bids,
                    asks=asks,
                    best_bid=bids[0][0] if bids else 0.0,
                    best_ask=asks[0][0] if asks else 0.0
                )
        elif exchange.lower() == "kraken":
            url = f"{self.kraken_base_url}/0/public/Depth"
            # Kraken uses different symbol names, but let's assume symbol is already mapped if needed
            params = {"pair": symbol, "count": limit}
            async with self.session.get(url, params=params) as resp:
                data = await resp.json()
                if data.get('error'):
                    raise Exception(f"Kraken API error: {data['error']}")
                
                # Kraken returns data keyed by the symbol name
                pair_data = list(data['result'].values())[0]
                bids = [(float(b[0]), float(b[1])) for b in pair_data['bids']]
                asks = [(float(a[0]), float(a[1])) for a in pair_data['asks']]
                return OrderBook(
                    exchange="Kraken",
                    symbol=symbol,
                    timestamp=datetime.now(),
                    bids=bids,
                    asks=asks,
                    best_bid=bids[0][0] if bids else 0.0,
                    best_ask=asks[0][0] if asks else 0.0
                )
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

    async def get_account_balance(self, exchange: str) -> Dict[str, float]:
        if PAPER_TRADING:
            # Return healthy mock balances for simulation
            return {"BTC": 1.0, "USDT": 10000.0, "ETH": 10.0}

        if exchange.lower() == "binance":
            url = f"{self.binance_base_url}/api/v3/account"
            params = {"timestamp": int(time.time() * 1000)}
            params["signature"] = self._get_binance_signature(params)
            headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
            async with self.session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()
                balances = {}
                for b in data.get('balances', []):
                    free = float(b['free'])
                    locked = float(b['locked'])
                    if free > 0 or locked > 0:
                        balances[b['asset']] = free + locked
                return balances
        elif exchange.lower() == "kraken":
            urlpath = "/0/private/Balance"
            url = f"{self.kraken_base_url}{urlpath}"
            data = {"nonce": int(time.time() * 1000)}
            headers = {
                "API-Key": KRAKEN_API_KEY,
                "API-Sign": self._get_kraken_signature(urlpath, data)
            }
            async with self.session.post(url, data=data, headers=headers) as resp:
                data = await resp.json()
                if data.get('error'):
                    raise Exception(f"Kraken API error: {data['error']}")
                return {asset: float(val) for asset, val in data['result'].items() if float(val) > 0}
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

    async def place_buy_order(self, exchange: str, symbol: str, quantity: float, price: float) -> OrderResult:
        return await self._place_order(exchange, symbol, "BUY", quantity, price)

    async def place_sell_order(self, exchange: str, symbol: str, quantity: float, price: float) -> OrderResult:
        return await self._place_order(exchange, symbol, "SELL", quantity, price)

    async def _place_order(self, exchange: str, symbol: str, side: str, quantity: float, price: float) -> OrderResult:
        if PAPER_TRADING:
            logger.info(f"[SIMULATION] {side} {quantity} {symbol} @ {price} on {exchange}")
            return OrderResult(
                order_id=f"sim_{int(time.time())}",
                exchange=exchange,
                side=side.lower(),
                quantity=quantity,
                price=price,
                status="filled", # Assume 100% fill for PoC
                filled_quantity=quantity,
                timestamp=datetime.now()
            )

        if exchange.lower() == "binance":
            url = f"{self.binance_base_url}/api/v3/order"
            params = {
                "symbol": symbol,
                "side": side,
                "type": "LIMIT",
                "timeInForce": "GTC",
                "quantity": f"{quantity:.8f}",
                "price": f"{price:.2f}",
                "timestamp": int(time.time() * 1000)
            }
            params["signature"] = self._get_binance_signature(params)
            headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
            async with self.session.post(url, params=params, headers=headers) as resp:
                data = await resp.json()
                return OrderResult(
                    order_id=str(data.get('orderId')),
                    exchange="Binance",
                    side=side.lower(),
                    quantity=float(data.get('origQty', 0)),
                    price=float(data.get('price', 0)),
                    status=data.get('status', 'rejected').lower(),
                    filled_quantity=float(data.get('executedQty', 0)),
                    timestamp=datetime.now()
                )
        elif exchange.lower() == "kraken":
            urlpath = "/0/private/AddOrder"
            url = f"{self.kraken_base_url}{urlpath}"
            data = {
                "nonce": int(time.time() * 1000),
                "pair": symbol,
                "type": side.lower(),
                "ordertype": "limit",
                "price": f"{price:.2f}",
                "volume": f"{quantity:.8f}"
            }
            headers = {
                "API-Key": KRAKEN_API_KEY,
                "API-Sign": self._get_kraken_signature(urlpath, data)
            }
            async with self.session.post(url, data=data, headers=headers) as resp:
                data = await resp.json()
                if data.get('error'):
                    logger.error(f"Kraken order error: {data['error']}")
                    status = "rejected"
                    order_id = ""
                else:
                    status = "open" # Kraken AddOrder returns txid
                    order_id = data['result']['txid'][0]
                
                return OrderResult(
                    order_id=order_id,
                    exchange="Kraken",
                    side=side.lower(),
                    quantity=quantity,
                    price=price,
                    status=status,
                    filled_quantity=0.0, # Initial
                    timestamp=datetime.now()
                )
        return None

    async def cancel_order(self, exchange: str, symbol: str, order_id: str) -> bool:
        if PAPER_TRADING:
            return True

        if exchange.lower() == "binance":
            url = f"{self.binance_base_url}/api/v3/order"
            params = {
                "symbol": symbol,
                "orderId": order_id,
                "timestamp": int(time.time() * 1000)
            }
            params["signature"] = self._get_binance_signature(params)
            headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
            async with self.session.delete(url, params=params, headers=headers) as resp:
                data = await resp.json()
                return data.get('status') == 'CANCELED'
        elif exchange.lower() == "kraken":
            urlpath = "/0/private/CancelOrder"
            url = f"{self.kraken_base_url}{urlpath}"
            data = {
                "nonce": int(time.time() * 1000),
                "txid": order_id
            }
            headers = {
                "API-Key": KRAKEN_API_KEY,
                "API-Sign": self._get_kraken_signature(urlpath, data)
            }
            async with self.session.post(url, data=data, headers=headers) as resp:
                data = await resp.json()
                return not data.get('error')
        return False

    async def get_recent_trades(self, exchange: str, symbol: str, limit: int = 100) -> List[Trade]:
        if exchange.lower() == "binance":
            url = f"{self.binance_base_url}/api/v3/trades"
            params = {"symbol": symbol, "limit": limit}
            async with self.session.get(url, params=params) as resp:
                data = await resp.json()
                return [Trade(
                    exchange="Binance",
                    symbol=symbol,
                    price=float(t['price']),
                    quantity=float(t['qty']),
                    side="unknown", # Binance trades don't explicitly say buy/sell in this endpoint
                    timestamp=datetime.fromtimestamp(t['time'] / 1000)
                ) for t in data]
        elif exchange.lower() == "kraken":
            url = f"{self.kraken_base_url}/0/public/Trades"
            params = {"pair": symbol}
            async with self.session.get(url, params=params) as resp:
                data = await resp.json()
                pair_data = list(data['result'].values())[0]
                return [Trade(
                    exchange="Kraken",
                    symbol=symbol,
                    price=float(t[0]),
                    quantity=float(t[1]),
                    side="buy" if t[3] == "b" else "sell",
                    timestamp=datetime.fromtimestamp(t[2])
                ) for t in pair_data[-limit:]]
        return []

    async def get_trading_fees(self, exchange: str) -> Dict[str, float]:
        # For Phase 1, we can return defaults from config or fetch if needed
        # Binance and Kraken have complex tier systems, usually 0.1% for Binance and 0.26% for Kraken
        if exchange.lower() == "binance":
            return {"maker": 0.001, "taker": 0.001}
        elif exchange.lower() == "kraken":
            return {"maker": 0.0016, "taker": 0.0026}
        return {"maker": 0.002, "taker": 0.002}

async def test_client():
    from config import SYMBOL_BINANCE, SYMBOL_KRAKEN
    async with ExchangeClient() as client:
        print("Fetching Binance Order Book...")
        try:
            binance_book = await client.get_order_book("Binance", SYMBOL_BINANCE)
            print(f"Binance Best Bid: {binance_book.best_bid}, Best Ask: {binance_book.best_ask}")
        except Exception as e:
            print(f"Binance Error: {e}")

        print("\nFetching Kraken Order Book...")
        try:
            kraken_book = await client.get_order_book("Kraken", SYMBOL_KRAKEN)
            print(f"Kraken Best Bid: {kraken_book.best_bid}, Best Ask: {kraken_book.best_ask}")
        except Exception as e:
            print(f"Kraken Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_client())
