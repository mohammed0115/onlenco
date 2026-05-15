#!/usr/bin/env bash
# Smart deploy for Onlenco — handles BOTH first-time app launch and
# subsequent updates from one entry point.
#
# Run as root (or via sudo) on the server:
#     sudo bash /opt/onlenco/scripts/update.sh
#
# Modes (auto-detected):
#   * first-deploy: containers missing OR DB not yet migrated. We build,
#     migrate from zero, seed, collectstatic, start, healthcheck.
#   * update:       stack already running with a migrated DB. We back up,
#     pull, build if code changed, migrate diffs, re-seed (idempotent),
#     collectstatic, restart, healthcheck.
#
# Prerequisites (run scripts/deploy.sh once on a fresh server first):
#   * Docker + compose plugin installed
#   * Git checkout in $APP_DIR
#   * .env populated from .env.production.example
#
# Tunables (env vars):
#   APP_USER       (default: onlenco)
#   APP_DIR        (default: /opt/onlenco)
#   COMPOSE_FILES  (default: -f docker-compose.yml -f docker-compose.deploy.yml)
#   BRANCH         (default: main)
#   HEALTHCHECK_URL (default: http://localhost/healthz/ on container network)
#   FORCE_BUILD    (default: 0) — set 1 to force image rebuild
#   SKIP_BACKUP    (default: 0) — set 1 to skip DB pg_dump
#   SKIP_SEEDS     (default: 0) — set 1 to skip idempotent seeds
#
# Exit codes:
#   0  success
#   2  bad environment (missing prerequisite)
#   3  git/pull failure
#   4  build failure
#   5  DB never became ready
#   6  migration drift detected (uncommitted model changes)
#   7  migrate failed (DB rolled back to backup snapshot location)
#   8  collectstatic failed
#   9  healthcheck failed after restart

set -uo pipefail

# === Settings ===========================================================
APP_USER="${APP_USER:-onlenco}"
APP_DIR="${APP_DIR:-/opt/onlenco}"
COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.deploy.yml}"
BRANCH="${BRANCH:-main}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"
FORCE_BUILD="${FORCE_BUILD:-0}"
SKIP_BACKUP="${SKIP_BACKUP:-0}"
SKIP_SEEDS="${SKIP_SEEDS:-0}"

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$APP_DIR/backups"
BACKUP_FILE=""   # populated if backup runs
MODE=""          # 'first-deploy' or 'update'
SEED_SKIPPED=()

# === Logging ============================================================
if [ -t 1 ]; then
    C_RED="\033[31m"; C_GREEN="\033[32m"; C_YELLOW="\033[33m"
    C_BLUE="\033[34m"; C_BOLD="\033[1m"; C_RESET="\033[0m"
else
    C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_BOLD=""; C_RESET=""
fi
log()  { printf "${C_BLUE}==>${C_RESET} ${C_BOLD}%s${C_RESET}\n" "$*"; }
ok()   { printf "    ${C_GREEN}✓${C_RESET} %s\n" "$*"; }
note() { printf "      %s\n" "$*"; }
warn() { printf "    ${C_YELLOW}!${C_RESET} %s\n" "$*"; }
err()  { printf "    ${C_RED}✗${C_RESET} %s\n" "$*" >&2; }

die() {
    # die <exit_code> <message>
    err "$2"
    print_recovery_hints "$1"
    exit "$1"
}

