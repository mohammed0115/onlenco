#!/bin/sh
# Container entrypoint. Runs as root, makes the bind-mounted/named
# media volume writable for the unprivileged `onlenco` user (Docker
# creates fresh named volumes owned by root, shadowing the build-time
# chown), then drops privileges before exec'ing the real command.
set -e

if [ "$(id -u)" = "0" ]; then
    # Best-effort: chown only when the top-level isn't already onlenco-owned.
    # Avoids a slow recursive walk on every restart once permissions stick.
    if [ "$(stat -c %U /app/media 2>/dev/null)" != "onlenco" ]; then
        chown -R onlenco:onlenco /app/media || true
    fi
    exec gosu onlenco:onlenco "$@"
fi

exec "$@"
