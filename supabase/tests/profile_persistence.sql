-- #67 profile RPC and authentication-boundary checks as tetote_app.

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

-- ensure_user must preserve user-owned and privileged fields on every login.
select app.ensure_user('st_owner', '上書き禁止', 'admin');
do $$
declare v_name text;
declare v_role account_role;
begin
    select display_name, role into v_name, v_role
      from app.resolve_authenticated_user('st_owner');
    if v_name <> '依頼 太郎' or v_role <> 'member' then
        raise exception 'FAIL 再認証で既存プロフィールが上書きされた';
    end if;
    raise notice 'OK   再認証は既存プロフィールを保持';
end;
$$;

-- A verified, previously unknown subject is provisioned without Memory state.
do $$
declare v_role account_role;
begin
    select role into v_role from app.resolve_authenticated_user('st_after_restart');
    if v_role <> 'member' then
        raise exception 'FAIL 新規subjectの安全なプロビジョニング';
    end if;
    raise notice 'OK   DBだけで認証subjectを解決';
end;
$$;

begin;
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);

select * from app.update_own_profile(jsonb_build_object(
    'prefectureCode', '01',
    'birthYear', 2001,
    'helperType', 'student',
    'university', '北海大学',
    'faculty', '工学部',
    'schoolYear', 2,
    'notes', '夕方に連絡'
));

do $$
declare v_name text;
declare v_notes text;
declare v_type helper_type;
begin
    select display_name, notes, helper_type into v_name, v_notes, v_type
      from app.update_own_profile('{"notes": null}'::jsonb);
    if v_name <> '依頼 太郎' or v_notes is not null or v_type <> 'student' then
        raise exception 'FAIL PATCHの省略維持またはnull消去';
    end if;
    raise notice 'OK   PATCHの省略維持とnull消去';
end;
$$;

select pg_temp.assert_rejected(
    $$select * from app.update_own_profile('{"role":"admin"}'::jsonb)$$,
    '権限フィールドは更新不可'
);
select pg_temp.assert_rejected(
    $$select * from app.update_own_profile('{"areaCode":"UNKNOWN"}'::jsonb)$$,
    '未知の活動地域を拒否'
);
select pg_temp.assert_rejected(
    $$select * from app.update_own_profile('{"prefectureCode":"48"}'::jsonb)$$,
    '不正な都道府県コードを拒否'
);
select pg_temp.assert_rejected(
    $$select * from app.update_own_profile('{"helperType":"worker"}'::jsonb)$$,
    'workerは職業必須'
);
select pg_temp.assert_rejected(
    $$update users set role='admin' where id=app.current_actor()$$,
    'usersへの汎用UPDATE権限なし'
);
rollback;

do $$
declare v_count integer;
begin
    select count(*) into v_count from app.list_active_operational_areas();
    if v_count <> 3 then raise exception 'FAIL 活動地域一覧: %', v_count; end if;
    raise notice 'OK   活動地域一覧は有効な3件';
end;
$$;
