#!/usr/bin/env bash
# 同じversionを見た2接続が同時に選択しても、成功は1件だけになることを検査する。
set -euo pipefail

PGBIN="${PGBIN:-$(pg_config --bindir)}"
PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-55432}"
PGDATABASE="${PGDATABASE:-tetote}"
PSQL=("$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" -tA -v ON_ERROR_STOP=1)
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

actor_id="aaaaaaaa-0000-0000-0000-000000000001"

run_selection() {
  local application_id="$1"
  local output_file="$2"
  "${PSQL[@]}" -c "begin; select set_config('app.actor_id', '$actor_id', true); select app.select_application('$application_id', 11)->>'code'; commit;" >"$output_file"
}

run_selection "eeeeeeee-3000-0000-0000-000000000001" "$TMP_DIR/first" &
first_pid=$!
run_selection "eeeeeeee-3000-0000-0000-000000000002" "$TMP_DIR/second" &
second_pid=$!
wait "$first_pid"
wait "$second_pid"

selected_count="$(grep -hxc 'SELECTED' "$TMP_DIR/first" "$TMP_DIR/second" | awk '{s += $1} END {print s}')"
conflict_count="$(grep -hxc 'REQUEST_STATE_CONFLICT' "$TMP_DIR/first" "$TMP_DIR/second" | awk '{s += $1} END {print s}')"
match_count="$("${PSQL[@]}" -c \
  "begin; select set_config('app.actor_id', '$actor_id', true); select count(*) from matches m join requests r on r.id=m.request_id where r.title='同時選択テスト'; commit;" \
  | tail -2 | head -1)"

if [[ "$selected_count" != 1 || "$conflict_count" != 1 || "$match_count" != 1 ]]; then
  echo "FAIL 同時選択 selected=$selected_count conflict=$conflict_count matches=$match_count"
  exit 1
fi
echo "OK   複数接続の同時選択でも定員超過せず1件だけ成功"
