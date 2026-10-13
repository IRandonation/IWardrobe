#!/usr/bin/env bash
set -euo pipefail
runtime="${XDG_DATA_HOME:-$HOME/.local/share}/iwardrobe-runtime"
export LD_LIBRARY_PATH="$runtime/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$runtime/root/usr/bin/redis-cli" -p 6380 shutdown || true
"$runtime/root/usr/lib/postgresql/16/bin/pg_ctl" -D "$runtime/postgres" stop -m fast
