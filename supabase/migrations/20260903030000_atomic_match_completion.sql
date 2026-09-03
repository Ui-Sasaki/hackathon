-- 完了確認とdisputeを、match/request/application/auditの単一transactionで処理する。

begin;

alter table matches add column disputed_at timestamptz;

create or replace function app.complete_match(p_match_id uuid)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_match matches%rowtype;
    v_requester uuid;
    v_status match_status;
begin
    select m.* into v_match from matches m
     where m.id = p_match_id for update;
    if found then
        select r.requester_id into v_requester from requests r
         where r.id = v_match.request_id for update;
    end if;
    if not found or not app.match_is_visible(p_match_id) then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;
    if v_match.status not in ('matched', 'completion_pending') then
        return jsonb_build_object('code', 'MATCH_NOT_COMPLETABLE');
    end if;
    if app.current_actor() = v_requester then
        if v_match.requester_confirmed then
            return jsonb_build_object('code', 'COMPLETION_ALREADY_CONFIRMED');
        end if;
        v_match.requester_confirmed := true;
    elsif app.current_actor() = v_match.helper_id then
        if v_match.helper_confirmed then
            return jsonb_build_object('code', 'COMPLETION_ALREADY_CONFIRMED');
        end if;
        v_match.helper_confirmed := true;
    else
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;

    v_status := case
        when v_match.requester_confirmed and v_match.helper_confirmed
            then 'completed'::match_status
        else 'completion_pending'::match_status
    end;
    update matches
       set requester_confirmed = v_match.requester_confirmed,
           helper_confirmed = v_match.helper_confirmed,
           status = v_status,
           completed_at = case when v_status = 'completed' then now() else null end,
           updated_at = now()
     where id = p_match_id;
    update requests
       set status = v_status::text::request_status, updated_at = now()
     where id = v_match.request_id;
    if v_status = 'completed' then
        update applications
           set status = 'completed', updated_at = now()
         where id = v_match.application_id;
    end if;
    return jsonb_build_object('code', 'CONFIRMED', 'status', v_status);
end;
$$;

create or replace function app.dispute_match(p_match_id uuid, p_reason text)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_match matches%rowtype;
    v_audit_id uuid;
begin
    select m.* into v_match from matches m
     where m.id = p_match_id for update;
    if not found or not app.match_is_visible(p_match_id) then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;
    if v_match.status in ('completed', 'disputed', 'cancelled') then
        return jsonb_build_object('code', 'MATCH_NOT_DISPUTABLE');
    end if;
    if length(trim(p_reason)) not between 10 and 1000 then
        return jsonb_build_object('code', 'INVALID_DISPUTE_REASON');
    end if;
    update matches set status = 'disputed', dispute_reason = p_reason,
        disputed_at = now(), updated_at = now() where id = p_match_id;
    update requests set status = 'disputed', updated_at = now()
     where id = v_match.request_id;
    insert into audit_logs (actor_id, event_type, target_type, target_id, result, detail)
    values (app.current_actor(), 'match.disputed', 'match', p_match_id, 'success',
            jsonb_build_object('requestId', v_match.request_id))
    returning id into v_audit_id;
    return jsonb_build_object(
        'code', 'DISPUTED', 'auditLogId', v_audit_id
    );
end;
$$;

revoke all on function app.complete_match(uuid) from public;
revoke all on function app.dispute_match(uuid, text) from public;
grant execute on function app.complete_match(uuid) to tetote_app;
grant execute on function app.dispute_match(uuid, text) to tetote_app;

commit;
