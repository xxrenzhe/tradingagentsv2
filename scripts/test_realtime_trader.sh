#!/bin/bash
# Lightglow Real-time Trader Test Script

set -e

echo "============================================================"
echo "🚀 Lightglow Real-time Trader Test"
echo "============================================================"
echo ""

# Activate virtual environment
source .venv/bin/activate

# Check IBKR connection
echo "📡 Checking IBKR connection..."
if nc -z localhost 7497 2>/dev/null; then
    echo "✅ IBKR TWS connected on port 7497"
else
    echo "❌ IBKR TWS not connected on port 7497"
    echo "   Please start IBKR TWS or Gateway first"
    exit 1
fi
echo ""

# Create logs directory
mkdir -p logs

# Generate log filename
LOG_FILE="logs/lightglow_realtime_$(date +%Y%m%d_%H%M%S).log"

echo "📝 Log file: $LOG_FILE"
echo ""

# Start trader
echo "🚀 Starting Lightglow Real-time Trader..."
echo "   Press Ctrl+C to stop"
echo ""

python scripts/run_lightglow_realtime_trader.py \
    --symbol MNQ \
    --contract-month 202606 \
    --lookback 100 \
    --premium 0.95 \
    --discount 0.05 \
    --atr-threshold 8.0 \
    --exit-bars 2 \
    2>&1 | tee "$LOG_FILE"

echo ""
echo "============================================================"
echo "✅ Trader stopped"
echo "📝 Log saved to: $LOG_FILE"
echo "============================================================"
