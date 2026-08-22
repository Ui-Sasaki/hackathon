-- RLS が実際に拒否することを確認する。
--
-- ⚠️ **必ず非特権ロール（tetote_app）で実行すること。** superuser とテーブル所有者は
-- RLS を迂回するため、所有者で実行すると全件通ってしまい何も検証できない。
--
-- 使い方:
--   psql -U tetote_app -d tetote -v ON_ERROR_STOP=1 -f supabase/tests/baseline_rls.sql

\set OWNER    '''aaaaaaaa-0000-0000-0000-000000000001'''
\set HELPER   '''aaaaaaaa-0000-0000-0000-000000000002'''
\set STRANGER '''aaaaaaaa-0000-0000-0000-000000000003'''
\set BLOCKED  '''aaaaaaaa-0000-0000-0000-000000000004'''
\set ADMIN    '''aaaaaaaa-0000-0000-0000-000000000009'''

create or replace function pg_temp.assert_count(stmt text, expected bigint, label text)
returns void language plpgsql as $$
declare n bigint;
begin
    execute stmt into n;
    if n <> expected then
        raise exception 'FAIL % : 期待 % 件 / 実際 % 件', label, expected, n;
    end if;
    raise notice 'OK   % (% 件)', label, n;
end;
$$;

create or replace function pg_temp.assert_rejected(stmt text, label text)
returns void language plpgsql as $$
begin
    begin
        execute stmt;
    exception when others then
        raise notice 'OK   % (%)', label, sqlstate;
        return;
    end;
    raise exception 'FAIL % : 拒否されるべき操作が成功した', label;
end;
$$;

-- =========================================================================
-- 1. 未認証（actor 未設定）
-- =========================================================================
begin;
select set_config('app.actor_id', '', true);

select pg_temp.assert_count('select count(*) from requests', 0, '未認証: 依頼が見えない');
select pg_temp.assert_count('select count(*) from users', 0, '未認証: 利用者が見えない');
select pg_temp.assert_count('select count(*) from messages', 0, '未認証: メッセージが見えない');
select pg_temp.assert_count('select count(*) from matches', 0, '未認証: マッチが見えない');
select pg_temp.assert_count('select count(*) from achievement_profiles', 0,
                            '未認証: 実績プロフィールが見えない');
rollback;

-- =========================================================================
-- 2. 依頼者本人
-- =========================================================================
begin;
select set_config('app.actor_id', :OWNER, true);

-- 自分の依頼は取消済みも含めて見える（公開1 + 取消1）。
-- ブロック相手の公開依頼は除外されるので 2 件。
select pg_temp.assert_count('select count(*) from requests', 2,
                            '依頼者: 自分の依頼は取消済みも見え、ブロック相手の依頼は見えない');
select pg_temp.assert_count(
    'select count(*) from requests where id = ''bbbbbbbb-0000-0000-0000-000000000003''', 0,
    '依頼者: ブロックした相手の公開依頼が見えない');
select pg_temp.assert_count('select count(*) from messages', 1,
                            '依頼者: 自分のマッチのメッセージが見える');
select pg_temp.assert_count('select count(*) from user_blocks', 1,
                            '依頼者: 自分がブロックした関係が見える');
rollback;

-- =========================================================================
-- 3. 無関係な利用者
-- =========================================================================
begin;
select set_config('app.actor_id', :STRANGER, true);

-- 公開中の依頼2件だけ。取消済みは見えない。
select pg_temp.assert_count('select count(*) from requests', 2,
                            '無関係: 公開中の依頼だけが見える');
select pg_temp.assert_count(
    'select count(*) from requests where status = ''cancelled''', 0,
    '無関係: 取消済みの依頼が見えない');
select pg_temp.assert_count('select count(*) from messages', 0,
                            '無関係: 他人のマッチのメッセージが見えない');
select pg_temp.assert_count('select count(*) from matches', 0,
                            '無関係: 他人のマッチが見えない');
select pg_temp.assert_count('select count(*) from applications', 0,
                            '無関係: 他人の応募が見えない');
-- 自分の行だけは見える。他人の行が見えないことを別途確認する。
select pg_temp.assert_count('select count(*) from users', 1,
                            '無関係: 見えるのは自分の利用者行だけ');
