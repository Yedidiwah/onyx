#!/bin/bash
cd /root/onyx
BEFORE=$(git rev-parse HEAD)

if ! git pull origin main --quiet --no-edit; then
    echo "$(date): git pull failed or conflicted - aborting merge, needs manual attention"
    git merge --abort 2>/dev/null
    exit 1
fi

AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" != "$AFTER" ]; then
    echo "$(date): Pulled new changes ($BEFORE -> $AFTER)"

    if git diff --name-only "$BEFORE" "$AFTER" | grep -qE "^(vlisten\.py|scripts/agent_brain\.py)$"; then
        echo "$(date): Bot code changed - restarting onyx-listener.service"
        systemctl restart onyx-listener.service
    fi
fi