print_recovery_hints() {
    local code=$1
    echo
    printf "${C_BOLD}Diagnostics:${C_RESET}\n"
    if [ -n "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
        echo "  DB snapshot taken before this run:"
        echo "    $BACKUP_FILE"
        echo "  Restore (DESTRUCTIVE — will overwrite current DB):"
        echo "    cat $BACKUP_FILE | docker compose $COMPOSE_FILES exec -T db \\"
        echo "      psql -U \"\$POSTGRES_USER\" \"\$POSTGRES_DB\""
    fi
    echo "  Web logs:    cd $APP_DIR && docker compose $COMPOSE_FILES logs --tail=200 web"
    echo "  DB logs:     cd $APP_DIR && docker compose $COMPOSE_FILES logs --tail=200 db"
    case "$code" in
        2) echo "  Prerequisite missing — install Docker / create .env / clone repo first." ;;
        3) echo "  Git diverged — investigate with: git -C $APP_DIR status && git -C $APP_DIR log --oneline -5" ;;
        4) echo "  Build failed — try: cd $APP_DIR && docker compose $COMPOSE_FILES build --no-cache web" ;;
        5) echo "  DB never came up — check disk space, port conflict on 5432, or db logs above." ;;
        6) echo "  A developer forgot to commit a migration. Generate locally with:" ;
           echo "    python manage.py makemigrations && git add */migrations/*.py && commit + push" ;;
        7) echo "  Migration failed mid-way. Inspect django_migrations table:" ;
           echo "    docker compose $COMPOSE_FILES exec -T db psql -U \"\$POSTGRES_USER\" \"\$POSTGRES_DB\" -c '\\dt'" ;;
        9) echo "  Healthcheck failed — gunicorn may have failed to import settings. Tail web logs above." ;;
    esac
}

# === Helpers ============================================================
USE_APP_USER=0
if id "$APP_USER" >/dev/null 2>&1; then
    USE_APP_USER=1
else
    warn "User '$APP_USER' not found — running as $(id -un)."
fi

run() {
    # Run a shell command from $APP_DIR. As $APP_USER when that user
    # exists, otherwise as the current user.
    if [ "$USE_APP_USER" = "1" ]; then
        sudo -u "$APP_USER" -- bash -lc "cd '$APP_DIR' && $*"
    else
        bash -lc "cd '$APP_DIR' && $*"
    fi
}

dc() {
    # Wrapper for docker-compose with the right -f overlay flags.
    run "docker compose $COMPOSE_FILES $*"
}

dc_quiet() {
    # Same, but suppress stderr — for probes whose failure is expected.
    if [ "$USE_APP_USER" = "1" ]; then
        sudo -u "$APP_USER" -- bash -lc "cd '$APP_DIR' && docker compose $COMPOSE_FILES $* 2>/dev/null"
    else
        bash -lc "cd '$APP_DIR' && docker compose $COMPOSE_FILES $* 2>/dev/null"
    fi
}

# === [1/9] Sanity checks ================================================
log "[1/9] Sanity checks"
[ -d "$APP_DIR" ]       || die 2 "$APP_DIR does not exist. Run scripts/deploy.sh first."
[ -d "$APP_DIR/.git" ]  || die 2 "$APP_DIR is not a git checkout."
[ -f "$APP_DIR/.env" ]  || die 2 "$APP_DIR/.env is missing. Copy from .env.production.example and fill in secrets."
command -v docker >/dev/null || die 2 "docker is not installed. Run scripts/deploy.sh first."

# Mark the checkout as safe (root-owned tree, sudo'd commands).
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

# Validate the compose file parses BEFORE any docker mutation.
if ! dc "config -q" >/dev/null 2>&1; then
    die 2 "docker compose config rejected the file. Run: docker compose $COMPOSE_FILES config"
fi
ok "environment looks healthy"

# === [2/9] Detect deploy mode ===========================================
log "[2/9] Detect deploy mode"
detect_mode() {
    # No db container running? → first deploy of app stack.
    if ! dc_quiet "ps -q db" | grep -q .; then
        echo "first-deploy"; return
    fi
    # DB container exists but not accepting connections? → first deploy
    # (Docker just started it; nothing migrated yet).
    if ! dc_quiet "exec -T db pg_isready -q -U \"\${POSTGRES_USER:-onlenco}\"" ; then
        echo "first-deploy"; return
    fi
    # django_migrations table missing or empty? → first deploy.
    local row_count
    row_count="$(dc_quiet "exec -T db psql -U \"\${POSTGRES_USER:-onlenco}\" -d \"\${POSTGRES_DB:-onlenco}\" -tA -c \"SELECT COUNT(*) FROM django_migrations;\"" | tr -d '[:space:]' || true)"
    if [ -z "$row_count" ] || [ "$row_count" = "0" ]; then
        echo "first-deploy"; return
    fi
    echo "update"
}
MODE="$(detect_mode)"
ok "mode: $MODE"

# === [3/9] Backup database (update mode only) ===========================
log "[3/9] Backup database"
if [ "$MODE" = "first-deploy" ]; then
    note "first deploy — nothing to back up yet"
