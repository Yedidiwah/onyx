#!/bin/bash
cd /root/onyx
source venv/bin/activate

echo "=================================================="
echo "ONYX Yacht Deals Update"
echo "=================================================="

python -u skippercity_deals.py --json data/yachts.json || { echo "ERROR: Yacht data update failed."; exit 1; }

git add data/yachts.json

if git diff --cached --quiet; then
    echo "No change in yacht data - nothing to commit."
else
    git commit -m "Auto-update yacht deals from server" --quiet

    if git push origin main --quiet 2>/dev/null; then
        echo "Pushed successfully."
    else
        echo "Push rejected (remote moved) - pulling and retrying once..."
        if git pull origin main --no-edit --quiet && git push origin main --quiet; then
            echo "Pushed after pull."
        else
            echo "ERROR: Could not sync with remote - needs manual check."
        fi
    fi
fi

echo "=================================================="
echo "ONYX Yacht Deals update completed."
echo "=================================================="
