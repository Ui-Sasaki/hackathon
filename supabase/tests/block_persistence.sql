-- #14 block mutation and audit checks as tetote_app.

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
    raise notice 'OK   ブロック関係を利用者単位で一意保存';
end;
$$;

-- Repeating the operation is idempotent for state.
select pg_temp.assert_code(
    app.set_own_block('st_helper', true), 'OK', '重複ブロックは冪等'
);
select pg_temp.assert_code(
    app.set_own_block('st_helper', false), 'OK', '本人のブロック解除を保存'
);
do $$
begin
    if app.is_blocked_pair(
        'aaaaaaaa-0000-0000-0000-000000000001',
        'aaaaaaaa-0000-0000-0000-000000000002'
    ) then
        raise exception 'FAIL ブロック解除後も関係が残った';
    end if;
    raise notice 'OK   解除と監査ログを原子的に保存';
end;
$$;

select pg_temp.assert_code(
    app.set_own_block('st_owner', true),
    'SELF_BLOCK_NOT_ALLOWED', '自己ブロックを拒否'
);
select pg_temp.assert_code(
    app.set_own_block('unknown-subject', true),
    'USER_PROFILE_NOT_FOUND', '存在しない対象を秘匿して拒否'
);
rollback;

begin;
select set_config('app.actor_id', '', true);
select pg_temp.assert_code(
    app.set_own_block('st_helper', true),
    'ROLE_FORBIDDEN', 'actor未設定の変更を拒否'
);
rollback;
