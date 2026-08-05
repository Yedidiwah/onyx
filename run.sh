#!/bin/bash
cd /root/onyx
source venv/bin/activate

echo "=================================================="
echo "ONYX Radar Full Update"
echo "=================================================="

echo "[1/4] Downloading current Villiers flights..."
python -u vfetche.py || { echo "ERROR: Villiers flight update failed."; exit 1; }

echo "[2/4] Creating website flights.json..."
python -u scripts/update_site.py || { echo "ERROR: Website flight data failed."; exit 1; }

echo "[3/4] Creating global airports.json..."
python -u scripts/build_airports_data.py || { echo "ERROR: Airport catalogue generation failed."; exit 1; }

echo "[4/4] Sending current flights to Telegram..."
python -u vtelegram.py || { echo "ERROR: Telegram processing failed."; exit 1; }

echo "=================================================="
echo "ONYX Radar update completed successfully."
echo "=================================================="

# Git Auto-Push
git add .
git commit -m "Auto-update flights data and telegram alerts from server"
git push origin main
