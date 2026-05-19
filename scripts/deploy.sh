#!/usr/bin/env bash
# First-time deploy of Onlenco to onlenco.academy.
#
# Run as a non-root user with sudo on a fresh Ubuntu/Debian server.
# Domain DNS must already point onlenco.academy and www.onlenco.academy
# at this server (187.127.86.111).

set -euo pipefail

# --- Settings (override via environment) ---
APP_USER="${APP_USER:-onlenco}"
APP_DIR="${APP_DIR:-/opt/onlenco}"
REPO_URL="${REPO_URL:?Set REPO_URL to your git remote, e.g. git@github.com:you/onlenco.git}"

echo "==> [1/8] Install OS deps"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg git ufw

echo "==> [2/8] Install Docker (skip if already installed)"
if ! command -v docker >/dev/null; then
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") $(lsb_release -cs) stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

echo "==> [3/8] Open firewall (22, 80, 443)"
sudo ufw allow OpenSSH || true
sudo ufw allow 80/tcp || true
sudo ufw allow 443/tcp || true
yes | sudo ufw enable || true

echo "==> [4/8] Create app user + directory"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
    sudo useradd -m -s /bin/bash "$APP_USER"
    sudo usermod -aG docker "$APP_USER"
fi
sudo mkdir -p "$APP_DIR"
sudo chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

echo "==> [5/8] Clone or update repo"
if [ ! -d "$APP_DIR/.git" ]; then
    sudo -u "$APP_USER" git clone "$REPO_URL" "$APP_DIR"
else
    sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
fi

cd "$APP_DIR"

if [ ! -f .env ]; then
    echo "==> [6/8] Bootstrapping .env from .env.production.example"
    sudo -u "$APP_USER" cp .env.production.example .env
    echo "EDIT $APP_DIR/.env now (fill SECRET_KEY, POSTGRES_PASSWORD, EMAIL_*, AI_API_KEY)"
    echo "Then re-run this script."
    exit 0
fi

echo "==> [7/8] Build + start containers"
sudo -u "$APP_USER" docker compose -f docker-compose.yml -f docker-compose.deploy.yml \
    pull caddy db redis || true
sudo -u "$APP_USER" docker compose -f docker-compose.yml -f docker-compose.deploy.yml \
    up -d --build

echo "==> [8/8] Migrate + seed"
sudo -u "$APP_USER" docker compose exec -T web python manage.py migrate
sudo -u "$APP_USER" docker compose exec -T web python manage.py collectstatic --noinput

# Idempotent seeds — safe to run on every deploy.
for cmd in \
    seed_role_groups \
    seed_course_levels \
    seed_learning_core \
    seed_achievements \
    seed_dictionary \
    seed_books \
    seed_exam_blueprints \
    seed_placement_questions \
    ; do
    sudo -u "$APP_USER" docker compose exec -T web python manage.py "$cmd" || true
done

echo
echo "Deploy complete. Visit https://onlenco.academy/"
echo "Create the first admin:"
echo "    docker compose exec -it web python manage.py createsuperuser"
echo "Optional: enrol an admin TOTP device after first admin login at"
echo "    /admin/otp_totp/totpdevice/add/"
