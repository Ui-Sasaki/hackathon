-- #20 応募永続化: 本人確認必須フラグ、応募RLS、取り下げ状態遷移。
-- baseline migration は変更せず、この差分だけを追加する。

begin;

alter table requests
    add column verification_required boolean not null default false;

create or replace function app.request_accepts_application(
    p_request_id uuid,
    p_actor_id uuid
)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
    select exists (
        select 1
          from requests r
          join users u on u.id = p_actor_id
         where r.id = p_request_id
           and r.requester_id <> p_actor_id
           and r.status = 'published'
           and (r.expires_at is null or r.expires_at > now())
           and (not r.verification_required or u.verification_status = 'approved')
           and u.status = 'active'
           and not app.is_blocked_pair(r.requester_id, p_actor_id)
    );
$$;

revoke all on function app.request_accepts_application(uuid, uuid) from public;
grant execute on function app.request_accepts_application(uuid, uuid) to tetote_app;

create or replace function app.application_helper_profile(p_application_id uuid)
returns jsonb language sql stable security definer
set search_path = public, pg_temp as $$
    select jsonb_build_object(
        'display_name', u.display_name,
        'verification_status', u.verification_status,
        'email_verified', u.email_verified,
        'achievement_count', (
            select count(*) from achievement_profiles ap where ap.user_id = u.id
        )
    )
    from applications a
    join users u on u.id = a.helper_id
    where a.id = p_application_id
      and (
          a.helper_id = app.current_actor()
          or app.request_owner(a.request_id) = app.current_actor()
          or app.is_admin()
      )
      and (
          a.helper_id = app.current_actor()
          or not app.is_blocked_pair(a.helper_id, app.current_actor())
      );
$$;

revoke all on function app.application_helper_profile(uuid) from public;
grant execute on function app.application_helper_profile(uuid) to tetote_app;

drop policy applications_insert on applications;
create policy applications_insert on applications for insert to tetote_app
    with check (
        helper_id = app.current_actor()
        and app.request_accepts_application(request_id, app.current_actor())
    );

create or replace function app.withdraw_application(p_application_id uuid)
returns uuid language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_application_id uuid;
begin
    update applications
       set status = 'withdrawn', updated_at = now()
     where id = p_application_id
       and helper_id = app.current_actor()
       and status = 'applied'
    returning id into v_application_id;
    return v_application_id;
end;
$$;

revoke all on function app.withdraw_application(uuid) from public;
grant execute on function app.withdraw_application(uuid) to tetote_app;

-- 応募者選択は依頼行をロックし、定員確認からマッチ作成までを原子的に行う。
create or replace function app.select_application(
    p_application_id uuid,
    p_request_id uuid,
    p_expected_version integer
)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_request requests%rowtype;
    v_application applications%rowtype;
    v_selected_count integer;
    v_capacity_reached boolean;
    v_match_id uuid;
begin
    select * into v_request from requests where id = p_request_id for update;
    if not found then
        return jsonb_build_object('code', 'REQUEST_NOT_FOUND');
    end if;
    if v_request.requester_id <> app.current_actor() and not app.is_admin() then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if v_request.version <> p_expected_version then
        return jsonb_build_object(
            'code', 'REQUEST_STATE_CONFLICT', 'currentVersion', v_request.version
        );
    end if;

    select * into v_application from applications where id = p_application_id;
    if not found then
        return jsonb_build_object('code', 'APPLICATION_NOT_FOUND');
    end if;
    if v_application.request_id <> p_request_id then
        return jsonb_build_object('code', 'APPLICATION_REQUEST_MISMATCH');
    end if;
    if v_application.status <> 'applied' then
        return jsonb_build_object('code', 'APPLICATION_NOT_SELECTABLE');
    end if;
    if v_request.status not in ('published', 'matching') then
        return jsonb_build_object('code', 'REQUEST_STATE_CONFLICT', 'currentVersion', v_request.version);
    end if;

    select count(*) into v_selected_count from matches where request_id = p_request_id;
    if v_selected_count >= v_request.required_helpers then
        return jsonb_build_object('code', 'CAPACITY_REACHED');
    end if;
    v_capacity_reached := v_selected_count + 1 >= v_request.required_helpers;

    update applications
       set status = 'selected', updated_at = now()
     where id = p_application_id;
    insert into matches (request_id, helper_id, application_id)
    values (p_request_id, v_application.helper_id, p_application_id)
    returning id into v_match_id;

    if v_capacity_reached then
        update applications
           set status = 'not_selected', updated_at = now()
         where request_id = p_request_id and status = 'applied';
    end if;
    update requests
       set status = case when v_capacity_reached then 'matched'::request_status
                         else 'matching'::request_status end,
           version = version + 1,
           updated_at = now()
     where id = p_request_id;

    return jsonb_build_object('code', 'OK', 'matchId', v_match_id);
