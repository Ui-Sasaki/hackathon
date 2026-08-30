#!/usr/bin/env bash
set -euo pipefail

PGBIN="${PGBIN:-/usr/lib/postgresql/18/bin}"
PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-55432}"
PGDATABASE="${PGDATABASE:-tetote}"
RESULT_DIR="$(mktemp -d)"
trap 'rm -rf "$RESULT_DIR"' EXIT

run_selection() {
  local application_id="$1"
  "$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
    -tA -v ON_ERROR_STOP=1 -c "
      begin;
      select set_config(
        'app.actor_id', '10000000-0000-0000-0000-000000000001', true
      );
      select app.select_application(
        '$application_id',
        '20000000-0000-0000-0000-000000000002',
        1
      );
      commit;
    "
}

run_selection '30000000-0000-0000-0000-000000000002' >"$RESULT_DIR/a" &
pid_a=$!
run_selection '30000000-0000-0000-0000-000000000003' >"$RESULT_DIR/b" &
pid_b=$!
wait "$pid_a"
wait "$pid_b"

ok_count="$(grep -h -c '"code": "OK"' "$RESULT_DIR/a" "$RESULT_DIR/b" | awk '{s += $1} END {print s}')"
conflict_count="$(grep -h -c 'REQUEST_STATE_CONFLICT' "$RESULT_DIR/a" "$RESULT_DIR/b" | awk '{s += $1} END {print s}')"
match_count="$($PGBIN/psql -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" -tA -c "
  begin;
  select set_config(
    'app.actor_id', '10000000-0000-0000-0000-000000000001', true
  );
  select count(*) from matches where request_id = '20000000-0000-0000-0000-000000000002';
  rollback;
" | grep -E '^[0-9]+$')"

if [[ "$ok_count" != "1" || "$conflict_count" != "1" || "$match_count" != "1" ]]; then
  echo "FAIL 同時選択の結果が不正 (ok=$ok_count conflict=$conflict_count matches=$match_count)"
  sed -n '1,20p' "$RESULT_DIR/a" "$RESULT_DIR/b"
  exit 1
fi
echo "OK   2接続の同時選択でも定員を超えず片方を競合拒否"
