#!/usr/bin/env bash
set -euo pipefail
runtime="${XDG_DATA_HOME:-$HOME/.local/share}/iwardrobe-runtime"
pgbin="$runtime/root/usr/lib/postgresql/16/bin"
export LD_LIBRARY_PATH="$runtime/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p "$runtime/logs" "$runtime/socket" "$runtime/redis"
if [ ! -f "$runtime/postgres/PG_VERSION" ]; then
  umask 077
  printf '%s\n' 'local-development' > "$runtime/init-password"
  "$pgbin/initdb" -D "$runtime/postgres" -U iwardrobe --auth-local=trust --auth-host=scram-sha-256 --pwfile="$runtime/init-password" --encoding=UTF8 --locale=C.UTF-8
  rm -f "$runtime/init-password"
fi
if ! "$pgbin/pg_ctl" -D "$runtime/postgres" status >/dev/null 2>&1; then
  "$pgbin/pg_ctl" -D "$runtime/postgres" -l "$runtime/logs/postgres.log" -o "-p 5433 -h 127.0.0.1 -k $runtime/socket" start
fi
for database in iwardrobe iwardrobe_test; do
  exists=$("$pgbin/psql" -h "$runtime/socket" -p 5433 -U iwardrobe -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='$database'")
  if [ "$exists" != "1" ]; then "$pgbin/createdb" -h "$runtime/socket" -p 5433 -U iwardrobe "$database"; fi
done
if ! "$runtime/root/usr/bin/redis-cli" -h 127.0.0.1 -p 6380 ping >/dev/null 2>&1; then
  "$runtime/root/usr/bin/redis-server" --bind 127.0.0.1 --port 6380 --protected-mode yes --daemonize yes --dir "$runtime/redis" --appendonly yes --logfile "$runtime/logs/redis.log" --pidfile "$runtime/redis.pid"
fi
for attempt in 1 2 3 4 5; do
  if "$runtime/root/usr/bin/redis-cli" -p 6380 ping; then break; fi
  sleep 0.2
done
"$runtime/root/usr/bin/redis-cli" -p 6380 ping >/dev/null
echo 'IWardrobe local dependencies: PostgreSQL 5433, Redis 6380 (loopback only).'
