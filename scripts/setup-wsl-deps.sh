#!/usr/bin/env bash
# Optional local-only fallback for Windows without Docker. No system packages are installed.
set -euo pipefail
runtime="${XDG_DATA_HOME:-$HOME/.local/share}/iwardrobe-runtime"
mkdir -p "$runtime/apt/lists/partial" "$runtime/apt/cache/archives/partial" "$runtime/debs" "$runtime/root" "$runtime/logs" "$runtime/socket" "$runtime/redis"
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o "$runtime/apt/postgresql.asc"
cat > "$runtime/apt/sources.list" <<EOF
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu jammy main universe
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] https://archive.ubuntu.com/ubuntu jammy-updates main universe
deb [signed-by=$runtime/apt/postgresql.asc] https://apt.postgresql.org/pub/repos/apt jammy-pgdg main
EOF
apt_args=(-o "Dir::Etc::sourcelist=$runtime/apt/sources.list" -o "Dir::Etc::sourceparts=-" -o "Dir::State::lists=$runtime/apt/lists" -o "Dir::Cache=$runtime/apt/cache" -o 'APT::Get::List-Cleanup=0' -o 'Acquire::Languages=none')
apt-get "${apt_args[@]}" update -qq
cd "$runtime/debs"
apt-get "${apt_args[@]}" download postgresql-16 postgresql-client-16 libpq5 redis-server redis-tools libjemalloc2 liblzf1 liblua5.1-0 lua-cjson lua-bitop
for package in ./*.deb; do dpkg-deb -x "$package" "$runtime/root"; done
export LD_LIBRARY_PATH="$runtime/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$runtime/root/usr/lib/postgresql/16/bin/postgres" --version
"$runtime/root/usr/bin/redis-server" --version
echo "Dependencies extracted to $runtime. Run scripts/start-wsl-deps.sh next."
