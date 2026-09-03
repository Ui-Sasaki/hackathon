-- 通報作成、対象可視性、高危険度依頼停止、監査ログを非特権ロールで検証する。

create or replace function pg_temp.assert_code(
    actual jsonb, expected text, label text
) returns void language plpgsql as $$
begin
    if actual ->> 'code' <> expected then
        raise exception 'FAIL % : expected %, actual %', label, expected, actual;
    end if;
    raise notice 'OK   %', label;
end;
$$;

begin;
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);
select pg_temp.assert_code(
    app.create_report('request', 'bbbbbbbb-0000-0000-0000-000000000001',
                      'dangerous_work', '高所で危険な作業を求められています。'),
    'CREATED', '閲覧可能な依頼を通報'
);
do $$
begin
    if (select status from requests where id = 'bbbbbbbb-0000-0000-0000-000000000001') <> 'suspended' then
        raise exception 'FAIL high risk request was not suspended';
    end if;
    if (select count(*) from audit_logs where actor_id = app.current_actor()
          and event_type in ('report_created', 'request_auto_suspended')) <> 2 then
        raise exception 'FAIL report and suspension audit logs were not written';
    end if;
    raise notice 'OK   通報・依頼停止・監査ログを原子的に保存';
end;
$$;
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000002', true);
select pg_temp.assert_code(
    app.create_report('request', 'bbbbbbbb-0000-0000-0000-000000000002',
                      'fraud', '見る権限のない取消済み依頼です。'),
    'REPORT_TARGET_NOT_FOUND', '閲覧権限のない対象を拒否'
);
select pg_temp.assert_code(
    app.create_report('request', 'not-a-uuid', 'fraud', 'IDが不正な依頼を通報します。'),
    'REPORT_TARGET_NOT_FOUND', '存在しない対象を拒否'
);
rollback;

begin;
select set_config('app.actor_id', '', true);
select pg_temp.assert_code(
    app.create_report('request', 'bbbbbbbb-0000-0000-0000-000000000001',
                      'fraud', '認証されていない通報は拒否されます。'),
    'ROLE_FORBIDDEN', 'actor未設定の通報を拒否'
);
rollback;
