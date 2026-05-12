#!/usr/bin/env bash
# Update an already-deployed Onlenco server to the latest main branch.
#
# Different from scripts/deploy.sh:
#   * Assumes Docker + the cloned repo already exist.
#   * Pulls latest code, rebuilds the image, runs migrations + collectstatic,
#     restarts containers with zero data loss.
#   * Idempotent — safe to re-run.
#
# Run as root (or via sudo) on the server:
#     sudo bash /opt/onlenco/scripts/update.sh
#
# Override APP_USER / APP_DIR / COMPOSE_FILES via env if you didn't use
# the defaults from deploy.sh.

set -euo pipefail

APP_USER="${APP_USER:-onlenco}"
APP_DIR="${APP_DIR:-/opt/onlenco}"
COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.deploy.yml}"
BRANCH="${BRANCH:-main}"

# --- App-user detection ------------------------------------------------
# When the dedicated app user exists, we sandbox file mutations to it
# (defence in depth — limits what a bug in this script could corrupt).
# When it doesn't (fresh server where deploy.sh wasn't used to bootstrap)
# we run everything as the current shell user — typically root via sudo.
if id "$APP_USER" >/dev/null 2>&1; then
    USE_APP_USER=1
else
    USE_APP_USER=0
    echo "    note: user '$APP_USER' not found — running as $(id -un)"
fi

run() {
    # Run a command from $APP_DIR. As $APP_USER when that user exists,
    # otherwise as the current user. Quote-friendly via bash -lc.
    if [ "$USE_APP_USER" = "1" ]; then
        sudo -u "$APP_USER" -- bash -lc "cd '$APP_DIR' && $*"
    else
        bash -lc "cd '$APP_DIR' && $*"
    fi
}

echo "==> [1/7] Sanity checks"
[ -d "$APP_DIR/.git" ] || { echo "ABORT: $APP_DIR is not a git checkout"; exit 1; }
[ -f "$APP_DIR/.env" ] || { echo "ABORT: $APP_DIR/.env missing — copy from .env.production.example"; exit 1; }
command -v docker >/dev/null || { echo "ABORT: docker is not installed"; exit 1; }

# Mark the checkout as a safe directory for git so root-owned trees
# don't trigger 'fatal: detected dubious ownership' when run by a
# different shell user. Idempotent — git deduplicates entries.
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

echo "==> [2/7] Backup the database before any migration runs"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$APP_DIR/backups"
# Create the dir + fix ownership BEFORE we try to write inside it. We're
# root (via sudo bash), so we can chown to the app user when one exists.
mkdir -p "$BACKUP_DIR"
if [ "$USE_APP_USER" = "1" ]; then
    chown -R "$APP_USER":"$APP_USER" "$BACKUP_DIR" 2>/dev/null || true
fi

# Best-effort backup — never blocks the update.
if run "docker compose $COMPOSE_FILES ps -q db 2>/dev/null" | grep -q .; then
    BACKUP_FILE="$BACKUP_DIR/db-$TS.sql"
    if run "docker compose $COMPOSE_FILES exec -T db \
            pg_dump -U \"\${POSTGRES_USER:-onlenco}\" \"\${POSTGRES_DB:-onlenco}\"" \
            > "$BACKUP_FILE" 2>/dev/null; then
        if [ -s "$BACKUP_FILE" ]; then
            if [ "$USE_APP_USER" = "1" ]; then
                chown "$APP_USER":"$APP_USER" "$BACKUP_FILE" 2>/dev/null || true
            fi
            echo "    backed up: $BACKUP_FILE ($(wc -c <"$BACKUP_FILE") bytes)"
        else
            echo "    note: pg_dump produced an empty file — db may be uninitialised"
            rm -f "$BACKUP_FILE"
        fi
    else
        echo "    WARN: pg_dump failed; continuing without a fresh backup"
    fi
else
    echo "    db container not running — backup skipped"
fi

echo "==> [3/7] Fetch + fast-forward $BRANCH"
run "git fetch origin '$BRANCH'"
LOCAL_HEAD="$(run "git rev-parse HEAD" | tr -d '[:space:]')"
REMOTE_HEAD="$(run "git rev-parse 'origin/$BRANCH'" | tr -d '[:space:]')"
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    echo "    already at $REMOTE_HEAD — nothing to pull"
else
    echo "    $LOCAL_HEAD  →  $REMOTE_HEAD"
    run "git merge --ff-only 'origin/$BRANCH'"
fi

echo "==> [4/7] Build image"
# We always rebuild after a pull. Python source + management commands +
# templates are baked into the image at `COPY . /app` build time — they
# do NOT live in a mounted volume, so a code-only commit must still
# trigger a rebuild. Docker layer caching keeps this cheap when
# requirements.txt is unchanged (only the COPY layer re-runs).
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ] && [ "${FORCE_BUILD:-0}" != "1" ]; then
    echo "    code unchanged since last run — skipping build"
else
    run "docker compose $COMPOSE_FILES build web cron"
fi

echo "==> [5/7] Restart containers"
run "docker compose $COMPOSE_FILES up -d"

echo "==> [6/7] Run migrations + collectstatic"
# Wait briefly for db readiness — first-time updates can race the
# Postgres container.
for i in 1 2 3 4 5 6 7 8 9 10; do
    if run "docker compose $COMPOSE_FILES exec -T db pg_isready -q -U \"\${POSTGRES_USER:-onlenco}\"" >/dev/null 2>&1; then
        break
    fi
    echo "    waiting for db ($i/10)…"
    sleep 2
done
run "docker compose $COMPOSE_FILES exec -T web python manage.py migrate --noinput"
run "docker compose $COMPOSE_FILES exec -T web python manage.py collectstatic --noinput"

echo "==> [7/7] Idempotent seeds"
# Don't swallow seed errors with -2>/dev/null any more — operators
# need to see when a seed command is missing or fails. We still allow
# the loop to continue past a single failure with `|| true`.
SEEDS=(
    seed_role_groups
    seed_course_levels
    seed_learning_core
    seed_achievements
    seed_dictionary
    seed_books
    seed_exam_blueprints
    seed_a0_audio_course
    import_a0_curriculum
    generate_a0_question_bank
)
SEED_SKIPPED=()
for cmd in "${SEEDS[@]}"; do
    echo "    --> $cmd"
    if ! run "docker compose $COMPOSE_FILES exec -T web python manage.py '$cmd'"; then
        SEED_SKIPPED+=("$cmd")
        echo "        (skipped — command unavailable or errored)"
    fi
done

echo
echo "Update complete."
if [ "${#SEED_SKIPPED[@]}" -gt 0 ]; then
    echo "Skipped seeds: ${SEED_SKIPPED[*]}"
fi
echo "Health check: curl -fsS https://sudaschool.academy/healthz/"
echo "Logs:         cd $APP_DIR && docker compose $COMPOSE_FILES logs -f web"
