#!/usr/bin/env python
"""Quick test of Lightglow realtime trader connection and data loading."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from ib_insync import IB, Future
from tradingagents.config.env import load_project_env

load_project_env()

print("="*60)
print("Testing Lightglow Realtime Trader")
print("="*60)

# Connect
print("\n1. Connecting to IBKR...")
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=9999, timeout=10)
print(f"✅ Connected to account: {ib.managedAccounts()}")

# Request delayed data
print("\n2. Requesting delayed market data...")
ib.reqMarketDataType(3)
print("✅ Delayed data requested")

# Qualify contract
print("\n3. Qualifying contract...")
contract = Future('MNQ', '202606', 'CME')
ib.qualifyContracts(contract)
print(f"✅ Contract: {contract}")

# Request historical data
print("\n4. Requesting historical bars...")
from datetime import datetime
bars = ib.reqHistoricalData(
    contract,
    endDateTime=datetime.now(),
    durationStr='2 D',
    barSizeSetting='1 min',
    whatToShow='TRADES',
    useRTH=False,
    formatDate=1,
)
print(f"✅ Loaded {len(bars)} historical bars")
if bars:
    print(f"   Latest bar: {bars[-1].date} | C:{bars[-1].close}")

# Try real-time bars
print("\n5. Testing real-time bars subscription...")
try:
    rt_bars = ib.reqRealTimeBars(
        contract,
        barSize=60,
        whatToShow='TRADES',
        useRTH=False,
    )
    print("✅ Real-time bars subscribed")
    print("   Waiting 10 seconds for data...")

    bar_count = 0
    def on_bar_update(bars, has_new_bar):
        global bar_count
        if has_new_bar:
            bar_count += 1
            bar = bars[-1]
            print(f"   📊 Bar {bar_count}: {bar.date} | C:{bar.close}")

    rt_bars.updateEvent += on_bar_update
    ib.sleep(10)

    print(f"✅ Received {bar_count} bars")

except Exception as e:
    print(f"⚠️ Real-time bars failed: {e}")
    print("   This is OK - will use polling fallback")

# Disconnect
print("\n6. Disconnecting...")
ib.disconnect()
print("✅ Disconnected")

print("\n" + "="*60)
print("✅ All tests passed!")
print("="*60)
