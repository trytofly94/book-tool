#!/bin/bash

# === CONFIGURATION VARIABLES ===
SESSION_NAME="book"
REPEAT_COUNT=6
TEST_FOLDER="/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"

# Base command messages (without test folder)
DEV_NEXT_ISSUE_BASE="/dev next issue"
PR_REVIEW_BASE="/pr-review the next pr"
DEV_IMPLEMENT_BASE="/dev implement necessary changes and then merge it! If there are issues that are too big to resolve now or not necessary for the current pr then create new issues and mark them with the appropriate priority"

# Dynamic test message that gets appended to commands
TEST_MSG=". Test on the books in this folder: $TEST_FOLDER"

# Complete command messages with test folder
DEV_NEXT_ISSUE_MSG="${DEV_NEXT_ISSUE_BASE}${TEST_MSG}"
PR_REVIEW_MSG="${PR_REVIEW_BASE}${TEST_MSG}"
DEV_IMPLEMENT_MSG="${DEV_IMPLEMENT_BASE}${TEST_MSG}"

# Sleep durations (in seconds)
CLEAR_SLEEP=5
DEV_SLEEP=2000      # 33min 20s
REVIEW_SLEEP=2000   # 33min 20s
IMPLEMENT_SLEEP=1000 # 16min 40s

# === HELPER FUNCTIONS ===
log_with_time() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

send_command() {
    local command="$1"
    log_with_time "Sending command: $command"
    tmux send-keys -t "$SESSION_NAME" "$command"
    tmux send-keys -t "$SESSION_NAME" C-m
}

sleep_with_progress() {
    local duration=$1
    local description="$2"
    local minutes=$((duration/60))
    local seconds=$((duration%60))
    
    log_with_time "Starting $description - Duration: ${minutes}m ${seconds}s"
    sleep "$duration"
    log_with_time "Completed $description"
}

# === MAIN WORKFLOW ===
log_with_time "Starting automated workflow"
log_with_time "Configuration:"
log_with_time "  Session: $SESSION_NAME"
log_with_time "  Cycles: $REPEAT_COUNT"
log_with_time "  Test Folder: $TEST_FOLDER"

for ((i=1; i<=REPEAT_COUNT; i++)); do
    log_with_time "=== Starting cycle $i of $REPEAT_COUNT ==="

    # Clear context
    log_with_time "Step 1/6: Clearing context"
    send_command "/clear"
    sleep_with_progress $CLEAR_SLEEP "context clear"

    # Move to next issue
    log_with_time "Step 2/6: Moving to next issue"
    send_command "$DEV_NEXT_ISSUE_MSG"
    sleep_with_progress $DEV_SLEEP "development work"

    # Clear context again
    log_with_time "Step 3/6: Clearing context"
    send_command "/clear"
    sleep_with_progress $CLEAR_SLEEP "context clear"

    # Review PR
    log_with_time "Step 4/6: Reviewing PR"
    send_command "$PR_REVIEW_MSG"
    sleep_with_progress $REVIEW_SLEEP "PR review"

    # Clear context before final step
    log_with_time "Step 5/6: Clearing context"
    send_command "/clear"
    sleep_with_progress $CLEAR_SLEEP "context clear"

    # Implement changes and merge
    log_with_time "Step 6/6: Implementing changes and merging"
    send_command "$DEV_IMPLEMENT_MSG"
    sleep_with_progress $IMPLEMENT_SLEEP "implementation and merge"

    log_with_time "=== Completed cycle $i of $REPEAT_COUNT ==="
    
    # Add a brief pause between cycles
    if [ $i -lt $REPEAT_COUNT ]; then
        log_with_time "Preparing for next cycle..."
        sleep 10
    fi
done

log_with_time "Workflow completed! All $REPEAT_COUNT cycles finished"
log_with_time "Total runtime: $((REPEAT_COUNT * (CLEAR_SLEEP*3 + DEV_SLEEP + REVIEW_SLEEP + IMPLEMENT_SLEEP + 10))) seconds"