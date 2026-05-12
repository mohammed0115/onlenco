#!/usr/bin/env bash
# Update an already-deployed Onlenco server to the latest main branch.
#
# Different from scripts/deploy.sh:
#   * Assumes Docker + the app user + the cloned repo already exist.
#   * Pulls latest code, rebuilds the image, runs migrations + collectstatic,
#     restarts containers with zero data loss.
#   * Idempotent — safe to re-run.
#
# Run as root or via sudo on the server:
#     sudo bash /opt/onlenco/scripts/update.sh
#
# Override APP_USER / APP_DIR / COMPOSE_FILES via env if you didn't use
# the defaults from deploy.sh.

set -euo pipefail

APP_USER="${APP_USER:-onlenco}"
APP_DIR="${APP_DIR:-/opt/onlenco}"
COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.deploy.yml}"
BRANCH="${BRANCH:-main}"

run_as_app() {
    # Run a command as the app user from $APP_DIR.
    sudo -u "$APP_USER" -- bash -lc "cd '$APP_DIR' && $*"
}

echo "==> [1/7] Sanity checks"
[ -d "$APP_DIR/.git" ] || { echo "ABORT: $APP_DIR is not a git checkout"; exit 1; }
[ -f "$APP_DIR/.env" ] || { echo "ABORT: $APP_DIR/.env missing — copy from .env.production.example"; exit 1; }
command -v docker >/dev/null || { echo "ABORT: docker is not installed"; exit 1; }

echo "==> [2/7] Backup the database before any migration runs"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$APP_DIR/backups"
sudo -u "$APP_USER" mkdir -p "$BACKUP_DIR"
# Best-effort. If the DB container isn't up yet (first update), skip
# silently — there is nothing to back up.
if run_as_app "docker compose $COMPOSE_FILES ps -q db" | grep -q .; then
    run_as_app "docker compose $COMPOSE_FILES exec -T db \
        pg_dump -U \${POSTGRES_USER:-onlenco} \${POSTGRES_DB:-onlenco}" \
        | sudo -u "$APP_USER" tee "$BACKUP_DIR/db-$TS.sql" >/dev/null
    echo "    backed up: $BACKUP_DIR/db-$TS.sql"
else
    echo "    db container not running — backup skipped"
fi

echo "==> [3/7] Fetch + fast-forward $BRANCH"
run_as_app "git fetch origin $BRANCH"
LOCAL_HEAD="$(run_as_app "git rev-parse HEAD")"
REMOTE_HEAD="$(run_as_app "git rev-parse origin/$BRANCH")"
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    echo "    already at $REMOTE_HEAD — nothing to pull"
else
    echo "    $LOCAL_HEAD  →  $REMOTE_HEAD"
    run_as_app "git merge --ff-only origin/$BRANCH"
fi

echo "==> [4/7] Build image (only if Dockerfile or requirements changed)"
NEED_BUILD=0
if run_as_app "git diff --name-only '$LOCAL_HEAD' HEAD 2>/dev/null" | \
    grep -E '^(Dockerfile|requirements\.txt|requirements-.*\.txt)$' >/dev/null; then
    NEED_BUILD=1
fi
# Force build when migrations changed too — they ship inside the image.
if run_as_app "git diff --name-only '$LOCAL_HEAD' HEAD 2>/dev/null" | \
    grep -E 'migrations/' >/dev/null; then
    NEED_BUILD=1
fi
if [ "$NEED_BUILD" = "1" ] || [ "${FORCE_BUILD:-0}" = "1" ]; then
    run_as_app "docker compose $COMPOSE_FILES build web cron"
else
    echo "    no Dockerfile / requirements / migration changes — skipping build"
fi

echo "==> [5/7] Restart containers"
run_as_app "docker compose $COMPOSE_FILES up -d"

echo "==> [6/7] Run migrations + collectstatic"
run_as_app "docker compose $COMPOSE_FILES exec -T web python manage.py migrate --noinput"
run_as_app "docker compose $COMPOSE_FILES exec -T web python manage.py collectstatic --noinput"

echo "==> [7/7] Idempotent seeds (best-effort, never blocks the update)"
for cmd in \
    seed_role_groups \
    seed_course_levels \
    seed_learning_core \
    seed_achievements \
    seed_dictionary \
    seed_books \
    seed_exam_blueprints \
    seed_a0_audio_course \
    import_a0_curriculum \
    generate_a0_question_bank \
    ; do
    if ! run_as_app "docker compose $COMPOSE_FILES exec -T web python manage.py $cmd" 2>/dev/null; then
        echo "    skipped: $cmd (command not present in this version)"
    fi
done

echo
echo "Update complete."
echo "Health check: curl -fsS https://sudaschool.academy/healthz/"
echo "Logs:         docker compose logs -f web   (run from $APP_DIR as $APP_USER)"
