-- Matching/chat persistence re-integrated on top of the current repository schema.
-- Historical migrations remain immutable; all replacements below are forward-only.

begin;

alter table matches
    add constraint matches_dispute_reason_length
    check (
        dispute_reason is null
        or length(trim(dispute_reason)) between 10 and 1000
    );

-- The former helper-id function exposed arbitrary profiles to every app connection.
-- Revoke it and expose only the profile attached to an application visible to the actor.
revoke all on function app.application_helper_profile(uuid) from public;
revoke execute on function app.application_helper_profile(uuid) from tetote_app;

create or replace function app.application_helper_profile_for_application(
    p_application_id uuid
)
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

revoke all on function app.application_helper_profile_for_application(uuid) from public;
grant execute on function app.application_helper_profile_for_application(uuid) to tetote_app;

-- Lock the request before validating version/capacity and creating the match.
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
    select * into v_request
      from requests
     where id = p_request_id
     for update;
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

    select * into v_application
      from applications
     where id = p_application_id
     for update;
    if not found then
        return jsonb_build_object('code', 'APPLICATION_NOT_FOUND');
    end if;
    if v_application.request_id <> p_request_id then
        return jsonb_build_object('code', 'APPLICATION_REQUEST_MISMATCH');
    end if;
    if v_application.status <> 'applied'
       or app.is_blocked_pair(v_request.requester_id, v_application.helper_id) then
        return jsonb_build_object('code', 'APPLICATION_NOT_SELECTABLE');
    end if;
    if v_request.status not in ('published', 'matching') then
        return jsonb_build_object(
            'code', 'REQUEST_STATE_CONFLICT', 'currentVersion', v_request.version
        );
    end if;

    select count(*) into v_selected_count
      from matches
     where request_id = p_request_id;
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
       set status = case
               when v_capacity_reached then 'matched'::request_status
               else 'matching'::request_status
           end,
           version = version + 1,
           updated_at = now()
     where id = p_request_id;

    insert into audit_logs (actor_id, event_type, target_type, target_id, result, detail)
    values (
        app.current_actor(), 'application_selected', 'match', v_match_id,
        'success', jsonb_build_object('applicationId', p_application_id)
    );

    return jsonb_build_object('code', 'OK', 'matchId', v_match_id);
end;
$$;

revoke all on function app.select_application(uuid, uuid, integer) from public;
grant execute on function app.select_application(uuid, uuid, integer) to tetote_app;

-- Confirm one party exactly once and update the parent request atomically.
create or replace function app.complete_match(p_match_id uuid, p_actor_role text)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_match matches%rowtype;
    v_requester_id uuid;
    v_new_status match_status;
    v_request_status request_status;
begin
    select * into v_match
      from matches
     where id = p_match_id
     for update;
    if not found then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;

    select requester_id into v_requester_id
      from requests
     where id = v_match.request_id
     for update;
    if app.current_actor() not in (v_requester_id, v_match.helper_id) then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if p_actor_role not in ('requester', 'helper')
       or (p_actor_role = 'requester' and app.current_actor() <> v_requester_id)
       or (p_actor_role = 'helper' and app.current_actor() <> v_match.helper_id) then
        return jsonb_build_object('code', 'ACTOR_ROLE_MISMATCH');
    end if;
    if v_match.status not in ('matched', 'completion_pending')
       or (p_actor_role = 'requester' and v_match.requester_confirmed)
       or (p_actor_role = 'helper' and v_match.helper_confirmed) then
        return jsonb_build_object('code', 'MATCH_NOT_COMPLETABLE');
    end if;

    update matches
       set requester_confirmed = requester_confirmed or p_actor_role = 'requester',
           helper_confirmed = helper_confirmed or p_actor_role = 'helper',
           status = case
               when (requester_confirmed or p_actor_role = 'requester')
                and (helper_confirmed or p_actor_role = 'helper')
               then 'completed'::match_status
               else 'completion_pending'::match_status
           end,
           completed_at = case
               when (requester_confirmed or p_actor_role = 'requester')
                and (helper_confirmed or p_actor_role = 'helper')
               then now()
               else completed_at
           end,
           updated_at = now()
     where id = p_match_id
    returning status into v_new_status;

    if v_new_status = 'completed'
       and not exists (
           select 1 from matches
            where request_id = v_match.request_id and status <> 'completed'
       ) then
        v_request_status := 'completed';
    else
        v_request_status := 'completion_pending';
    end if;

    update requests
       set status = v_request_status, updated_at = now()
     where id = v_match.request_id;

    insert into audit_logs (actor_id, event_type, target_type, target_id, result, detail)
    values (
        app.current_actor(), 'match_completion_confirmed', 'match', p_match_id,
        'success', jsonb_build_object('actorRole', p_actor_role, 'status', v_new_status)
    );

    return jsonb_build_object('code', 'OK');
