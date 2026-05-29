#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Attestplane Contributors
#
# Called by implement-planned-task.yml to start (or no-op if already running)
# an AutodevPipeline Temporal workflow for a given issue.
#
# Usage: trigger.sh <issue_number> <issue_title> <issue_body>

set -euo pipefail

ISSUE_NUMBER="${1:?issue_number required}"
ISSUE_TITLE="${2:?issue_title required}"
ISSUE_BODY="${3:?issue_body required}"
TEMPORAL_ADDRESS="${TEMPORAL_ADDRESS:-localhost:7233}"

INPUT_JSON=$(python3.11 -c "
import json, sys
print(json.dumps({
    'issue_number': int(sys.argv[1]),
    'issue_title':  sys.argv[2],
    'issue_body':   sys.argv[3],
}))" "$ISSUE_NUMBER" "$ISSUE_TITLE" "$ISSUE_BODY")

# --workflow-id makes this idempotent: duplicate issue events are no-ops
if temporal workflow start \
    --address        "${TEMPORAL_ADDRESS}" \
    --task-queue     "autodev" \
    --type           "AutodevPipeline" \
    --workflow-id    "autodev-issue-${ISSUE_NUMBER}" \
    --execution-timeout "2h" \
    --input          "${INPUT_JSON}" 2>&1; then
  echo "✅ Temporal workflow started for issue #${ISSUE_NUMBER}"
else
  echo "ℹ️  Workflow already running for issue #${ISSUE_NUMBER} (idempotent, skipping)"
fi