elif [ "$SKIP_BACKUP" = "1" ]; then
    warn "SKIP_BACKUP=1 — skipping pg_dump"
else
    mkdir -p "$BACKUP_DIR"
    if [ "$USE_APP_USER" = "1" ]; then
        chown -R "$APP_USER":"$APP_USER" "$BACKUP_DIR" 2>/dev/null || true
    fi
    BACKUP_FILE="$BACKUP_DIR/db-$TS.sql"
    if dc_quiet "exec -T db pg_dump -U \"\${POSTGRES_USER:-onlenco}\" \"\${POSTGRES_DB:-onlenco}\"" \
            > "$BACKUP_FILE"; then
        if [ -s "$BACKUP_FILE" ]; then
            if [ "$USE_APP_USER" = "1" ]; then
                chown "$APP_USER":"$APP_USER" "$BACKUP_FILE" 2>/dev/null || true
            fi
            ok "backup: $BACKUP_FILE ($(wc -c <"$BACKUP_FILE") bytes)"
            # Prune backups older than 14 days (keep disk under control).
            find "$BACKUP_DIR" -maxdepth 1 -name "db-*.sql" -type f -mtime +14 \
                -delete 2>/dev/null || true
        else
            warn "pg_dump produced an empty file — assuming uninitialised DB"
            rm -f "$BACKUP_FILE"; BACKUP_FILE=""
        fi
    else
        rm -f "$BACKUP_FILE"; BACKUP_FILE=""
        warn "pg_dump failed — continuing without a fresh backup"
    fi
fi

# === [4/9] Pull latest code =============================================
log "[4/9] Fetch + fast-forward $BRANCH"
LOCAL_HEAD_BEFORE="$(run "git rev-parse HEAD" | tr -d '[:space:]' || true)"
if ! run "git fetch origin '$BRANCH'"; then
    die 3 "git fetch failed — check network + remote credentials."
fi
LOCAL_HEAD="$(run "git rev-parse HEAD" | tr -d '[:space:]')"
REMOTE_HEAD="$(run "git rev-parse 'origin/$BRANCH'" | tr -d '[:space:]')"
if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
    ok "already at $REMOTE_HEAD"
else
    note "$LOCAL_HEAD  →  $REMOTE_HEAD"
    if ! run "git merge --ff-only 'origin/$BRANCH'"; then
        die 3 "fast-forward refused — branch diverged. Reconcile manually."
    fi
    ok "pulled $(run "git rev-list --count $LOCAL_HEAD..HEAD" | tr -d '[:space:]') new commit(s)"
fi

# === [5/9] Build image ==================================================
# We ALWAYS build by default. Docker layer caching makes this cheap when
# nothing changed (only the COPY layer revalidates). The previous
# "skip when HEAD unchanged" optimisation was a footgun: if an operator
# ran `git pull` outside the script, HEAD didn't move during this run
# but the running container was still on the OLD image, so
# `makemigrations --check` later in [7/9] would run against stale code
# and falsely complain about missing migrations. Opt out with SKIP_BUILD=1
# only when you've already built manually with the right context.
log "[5/9] Build image"
if [ "${SKIP_BUILD:-0}" = "1" ] && [ "$MODE" != "first-deploy" ]; then
    warn "SKIP_BUILD=1 — using existing image (you'd better know it matches the code on disk)"
else
    if ! dc "build web cron"; then
        die 4 "image build failed."
    fi
    ok "image built ($(date +%H:%M:%S))"
fi

# === [6/9] Start containers + wait for DB ===============================
# Two-phase start:
#   1. `up -d` brings up everything that's not running (db/redis/caddy).
#      If the freshly built web image differs from the running container,
#      compose will recreate web on its own here.
#   2. Force-recreate web + cron with --no-deps so that even when image
#      hashes happen to match (rare, but possible with a code-only edit
#      and BuildKit cache reuse), the app containers always restart from
#      the just-built image. db/redis/caddy stay untouched (no bounce).
log "[6/9] Start containers"
if ! dc "up -d"; then
    die 4 "docker compose up failed."