select pg_temp.assert_count(
    'select count(*) from users where id <> ''aaaaaaaa-0000-0000-0000-000000000003''', 0,
    '無関係: 他人の利用者行が見えない');
select pg_temp.assert_count('select count(*) from audit_logs', 0,
                            '無関係: 監査ログが見えない');
-- 本人未承認の実績プロフィールは visibility=public でも見えない。
select pg_temp.assert_count('select count(*) from achievement_profiles', 0,
                            '無関係: 未承認の実績プロフィールが見えない');
-- 他人になりすました応募はできない。
select pg_temp.assert_rejected($x$
  insert into applications (request_id, helper_id)
  values ('bbbbbbbb-0000-0000-0000-000000000001','aaaaaaaa-0000-0000-0000-000000000002')
$x$, '無関係: 他人名義の応募');
-- 他人名義の依頼作成もできない。
select pg_temp.assert_rejected($x$
  insert into requests (requester_id, title, category_id, area_code)
  values ('aaaaaaaa-0000-0000-0000-000000000001','なりすまし','pet_support','AREA-001')
$x$, '無関係: 他人名義の依頼作成');
rollback;

-- =========================================================================
-- 4. ブロックされた側
-- =========================================================================
begin;
select set_config('app.actor_id', :BLOCKED, true);

-- 自分の依頼1件のみ。ブロックした側の公開依頼は双方向判定で除外される。
select pg_temp.assert_count('select count(*) from requests', 1,
                            'ブロック側: 相手の公開依頼が双方向で除外される');
select pg_temp.assert_count('select count(*) from user_blocks', 0,
                            'ブロック側: 誰にブロックされたかは見えない');
-- ブロック関係にある相手の依頼へは応募できない。
select pg_temp.assert_rejected($x$
  insert into applications (request_id, helper_id)
  values ('bbbbbbbb-0000-0000-0000-000000000001','aaaaaaaa-0000-0000-0000-000000000004')
$x$, 'ブロック側: 相手の依頼への応募');
rollback;

-- =========================================================================
-- 5. マッチ当事者（支援者）
-- =========================================================================
begin;
select set_config('app.actor_id', :HELPER, true);

select pg_temp.assert_count('select count(*) from messages', 1,
                            '支援者: 自分のマッチのメッセージが見える');
select pg_temp.assert_count('select count(*) from matches', 1,
                            '支援者: 自分のマッチが見える');
select pg_temp.assert_count('select count(*) from applications', 1,
                            '支援者: 自分の応募が見える');
select pg_temp.assert_count('select count(*) from achievement_profiles', 1,
                            '支援者: 自分の実績プロフィールは未承認でも見える');
-- 自分の依頼ではないので、成立したマッチの依頼は見える。
select pg_temp.assert_count(
    'select count(*) from requests where id = ''bbbbbbbb-0000-0000-0000-000000000001''', 1,
    '支援者: 成立したマッチの依頼が見える');
rollback;

-- =========================================================================
-- 6. 管理者
-- =========================================================================
begin;
select set_config('app.actor_id', :ADMIN, true);

select pg_temp.assert_count('select count(*) from requests', 3, '管理者: 全依頼が見える');
select pg_temp.assert_count('select count(*) from audit_logs', 1, '管理者: 監査ログが見える');
select pg_temp.assert_count('select count(*) from messages', 1,
                            '管理者: 通報調査のためメッセージが見える');
rollback;

-- =========================================================================
-- 7. 直接 DML の禁止（状態遷移は専用関数へ寄せる）
-- =========================================================================
begin;
select set_config('app.actor_id', :OWNER, true);

select pg_temp.assert_rejected(
    'update requests set status = ''cancelled'' where requester_id = ''aaaaaaaa-0000-0000-0000-000000000001''',
    '直接 UPDATE が権限で拒否される');
select pg_temp.assert_rejected(
    'delete from requests where requester_id = ''aaaaaaaa-0000-0000-0000-000000000001''',
    '直接 DELETE が権限で拒否される');
select pg_temp.assert_rejected(
    'update audit_logs set result = ''tampered''',
    '監査ログの改変が拒否される');
select pg_temp.assert_rejected(
    'delete from audit_logs',
    '監査ログの削除が拒否される');
rollback;

\echo '--- RLS 検査完了 ---'
