#!/bin/sh
# Container entrypoint. Runs as root, makes the bind-mounted/named
# media volume writable for the unprivileged `onlenco` user (Docker
# creates fresh named volumes owned by root, shadowing the build-time
# chown), then drops privileges before exec'ing the real command.
set -e

if [ "$(id -u)" = "0" ]; then
    # Ensure /app/media exists and is writable by the `onlenco` user.
    # We can't trust a shallow top-level check: subdirectories like
    # `lessons/video/YYYY/MM/` get created lazily by Django on first
    # upload, and any leftover root-owned subdir (from an earlier image
    # build with a different UID, or a one-off `docker compose exec`
    # write as root) breaks subsequent uploads with a 500.
    #
    # `find ! -user onlenco -exec chown` is cheap on steady-state — the
    # filesystem walk reads inode metadata only and chown fires solely
    # on the misowned files. Self-heals after permission drift instead
    # of needing a manual `chown -R` after every incident.
    mkdir -p /app/media
    find /app/media \! -user onlenco -exec chown onlenco:onlenco {} + 2>/dev/null || true
    exec gosu onlenco:onlenco "$@"
fi

exec "$@"
