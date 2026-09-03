-- 応募者選択を、定員予約・マッチ作成・依頼更新と同一transactionで行う。
-- 呼び出し側は返却された code をHTTP 409/403/404へ変換する。

begin;

create or replace function app.select_application(
    p_application_id uuid,
    p_expected_version integer
)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_application applications%rowtype;
    v_request requests%rowtype;
    v_match matches%rowtype;
    v_selected_count integer;
    v_next_status request_status;
begin
    if p_expected_version is null or p_expected_version < 1 then
        return jsonb_build_object('code', 'REQUEST_STATE_CONFLICT');
    end if;

    select a.* into v_application
      from applications a
     where a.id = p_application_id;
    if not found then
        return jsonb_build_object('code', 'APPLICATION_NOT_FOUND');
    end if;

    -- 全ての選択を依頼単位で直列化する。応募行より先に依頼行をロックして
    -- 複数応募を逆順に選択した場合のdeadlockも避ける。
    select r.* into v_request
      from requests r
     where r.id = v_application.request_id
     for update;

    if v_request.requester_id <> app.current_actor() then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if not app.is_active_actor() then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if app.is_blocked_pair(v_request.requester_id, v_application.helper_id) then
        return jsonb_build_object('code', 'APPLICATION_NOT_FOUND');
    end if;
    if v_request.version <> p_expected_version then
        return jsonb_build_object(
            'code', 'REQUEST_STATE_CONFLICT',
            'currentVersion', v_request.version
        );
    end if;
    if v_request.status not in ('published', 'matching') then
        return jsonb_build_object('code', 'REQUEST_STATE_CONFLICT');
    end if;
    if v_application.status <> 'applied' then
        return jsonb_build_object('code', 'APPLICATION_NOT_SELECTABLE');
    end if;
    if v_request.verification_required and not exists (
        select 1 from users u
         where u.id = v_application.helper_id
           and u.status = 'active'
           and u.verification_status = 'approved'
    ) then
        return jsonb_build_object('code', 'HELPER_VERIFICATION_REQUIRED');
    end if;

    select count(*) into v_selected_count
      from matches m
     where m.request_id = v_request.id
       and m.status <> 'cancelled';
    if v_selected_count >= v_request.required_helpers then
        return jsonb_build_object('code', 'CAPACITY_REACHED');
    end if;

    update applications
       set status = 'selected', updated_at = now()
     where id = v_application.id;

    insert into matches (request_id, helper_id, application_id)
    values (v_request.id, v_application.helper_id, v_application.id)
    returning * into v_match;

    v_selected_count := v_selected_count + 1;
    v_next_status := case
        when v_selected_count >= v_request.required_helpers then 'matched'::request_status
        else 'matching'::request_status
    end;

    update requests
       set status = v_next_status,
           version = version + 1,
           updated_at = now()
     where id = v_request.id
    returning * into v_request;

    if v_next_status = 'matched' then
        update applications
           set status = 'not_selected', updated_at = now()
         where request_id = v_request.id
           and id <> v_application.id
           and status = 'applied';
    end if;

    return jsonb_build_object(
        'code', 'SELECTED',
        'applicationId', v_application.id,
        'requestId', v_request.id,
        'requestVersion', v_request.version,
        'requestStatus', v_request.status,
        'matchId', v_match.id,
        'matchedAt', v_match.matched_at
    );
exception
    when unique_violation then
        return jsonb_build_object('code', 'APPLICATION_NOT_SELECTABLE');
end;
$$;

revoke all on function app.select_application(uuid, integer) from public;
grant execute on function app.select_application(uuid, integer) to tetote_app;

commit;
