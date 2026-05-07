"""
Lightglow Optimized Strategy - Real-time IBKR Paper Trading

This script connects to IBKR and calculates Premium/Discount signals in real-time
based on live 1-minute bar data.

Strategy Parameters:
- Lookback: 100 bars
- Premium: 0.95 (95%)
- Discount: 0.05 (5%)
- Exit: 2 bars (2 minutes)
- ATR Filter: > 8.0
- Time Filter: NY Kill Zone (8:30-11:30, 13:30-16:00 EST)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from ib_insync import IB, Future, util

from tradingagents.config.env import load_project_env


class LightglowRealtimeTrader:
    """Real-time Lightglow strategy trader using IBKR live data."""

    def __init__(
        self,
        symbol: str = "MNQ",
        contract_month: str = "202606",
        lookback: int = 100,
        premium_threshold: float = 0.95,
        discount_threshold: float = 0.05,
        atr_length: int = 14,
        atr_threshold: float = 8.0,
        exit_bars: int = 2,
        max_position: int = 1,
        dry_run: bool = True,
    ):
        self.symbol = symbol
        self.contract_month = contract_month
        self.lookback = lookback
        self.premium_threshold = premium_threshold
        self.discount_threshold = discount_threshold
        self.atr_length = atr_length
        self.atr_threshold = atr_threshold
        self.exit_bars = exit_bars
        self.max_position = max_position
        self.dry_run = dry_run

        # Data storage
        self.bars = deque(maxlen=lookback + atr_length)  # Store enough for calculations
        self.position = 0
        self.entry_bar_count = 0
        self.entry_price = None
        self.entry_time = None

        # IBKR connection
        self.ib = IB()
        self.contract = None

    def connect(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        """Connect to IBKR TWS/Gateway."""
        self.ib.connect(host, port, clientId=client_id)
        print(f"✅ Connected to IBKR at {host}:{port}")

        # Request delayed/frozen market data (available for paper accounts)
        # Type 3 = Delayed (15-20 min delay)
        # Type 4 = Delayed frozen
        self.ib.reqMarketDataType(4)  # Use frozen delayed data
        print(f"✅ Requested delayed frozen market data (available for paper accounts)")

        # Create contract
        self.contract = Future(self.symbol, self.contract_month, "CME")
        self.ib.qualifyContracts(self.contract)
        print(f"✅ Contract qualified: {self.contract}")

    def is_kill_zone(self, dt: datetime) -> bool:
        """Check if current time is in NY Kill Zone."""
        # Convert to EST (UTC-5)
        hour_utc = dt.hour
        minute_utc = dt.minute

        # NY AM: 8:30-11:30 EST (13:30-16:30 UTC)
        ny_am = (hour_utc == 13 and minute_utc >= 30) or (14 <= hour_utc < 16) or (hour_utc == 16 and minute_utc <= 30)

        # NY PM: 13:30-16:00 EST (18:30-21:00 UTC)
        ny_pm = (hour_utc == 18 and minute_utc >= 30) or (19 <= hour_utc < 21)

        return ny_am or ny_pm

    def calculate_atr(self) -> float:
        """Calculate ATR from recent bars."""
        if len(self.bars) < self.atr_length + 1:
            return 0.0

        true_ranges = []
        bars_list = list(self.bars)

        for i in range(1, min(self.atr_length + 1, len(bars_list))):
            high = bars_list[i]["high"]
            low = bars_list[i]["low"]
            prev_close = bars_list[i - 1]["close"]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
            true_ranges.append(tr)

        return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

    def calculate_premium_discount(self) -> tuple[float, float, bool, bool]:
        """Calculate Premium/Discount levels and check if price is in zones."""
        if len(self.bars) < self.lookback:
            return 0.0, 0.0, False, False

        recent_bars = list(self.bars)[-self.lookback :]
        highs = [b["high"] for b in recent_bars]
        lows = [b["low"] for b in recent_bars]

        trailing_high = max(highs)
        trailing_low = min(lows)
        range_size = trailing_high - trailing_low

        premium_level = trailing_low + self.premium_threshold * range_size
        discount_level = trailing_low + self.discount_threshold * range_size

        current_close = self.bars[-1]["close"]
        in_premium = current_close > premium_level
        in_discount = current_close < discount_level

        return premium_level, discount_level, in_premium, in_discount

    def on_bar_update(self, bars, has_new_bar):
        """Callback when new bar data arrives."""
        if not has_new_bar:
            return

        bar = bars[-1]
        bar_dict = {
            "time": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        self.bars.append(bar_dict)

        print(f"\n📊 New Bar: {bar.date} | O:{bar.open} H:{bar.high} L:{bar.low} C:{bar.close}")

        # Check if we need to exit
        if self.position != 0:
            self.entry_bar_count += 1
            print(f"   Position: {self.position} | Bars in trade: {self.entry_bar_count}/{self.exit_bars}")

            if self.entry_bar_count >= self.exit_bars:
                self.exit_position(bar.close, "time_exit")
                return

        # Check for entry signals
        if self.position == 0 and len(self.bars) >= self.lookback:
            self.check_entry_signal(bar)

    def check_entry_signal(self, bar):
        """Check for entry signals."""
        # Calculate indicators
        atr = self.calculate_atr()
        premium_level, discount_level, in_premium, in_discount = self.calculate_premium_discount()

        # Check filters
        atr_filter = atr > self.atr_threshold
        time_filter = self.is_kill_zone(bar.date)

        print(f"   ATR: {atr:.2f} (threshold: {self.atr_threshold}) {'✅' if atr_filter else '❌'}")
        print(f"   Kill Zone: {'✅' if time_filter else '❌'}")
        print(f"   Premium: {premium_level:.2f} | In Premium: {'✅' if in_premium else '❌'}")
        print(f"   Discount: {discount_level:.2f} | In Discount: {'✅' if in_discount else '❌'}")

        # Entry logic
        if not atr_filter or not time_filter:
            return

        # Short in Premium
        if in_premium:
            print(f"🔴 SHORT SIGNAL at {bar.close}")
            self.enter_position(-1, bar.close, bar.date)

        # Long in Discount
        elif in_discount:
            print(f"🟢 LONG SIGNAL at {bar.close}")
            self.enter_position(1, bar.close, bar.date)

    def enter_position(self, direction: int, price: float, time: datetime):
        """Enter a position."""
        self.position = direction
        self.entry_price = price
        self.entry_time = time
        self.entry_bar_count = 0

        action = "BUY" if direction == 1 else "SELL"
        print(f"\n{'='*60}")
        print(f"{'🟢 ENTERING LONG' if direction == 1 else '🔴 ENTERING SHORT'}")
        print(f"Time: {time}")
        print(f"Price: {price}")
        print(f"Action: {action} {abs(direction)} {self.symbol}")
        print(f"Dry Run: {self.dry_run}")
        print(f"{'='*60}\n")

        if not self.dry_run:
            # Submit order to IBKR
            order = self.ib.placeOrder(
                self.contract,
                util.MarketOrder(action, abs(direction)),
            )
            print(f"✅ Order submitted: {order}")

    def exit_position(self, price: float, reason: str):
        """Exit current position."""
        if self.position == 0:
            return

        pnl_points = (price - self.entry_price) * self.position
        pnl_dollars = pnl_points * 20  # MNQ multiplier

        print(f"\n{'='*60}")
        print(f"⚪ EXITING POSITION")
        print(f"Entry: {self.entry_time} @ {self.entry_price}")
        print(f"Exit: {datetime.now(timezone.utc)} @ {price}")
        print(f"Reason: {reason}")
        print(f"PnL: {pnl_points:.2f} points (${pnl_dollars:.2f})")
        print(f"Dry Run: {self.dry_run}")
        print(f"{'='*60}\n")

        if not self.dry_run:
            # Submit closing order
            action = "SELL" if self.position > 0 else "BUY"
            order = self.ib.placeOrder(
                self.contract,
                util.MarketOrder(action, abs(self.position)),
            )
            print(f"✅ Exit order submitted: {order}")

        self.position = 0
        self.entry_price = None
        self.entry_time = None
        self.entry_bar_count = 0

    def run(self):
        """Start real-time trading."""
        print(f"\n{'='*60}")
        print(f"🚀 Starting Lightglow Real-time Trader")
        print(f"{'='*60}")
        print(f"Symbol: {self.symbol}")
        print(f"Contract: {self.contract_month}")
        print(f"Lookback: {self.lookback}")
        print(f"Premium: {self.premium_threshold}")
        print(f"Discount: {self.discount_threshold}")
        print(f"ATR Threshold: {self.atr_threshold}")
        print(f"Exit Bars: {self.exit_bars}")
        print(f"Dry Run: {self.dry_run}")
        print(f"{'='*60}\n")

        # First, load historical bars to initialize
        print("📥 Loading historical bars for initialization...")
        end_time = datetime.now()
        # Request smaller chunks to avoid timeout
        # IBKR limits: max 1 day for 1-min bars
        duration = "1 D"  # Just 1 day of 1-min bars

        historical_bars = self.ib.reqHistoricalData(
            self.contract,
            endDateTime=end_time,
            durationStr=duration,
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=False,
            formatDate=1,
            timeout=30,  # 30 second timeout
        )

        if historical_bars:
            # Take last N bars
            recent_bars = historical_bars[-(self.lookback + self.atr_length):]
            for bar in recent_bars:
                bar_dict = {
                    "time": bar.date,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                self.bars.append(bar_dict)
            print(f"✅ Loaded {len(self.bars)} historical bars")
        else:
            print("⚠️ No historical bars loaded, will wait for real-time data")

        # For Paper accounts, use polling mode directly
        # Real-time bars require market data subscription
        print("💡 Using polling mode (recommended for Paper accounts)")
        print("   Polling historical bars every 60 seconds...\n")

        last_bar_time = None
        if self.bars:
            last_bar_time = self.bars[-1]["time"]
            print(f"   Last bar loaded: {last_bar_time}")

        poll_count = 0
        while True:
            try:
                poll_count += 1
                print(f"📡 Poll #{poll_count}: Requesting latest bars...")

                # Request latest bars (last 1 hour to ensure we get data)
                latest_bars = self.ib.reqHistoricalData(
                    self.contract,
                    endDateTime="",
                    durationStr="3600 S",  # Last 1 hour
                    barSizeSetting="1 min",
                    whatToShow="TRADES",
                    useRTH=False,
                    formatDate=1,
                    timeout=10,
                )

                if latest_bars:
                    latest_bar = latest_bars[-1]
                    print(f"   Latest bar: {latest_bar.date} | O:{latest_bar.open} H:{latest_bar.high} L:{latest_bar.low} C:{latest_bar.close}")

                    # Check if this is a new bar
                    if last_bar_time is None or latest_bar.date != last_bar_time:
                        print(f"   ✅ New bar detected!")
                        self.on_bar_update([latest_bar], True)
                        last_bar_time = latest_bar.date
                    else:
                        print(f"   ⏸️  Same bar, waiting...")
                else:
                    print(f"   ⚠️  No bars returned (market may be closed)")

                print(f"   Sleeping 60 seconds...\n")
                self.ib.sleep(60)

            except KeyboardInterrupt:
                print("\n\n⚠️ Interrupted by user")
                break
            except Exception as e:
                print(f"❌ Error in polling loop: {e}")
                print(f"   Retrying in 60 seconds...\n")
                self.ib.sleep(60)

        # Keep running
        try:
            self.ib.run()
        except KeyboardInterrupt:
            print("\n\n⚠️ Interrupted by user")
            if self.position != 0:
                print(f"⚠️ WARNING: Still in position ({self.position})")
                print("   Please close manually or restart")

    def disconnect(self):
        """Disconnect from IBKR."""
        self.ib.disconnect()
        print("✅ Disconnected from IBKR")


def main() -> int:
    load_project_env()

    parser = argparse.ArgumentParser(description="Lightglow real-time IBKR paper trader")
    parser.add_argument("--symbol", default="MNQ", help="Trading symbol")
    parser.add_argument("--contract-month", default="202606", help="Contract month")
    parser.add_argument("--host", default="127.0.0.1", help="IBKR host")
    parser.add_argument("--port", type=int, default=7497, help="IBKR port")
    parser.add_argument("--client-id", type=int, default=None, help="IBKR client ID (random if not specified)")
    parser.add_argument("--lookback", type=int, default=100, help="Lookback period")
    parser.add_argument("--premium", type=float, default=0.95, help="Premium threshold")
    parser.add_argument("--discount", type=float, default=0.05, help="Discount threshold")
    parser.add_argument("--atr-length", type=int, default=14, help="ATR period")
    parser.add_argument("--atr-threshold", type=float, default=8.0, help="ATR threshold")
    parser.add_argument("--exit-bars", type=int, default=2, help="Exit after N bars")
    parser.add_argument("--max-position", type=int, default=1, help="Max position size")
    parser.add_argument("--submit", action="store_true", help="Submit real orders (not dry-run)")
    args = parser.parse_args()

    # Use random client ID if not specified
    if args.client_id is None:
        import random
        args.client_id = random.randint(100, 9999)
        print(f"Using random client ID: {args.client_id}")

    trader = LightglowRealtimeTrader(
        symbol=args.symbol,
        contract_month=args.contract_month,
        lookback=args.lookback,
        premium_threshold=args.premium,
        discount_threshold=args.discount,
        atr_length=args.atr_length,
        atr_threshold=args.atr_threshold,
        exit_bars=args.exit_bars,
        max_position=args.max_position,
        dry_run=not args.submit,
    )

    try:
        trader.connect(host=args.host, port=args.port, client_id=args.client_id)
        trader.run()
    except KeyboardInterrupt:
        print("\n⚠️ Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        trader.disconnect()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
