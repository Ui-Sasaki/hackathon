#!/usr/bin/env bash
# baseline schema の検証を最初から通す。
#
# 前提: PostgreSQL 15 以上。既定は WSL 上のユーザー所有クラスタ（port 55432）。
# 別の DB を使う場合は PGHOST / PGPORT / PGSUPERUSER / PGDATABASE を上書きする。
#
#   ./supabase/tests/run.sh
#
# ⚠️ RLS 検査は必ず非特権ロール tetote_app で実行する。superuser と table owner は
#    RLS を迂回するため、所有者で実行すると全件通ってしまい何も検証できない。
set -euo pipefail

PGBIN="${PGBIN:-$(pg_config --bindir)}"
PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-55432}"
PGSUPERUSER="${PGSUPERUSER:-tetote}"
PGDATABASE="${PGDATABASE:-tetote}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MIGRATIONS_DIR="$HERE/../migrations"

psql_su() { "$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U "$PGSUPERUSER" "$@"; }

echo "=== 1. データベースを作り直す ==="
"$PGBIN/dropdb"   -h "$PGHOST" -p "$PGPORT" -U "$PGSUPERUSER" --if-exists "$PGDATABASE"
"$PGBIN/createdb" -h "$PGHOST" -p "$PGPORT" -U "$PGSUPERUSER" "$PGDATABASE"

echo "=== 2. migration を適用する ==="
# ファイル名の日時順に supabase/migrations/ の全ファイルを適用する。
# 1本だけを名指しすると、後から追加した migration が検査対象から漏れる。
for migration in "$MIGRATIONS_DIR"/*.sql; do
  echo "  - $(basename "$migration")"
  psql_su -d "$PGDATABASE" -q -v ON_ERROR_STOP=1 -f "$migration"
done
psql_su -d "$PGDATABASE" -tA -c "
  select 'tables=' || (select count(*) from pg_tables where schemaname='public')
      || ' enums='  || (select count(*) from pg_type where typtype='e'
                        and typnamespace='public'::regnamespace)
      || ' checks=' || (select count(*) from pg_constraint where contype='c'
                        and connamespace='public'::regnamespace)
      || ' fks='    || (select count(*) from pg_constraint where contype='f'
                        and connamespace='public'::regnamespace)
      || ' indexes='|| (select count(*) from pg_indexes where schemaname='public')
      || ' policies='|| (select count(*) from pg_policies where schemaname='public');"

echo "=== 3. 制約検査（superuser。制約は RLS と独立に効く）==="
psql_su -d "$PGDATABASE" -v ON_ERROR_STOP=1 -f "$HERE/baseline_constraints.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 4. RLS 検査用データを投入する ==="
psql_su -d "$PGDATABASE" -q -v ON_ERROR_STOP=1 -f "$HERE/_rls_seed.sql"

echo "=== 5. RLS 検査（非特権ロール tetote_app）==="
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/baseline_rls.sql" 2>&1 \
  | grep -E 'OK |FAIL|完了' | sed 's/^psql:[^ ]* //'

echo "=== 6. 応募永続化検査（非特権ロール tetote_app）==="
psql_su -d "$PGDATABASE" -q -v ON_ERROR_STOP=1 -f "$HERE/_application_seed.sql"
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/application_persistence.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 7. 応募選択の原子処理検査（非特権ロール tetote_app）==="
psql_su -d "$PGDATABASE" -q -v ON_ERROR_STOP=1 -f "$HERE/_selection_seed.sql"
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/atomic_application_selection.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 8. 応募選択の同時実行検査（2接続）==="
bash "$HERE/atomic_selection_concurrency.sh"

echo "=== 9. マッチ永続化・取得認可検査（非特権ロール tetote_app）==="
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/match_persistence.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 10. チャット永続化・既読・認可検査（非特権ロール tetote_app）==="
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/chat_persistence.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 11. 完了確認・dispute原子処理検査（非特権ロール tetote_app）==="
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/atomic_match_completion.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 11.1 チャット一覧・認可検査（非特権ロール tetote_app）==="
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/chat_list_persistence.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 12. 認証境界・プロフィール永続化検査（非特権ロール tetote_app）==="
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/identity_profile_persistence.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 13. ブロック永続化・監査検査（非特権ロール tetote_app）==="
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/block_persistence.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 14. 通報・依頼停止・監査検査（非特権ロール tetote_app）==="
"$PGBIN/psql" -h "$PGHOST" -p "$PGPORT" -U tetote_app -d "$PGDATABASE" \
  -v ON_ERROR_STOP=1 -f "$HERE/report_persistence.sql" 2>&1 \
  | grep -E 'OK |FAIL' | sed 's/^psql:[^ ]* //'

echo "=== 全検査を通過した ==="