fi
if ! dc "up -d --force-recreate --no-deps web cron"; then
    die 4 "docker compose recreate of web/cron failed."
fi
ok "containers up — web/cron recreated from fresh image"

note "waiting for postgres readiness (up to 60s)…"
DB_READY=0
for i in $(seq 1 30); do
    if dc_quiet "exec -T db pg_isready -q -U \"\${POSTGRES_USER:-onlenco}\""; then
        DB_READY=1
        ok "postgres ready after ${i}×2s"
        break
    fi
    sleep 2
done
[ "$DB_READY" = "1" ] || die 5 "postgres never became ready."

# === [7/9] Migrations ===================================================
log "[7/9] Migrations"

# Pre-flight: are there model changes the developer forgot to materialise
# as a migration? Catch it BEFORE we corrupt prod schema state. The
# `--check` exit code is 0 (no changes) or 1 (changes pending).
note "checking for uncommitted model changes…"
if dc "exec -T web python manage.py makemigrations --check --dry-run"; then
    ok "no model/migration drift"
else
    err "Uncommitted model changes detected — aborting before migrate runs."
    die 6 "Run 'python manage.py makemigrations' locally, commit, redeploy."
fi

# Show the plan so operators can see what's about to apply.
note "pending plan:"
dc "exec -T web python manage.py showmigrations --plan" \
    | awk '/\[ \]/ { print "        " $0 }' || true

if ! dc "exec -T web python manage.py migrate --noinput"; then
    die 7 "migrate failed. Inspect 'django_migrations' table + web logs."
fi
ok "migrations applied"

# === [8/9] Collectstatic + idempotent seeds =============================
log "[8/9] Collectstatic + seeds"
if ! dc "exec -T web python manage.py collectstatic --noinput"; then
    die 8 "collectstatic failed."
fi
ok "static assets collected"

if [ "$SKIP_SEEDS" = "1" ]; then
    warn "SKIP_SEEDS=1 — skipping seeds"
else
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
    for cmd in "${SEEDS[@]}"; do
        note "→ $cmd"
        if ! dc "exec -T web python manage.py '$cmd'"; then
            SEED_SKIPPED+=("$cmd")
            warn "$cmd skipped (command unavailable or errored)"
        fi
    done
fi

# === [9/9] Restart web + healthcheck ====================================
log "[9/9] Restart web + healthcheck"
# `up -d` above started everything; here we replace the web container so
# new gunicorn workers pick up code/migrations cleanly. db/redis untouched.
if ! dc "up -d --no-deps web cron"; then
    die 9 "web restart failed."
fi
ok "web restarted"

# Healthcheck: prefer the container's own /healthz/, fall back to host curl.
note "running healthcheck…"
HEALTH_PASS=0
for i in $(seq 1 15); do
    if dc_quiet "exec -T web curl -fsS http://localhost:8000/healthz/" >/dev/null; then
        HEALTH_PASS=1
        ok "/healthz/ OK after ${i}×2s"
        break
    fi
    sleep 2
done
if [ "$HEALTH_PASS" = "0" ]; then
    die 9 "healthcheck never passed — gunicorn may be crashing on startup."
fi

# Optional external healthcheck (e.g. through Caddy/Cloudflare).
if [ -n "$HEALTHCHECK_URL" ]; then
    if curl -fsS --max-time 10 "$HEALTHCHECK_URL" >/dev/null 2>&1; then
        ok "external healthcheck $HEALTHCHECK_URL OK"
    else
        warn "external healthcheck $HEALTHCHECK_URL failed (container is healthy though)."
    fi
fi

# === Summary ============================================================
echo
printf "${C_GREEN}${C_BOLD}✓ Deploy complete${C_RESET}  (mode: %s)\n" "$MODE"
echo "    HEAD:     $LOCAL_HEAD"
if [ -n "$BACKUP_FILE" ]; then
    echo "    Backup:   $BACKUP_FILE"
fi
if [ "${#SEED_SKIPPED[@]}" -gt 0 ]; then
    echo "    Skipped seeds: ${SEED_SKIPPED[*]}"
fi
echo "    Logs:     cd $APP_DIR && docker compose $COMPOSE_FILES logs -f web"
echo "    Health:   curl -fsS https://onlenco.academy/healthz/"