end;
$$;

revoke all on function app.select_application(uuid, uuid, integer) from public;
grant execute on function app.select_application(uuid, uuid, integer) to tetote_app;

-- 当事者の完了確認と依頼状態を同じトランザクションで更新する。
create or replace function app.complete_match(p_match_id uuid, p_actor_role text)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_match matches%rowtype;
    v_requester_id uuid;
    v_new_status match_status;
    v_request_status request_status;
begin
    select * into v_match from matches where id = p_match_id for update;
    if not found then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;
    select requester_id into v_requester_id from requests where id = v_match.request_id for update;
    if app.current_actor() not in (v_requester_id, v_match.helper_id) then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if (p_actor_role = 'requester' and app.current_actor() <> v_requester_id)
       or (p_actor_role = 'helper' and app.current_actor() <> v_match.helper_id)
       or p_actor_role not in ('requester', 'helper') then
        return jsonb_build_object('code', 'ACTOR_ROLE_MISMATCH');
    end if;
    if v_match.status not in ('matched', 'completion_pending') then
        return jsonb_build_object('code', 'MATCH_NOT_COMPLETABLE');
    end if;

    update matches set
        requester_confirmed = requester_confirmed or p_actor_role = 'requester',
        helper_confirmed = helper_confirmed or p_actor_role = 'helper',
        status = case
            when (requester_confirmed or p_actor_role = 'requester')
             and (helper_confirmed or p_actor_role = 'helper') then 'completed'::match_status
            else 'completion_pending'::match_status end,
        completed_at = case
            when (requester_confirmed or p_actor_role = 'requester')
             and (helper_confirmed or p_actor_role = 'helper') then now()
            else completed_at end,
        updated_at = now()
     where id = p_match_id
     returning status into v_new_status;

    if v_new_status = 'completed'
       and not exists (select 1 from matches where request_id = v_match.request_id and status <> 'completed') then
        v_request_status := 'completed';
    else
        v_request_status := 'completion_pending';
    end if;
    update requests set status = v_request_status, updated_at = now()
     where id = v_match.request_id;
    insert into audit_logs (actor_id, event_type, target_type, target_id, result, detail)
    values (app.current_actor(), 'match_completion_confirmed', 'match', p_match_id, 'success',
            jsonb_build_object('actorRole', p_actor_role, 'status', v_new_status));
    return jsonb_build_object('code', 'OK');
end;
$$;

revoke all on function app.complete_match(uuid, text) from public;
grant execute on function app.complete_match(uuid, text) to tetote_app;

-- disputeと依頼状態、監査ログを原子的に確定する。
create or replace function app.dispute_match(p_match_id uuid, p_reason text)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_match matches%rowtype;
    v_requester_id uuid;
begin
    select * into v_match from matches where id = p_match_id for update;
    if not found then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;
    select requester_id into v_requester_id from requests where id = v_match.request_id for update;
    if app.current_actor() not in (v_requester_id, v_match.helper_id) then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if v_match.status in ('completed', 'disputed') then
        return jsonb_build_object('code', 'MATCH_NOT_DISPUTABLE');
    end if;
    update matches set status = 'disputed', dispute_reason = p_reason, updated_at = now()
     where id = p_match_id;
    update requests set status = 'disputed', updated_at = now() where id = v_match.request_id;
    insert into audit_logs (actor_id, event_type, target_type, target_id, result, detail)
    values (app.current_actor(), 'match_disputed', 'match', p_match_id, 'success',
            jsonb_build_object('reason', p_reason));
    return jsonb_build_object('code', 'OK');
end;
$$;

