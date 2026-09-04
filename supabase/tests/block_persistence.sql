-- ブロック変更、監査ログ、RLS反映を非特権ロールで検証する。

create or replace function pg_temp.assert_code(
    actual jsonb, expected text, label text
) returns void language plpgsql as $$
begin
    if actual ->> 'code' <> expected then
        raise exception 'FAIL % : expected %, actual %', label, expected, actual;
    end if;
    if expected = 'OK' and nullif(actual ->> 'auditId', '') is null then
        raise exception 'FAIL % : 監査ログIDが返らない', label;
    end if;
    raise notice 'OK   %', label;
end;
$$;

begin;
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);

select pg_temp.assert_code(
    app.set_own_block('st_helper', true), 'OK', '本人のブロックを保存'
);
do $$
begin
    if not app.is_blocked_pair(
        'aaaaaaaa-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000002'
    ) then
        raise exception 'FAIL ブロック関係の双方向判定';
    end if;
    if (select count(*) from user_blocks
         where blocker_id = app.current_actor()
           and blocked_id = 'aaaaaaaa-0000-0000-0000-000000000002') <> 1 then
        raise exception 'FAIL ブロック関係の一意保存';
    end if;
    if (select count(*) from audit_logs
         where actor_id = app.current_actor()
           and event_type = 'user_blocked'
           and target_id = 'aaaaaaaa-0000-0000-0000-000000000002') <> 1 then
        raise exception 'FAIL ブロック監査ログ';
    end if;
    raise notice 'OK   ブロック関係と監査ログを原子的に保存';
end;
$$;

select pg_temp.assert_code(
    app.set_own_block('st_helper', true), 'OK', '重複ブロックは冪等'
);
select pg_temp.assert_code(
    app.set_own_block('st_helper', false), 'OK', '本人のブロック解除を保存'
);
select pg_temp.assert_code(
    app.set_own_block('st_helper', false), 'OK', '重複解除は冪等'
);
do $$
begin
    if app.is_blocked_pair(
        'aaaaaaaa-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000002'
    ) then
        raise exception 'FAIL ブロック解除後も関係が残った';
    end if;
    raise notice 'OK   ブロック解除を保存';
end;
$$;

select pg_temp.assert_code(
    app.set_own_block('st_owner', true),
    'SELF_BLOCK_NOT_ALLOWED', '自己ブロックを拒否'
);
select pg_temp.assert_code(
    app.set_own_block('unknown-subject', true),
    'USER_PROFILE_NOT_FOUND', '存在しない対象を拒否'
);
rollback;

begin;
select set_config('app.actor_id', '', true);
select pg_temp.assert_code(
    app.set_own_block('st_helper', true),
    'ROLE_FORBIDDEN', 'actor未設定の変更を拒否'
);
rollback;