end;
$$;

revoke all on function app.complete_match(uuid, text) from public;
grant execute on function app.complete_match(uuid, text) to tetote_app;

-- Dispute, request state and immutable audit entry share one transaction.
create or replace function app.dispute_match(p_match_id uuid, p_reason text)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_match matches%rowtype;
    v_requester_id uuid;
begin
    select * into v_match
      from matches
     where id = p_match_id
     for update;
    if not found then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;

    select requester_id into v_requester_id
      from requests
     where id = v_match.request_id
     for update;
    if app.current_actor() not in (v_requester_id, v_match.helper_id) then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if v_match.status in ('completed', 'disputed') then
        return jsonb_build_object('code', 'MATCH_NOT_DISPUTABLE');
    end if;
    if p_reason is null or length(trim(p_reason)) not between 10 and 1000 then
        return jsonb_build_object('code', 'DISPUTE_REASON_INVALID');
    end if;

    update matches
       set status = 'disputed', dispute_reason = p_reason, updated_at = now()
     where id = p_match_id;
    update requests
       set status = 'disputed', updated_at = now()
     where id = v_match.request_id;
    insert into audit_logs (actor_id, event_type, target_type, target_id, result, detail)
    values (
        app.current_actor(), 'match_disputed', 'match', p_match_id, 'success',
        jsonb_build_object('status', 'disputed')
    );

    return jsonb_build_object('code', 'OK');
end;
$$;

revoke all on function app.dispute_match(uuid, text) from public;
grant execute on function app.dispute_match(uuid, text) to tetote_app;

-- Recheck party and block relationship at write time; sent_at remains server-owned.
create or replace function app.send_message(p_match_id uuid, p_body text)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_match matches%rowtype;
    v_requester_id uuid;
    v_message_id uuid;
begin
    select * into v_match from matches where id = p_match_id;
    if not found then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;
    select requester_id into v_requester_id
      from requests
     where id = v_match.request_id;
    if app.current_actor() not in (v_requester_id, v_match.helper_id) then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if app.is_blocked_pair(v_requester_id, v_match.helper_id) then
        return jsonb_build_object('code', 'MESSAGE_FORBIDDEN');
    end if;

    insert into messages (match_id, sender_id, body)
    values (p_match_id, app.current_actor(), p_body)
    returning id into v_message_id;

    return jsonb_build_object('code', 'OK', 'messageId', v_message_id);
end;
$$;

revoke all on function app.send_message(uuid, text) from public;
grant execute on function app.send_message(uuid, text) to tetote_app;

-- Only a party/admin can mark the other party's messages read.
create or replace function app.mark_messages_read(p_match_id uuid)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
begin
    if not exists (select 1 from matches where id = p_match_id) then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;
    if not app.is_match_party(p_match_id, app.current_actor()) and not app.is_admin() then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    update messages
       set read_at = coalesce(read_at, now())
     where match_id = p_match_id and sender_id <> app.current_actor();
    return jsonb_build_object('code', 'OK');
end;
$$;

revoke all on function app.mark_messages_read(uuid) from public;
grant execute on function app.mark_messages_read(uuid) to tetote_app;

-- Cancellation also closes every still-pending application.
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

    update requests
       set status = p_new_status,
           version = case when p_bump_version then version + 1 else version end,
           updated_at = now()
     where id = p_id
       and (p_expected_version is null or version = p_expected_version)
    returning id into v_id;

    if v_id is not null and p_new_status = 'cancelled' then
        update applications
           set status = 'cancelled', updated_at = now()
         where request_id = v_id and status = 'applied';
    end if;
    return v_id;
end;
$$;

-- Development reset must respect all foreign-key dependencies introduced by matching.
create or replace function app.mock_reset_requests()
returns void language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_owner_1024 uuid;
    v_owner_1025 uuid;
begin
    delete from audit_logs;
    delete from messages;
    delete from reviews;
    delete from matches;
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
        '犬の散歩をお願いしたい',
        '体調不良のため、小型犬の散歩を30分お願いしたいです。',
        'pet_support', 'medium', 'AREA-001',
        timestamptz '2026-08-19T17:00:00+09:00', 30, 1,
        'published', 3, timestamptz '2026-08-18T10:00:00+09:00'
    ),
    (
        '39521aee-fc9b-5be6-9652-b3cf45d9107f', v_owner_1025,
        '玄関前の雪かきを手伝ってほしい',
        '玄関から歩道までの雪かきをお願いします。',
        'snow_removal', 'medium', 'AREA-001',
        timestamptz '2026-08-20T09:00:00+09:00', 45, 2,
        'published', 1, timestamptz '2026-08-18T11:00:00+09:00'
    );
end;
$$;

commit;
