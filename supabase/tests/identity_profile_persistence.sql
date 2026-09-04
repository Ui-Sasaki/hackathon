-- Authentication boundary and profile persistence checks as NOBYPASSRLS tetote_app.

do $$
declare v_name text; v_role account_role;
begin
  select display_name, role into v_name, v_role from app.resolve_authenticated_user('st_owner');
  if v_name <> '依頼 太郎' or v_role <> 'member' then
    raise exception 'FAIL 再認証でプロフィールまたはroleが上書きされた';
  end if;
  raise notice 'OK   再認証は既存プロフィールとroleを保持';
end; $$;

do $$ begin
  begin
    perform app.ensure_user('st_privilege_escalation', '管理者', 'admin');
  exception when insufficient_privilege then
    raise notice 'OK   role指定付き利用者作成を非公開化';
    return;
  end;
  raise exception 'FAIL tetote_appからadmin利用者を作成できた';
end; $$;

do $$
declare v_role account_role;
begin
  select role into v_role from app.resolve_authenticated_user('st_after_restart');
  if v_role <> 'member' then raise exception 'FAIL 新規subjectの安全な作成'; end if;
  if app.authenticated_user_id('st_after_restart') is null then
    raise exception 'FAIL 既存subjectの内部ID解決';
  end if;
  raise notice 'OK   SuperTokens subjectをDB利用者へ解決';
end; $$;

begin;
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);
select app.update_own_profile('{"notes":"夕方に連絡","helperType":"worker","occupation":"看護師"}');
do $$ begin
  if (select notes from app.own_profile()) <> '夕方に連絡' then raise exception 'FAIL 本人更新'; end if;
  raise notice 'OK   本人プロフィールを更新';
end; $$;
rollback;

do $$ begin
  if exists(select 1 from app.own_profile()) then raise exception 'FAIL actorなしで取得'; end if;
  raise notice 'OK   actor contextなしの取得を拒否';
end; $$;

do $$
declare v_profile jsonb;
begin
  v_profile := app.application_helper_profile(
    'aaaaaaaa-0000-0000-0000-000000000002'
  );
  if (v_profile ->> 'achievement_count')::integer <> 0
     or v_profile ?| array['auth_subject', 'area_code', 'region', 'notes', 'status'] then
    raise exception 'FAIL 公開プロフィールの機微情報制限';
  end if;
  raise notice 'OK   公開プロフィールから機微情報と未承認実績を除外';
end; $$;

begin;
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);
do $$ begin
  begin
    perform app.update_own_profile('{"role":"admin"}');
  exception when others then
    raise notice 'OK   保護フィールド更新を拒否 (%)', sqlstate;
    return;
  end;
  raise exception 'FAIL role更新が成功した';
end; $$;
rollback;
