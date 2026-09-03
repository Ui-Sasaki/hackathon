-- 通報、監査ログ、高危険度依頼の停止を actor context 付きの単一transactionで保存する。

begin;

create or replace function app.create_report(
    p_target_type text,
    p_target_id text,
    p_reason text,
    p_description text
)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_actor_id uuid := app.current_actor();
    v_target_id uuid;
    v_report_id uuid;
    v_severity report_severity;
    v_created_at timestamptz := clock_timestamp();
    v_visible boolean := false;
begin
    if not app.is_active_actor() then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if p_target_type not in ('user', 'request', 'match', 'message', 'review')
       or length(trim(p_reason)) = 0
       or length(trim(p_description)) not between 10 and 2000 then
        return jsonb_build_object('code', 'BAD_REQUEST');
    end if;

    if p_target_type = 'user' then
        select id into v_target_id
          from users where auth_subject = p_target_id and status <> 'deleted';
        -- 利用者を通報できるのは、公開プロフィールまたは既に閲覧できる依頼・応募・
        -- マッチを通してその利用者を知り得る場合に限る。
        select v_target_id is not null and (
            app.is_admin()
            or app.profile_is_public(v_target_id)
            or exists (
                select 1 from requests r
                 where r.requester_id = v_target_id
                   and (r.requester_id = v_actor_id
                        or (app.request_is_public(r.status, r.expires_at)
                            and not app.is_blocked_pair(r.requester_id, v_actor_id))
                        or app.actor_has_match_on_request(r.id, v_actor_id))
            )
            or exists (
                select 1 from matches m join requests r on r.id = m.request_id
                 where (m.helper_id = v_target_id or r.requester_id = v_target_id)
                   and (m.helper_id = v_actor_id or r.requester_id = v_actor_id)
            )
            or exists (
                select 1 from applications a
                 where a.helper_id = v_target_id
                   and (a.helper_id = v_actor_id
                        or app.request_owner(a.request_id) = v_actor_id)
            )
        ) into v_visible;
    else
        begin
            v_target_id := p_target_id::uuid;
        exception when invalid_text_representation then
            return jsonb_build_object('code', 'REPORT_TARGET_NOT_FOUND');
        end;

        if p_target_type = 'request' then
            select exists (
                select 1 from requests r
                 where r.id = v_target_id and (
                    app.is_admin() or r.requester_id = v_actor_id
                    or (app.request_is_public(r.status, r.expires_at)
                        and not app.is_blocked_pair(r.requester_id, v_actor_id))
                    or app.actor_has_match_on_request(r.id, v_actor_id)
                 )
            ) into v_visible;
        elsif p_target_type = 'match' then
            select exists (
                select 1 from matches m join requests r on r.id = m.request_id
                 where m.id = v_target_id
                   and (app.is_admin() or m.helper_id = v_actor_id
                        or r.requester_id = v_actor_id)
            ) into v_visible;
        elsif p_target_type = 'message' then
            select exists (
                select 1 from messages msg join matches m on m.id = msg.match_id
                    join requests r on r.id = m.request_id
                 where msg.id = v_target_id
                   and (app.is_admin() or m.helper_id = v_actor_id
                        or r.requester_id = v_actor_id)
            ) into v_visible;
        else
            select exists (
                select 1 from reviews rev
                 where rev.id = v_target_id and (
                    app.is_admin() or rev.reviewer_id = v_actor_id
                    or rev.reviewee_id = v_actor_id
                    or (app.profile_is_public(rev.reviewee_id)
                        and not app.is_blocked_pair(rev.reviewee_id, v_actor_id))
                 )
            ) into v_visible;
        end if;
    end if;

    if not coalesce(v_visible, false) then
        -- 同じ404系コードで存在しない対象と権限外の対象を扱い、存在を漏らさない。
        return jsonb_build_object('code', 'REPORT_TARGET_NOT_FOUND');
    end if;

    v_severity := case when p_reason in ('fraud', 'dangerous_work')
                       then 'high'::report_severity else 'medium'::report_severity end;
    insert into reports (
        reporter_id, target_type, target_id, reason, description, severity, status,
        created_at, updated_at
    ) values (
        v_actor_id, p_target_type, v_target_id, p_reason, p_description, v_severity,
        'open', v_created_at, v_created_at
    ) returning id into v_report_id;

    insert into audit_logs (
        actor_id, event_type, target_type, target_id, result, detail, created_at
    ) values (
        v_actor_id, 'report_created', p_target_type, v_target_id, 'success',
        jsonb_build_object('reportId', v_report_id, 'severity', v_severity), v_created_at
    );

    if v_severity = 'high' and p_target_type = 'request' then
        update requests set status = 'suspended', version = version + 1,
                            updated_at = v_created_at
         where id = v_target_id;
        insert into audit_logs (
            actor_id, event_type, target_type, target_id, result, detail, created_at
        ) values (
            v_actor_id, 'request_auto_suspended', 'request', v_target_id, 'success',
            jsonb_build_object('reportId', v_report_id), v_created_at
        );
    end if;

    return jsonb_build_object(
        'code', 'CREATED', 'id', v_report_id,
        'reporterId', app.auth_subject_of(v_actor_id), 'targetType', p_target_type,
        'targetId', p_target_id, 'reason', p_reason, 'description', p_description,
        'severity', v_severity, 'status', 'open',
        'createdAt', to_char(v_created_at at time zone 'UTC',
                             'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
    );
end;
$$;

revoke all on function app.create_report(text, text, text, text) from public;
grant execute on function app.create_report(text, text, text, text) to tetote_app;

commit;