revoke all on function app.dispute_match(uuid, text) from public;
grant execute on function app.dispute_match(uuid, text) to tetote_app;

-- 送信可否をDBで再検証し、ブロック関係がある当事者間の送信を拒否する。
create or replace function app.send_message(p_match_id uuid, p_body text)
returns uuid language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_match matches%rowtype;
    v_requester_id uuid;
    v_message_id uuid;
begin
    select * into v_match from matches where id = p_match_id;
    if not found then
        return null;
    end if;
    select requester_id into v_requester_id from requests where id = v_match.request_id;
    if app.current_actor() not in (v_requester_id, v_match.helper_id)
       or app.is_blocked_pair(v_requester_id, v_match.helper_id) then
        return null;
    end if;
    insert into messages (match_id, sender_id, body)
    values (p_match_id, app.current_actor(), p_body)
    returning id into v_message_id;
    return v_message_id;
end;
$$;

revoke all on function app.send_message(uuid, text) from public;
grant execute on function app.send_message(uuid, text) to tetote_app;

-- 閲覧者以外が送信した未読メッセージだけをサーバー時刻で既読化する。
create or replace function app.mark_messages_read(p_match_id uuid)
returns void language plpgsql security definer
set search_path = public, pg_temp as $$
begin
    if not app.is_match_party(p_match_id, app.current_actor()) and not app.is_admin() then
        return;
    end if;
    update messages set read_at = coalesce(read_at, now())
     where match_id = p_match_id and sender_id <> app.current_actor();
end;
$$;

revoke all on function app.mark_messages_read(uuid) from public;
grant execute on function app.mark_messages_read(uuid) to tetote_app;

-- 依頼取消と未処理応募の取消を同じトランザクションで確定する。
create or replace function app.set_request_status(
    p_id uuid,
    p_new_status request_status,
    p_expected_version integer default null,
    p_bump_version boolean default true
)
returns uuid language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_id uuid;
begin
    if p_new_status = 'cancelled' and not exists (
        select 1 from requests r
         where r.id = p_id
           and (r.requester_id = app.current_actor() or app.is_admin())
    ) then
        return null;
    end if;

    if p_expected_version is null then
        update requests set
            status = p_new_status,
            version = case when p_bump_version then version + 1 else version end
         where id = p_id
        returning id into v_id;
    else
        update requests set
            status = p_new_status,
            version = case when p_bump_version then version + 1 else version end
         where id = p_id and version = p_expected_version
        returning id into v_id;
    end if;

    if v_id is not null and p_new_status = 'cancelled' then
        update applications
           set status = 'cancelled', updated_at = now()
         where request_id = v_id and status = 'applied';
    end if;
    return v_id;
end;
$$;

-- 応募が存在しても開発用リセットがFKで失敗しないよう、既存関数を置換する。
create or replace function app.mock_reset_requests()
returns void language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_owner_1024 uuid;
    v_owner_1025 uuid;
begin
    delete from applications;
    delete from requests;

    v_owner_1024 := app.ensure_user('usr_101', '山田 花子', 'member');
    v_owner_1025 := app.ensure_user('usr_301', '地域住民', 'member');

    insert into requests (
        id, requester_id, title, original_text, category_id, risk_level,
        area_code, scheduled_at, estimated_minutes, required_helpers,
        status, version, created_at
    ) values
    (
        '5fcfec7f-a8b0-58d4-931e-593d60355ee3', v_owner_1024,
        '犬の散歩をお願いしたい', '体調不良のため、小型犬の散歩を30分お願いしたいです。',
        'pet_support', 'medium', 'AREA-001',
        timestamptz '2026-08-19T17:00:00+09:00', 30, 1,
        'published', 3, timestamptz '2026-08-18T10:00:00+09:00'
    ),
    (
        '39521aee-fc9b-5be6-9652-b3cf45d9107f', v_owner_1025,
        '玄関前の雪かきを手伝ってほしい', '玄関から歩道までの雪かきをお願いします。',
        'snow_removal', 'medium', 'AREA-001',
        timestamptz '2026-08-20T09:00:00+09:00', 45, 2,
        'published', 1, timestamptz '2026-08-18T11:00:00+09:00'
    );
end;
$$;

commit;
