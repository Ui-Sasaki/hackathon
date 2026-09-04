-- 簡易DB構成: 申請メタデータだけを保存し、証明画像の実体はUploadRepositoryの境界に残す。

begin;

alter table verification_requests
    add column method text not null default 'university_email',
    add constraint verification_method_allowed
        check (method in ('university_email', 'student_card'));

create or replace function app.create_verification_request(
    p_method text,
    p_storage_object_key text default null
)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_actor_id uuid := app.current_actor();
    v_id uuid;
    v_created_at timestamptz := clock_timestamp();
begin
    if not app.is_active_actor() then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if p_method not in ('university_email', 'student_card')
       or (p_method = 'student_card' and p_storage_object_key is null) then
        return jsonb_build_object('code', 'BAD_REQUEST');
    end if;
    if exists (select 1 from verification_requests
               where user_id = v_actor_id and status = 'pending') then
        return jsonb_build_object('code', 'VERIFICATION_ALREADY_PENDING');
    end if;

    insert into verification_requests (
        user_id, method, status, storage_object_key, deletion_due_at, created_at, updated_at
    ) values (
        v_actor_id, p_method, 'pending', p_storage_object_key,
        case when p_storage_object_key is null then null else v_created_at + interval '7 days' end,
        v_created_at, v_created_at
    ) returning id into v_id;

    update users set verification_status = 'pending', updated_at = v_created_at
     where id = v_actor_id;
    insert into audit_logs (actor_id, event_type, target_type, target_id, result, detail, created_at)
    values (v_actor_id, 'verification_requested', 'verification_request', v_id,
            'success', jsonb_build_object('method', p_method), v_created_at);

    return jsonb_build_object(
        'code', 'CREATED', 'id', v_id, 'userId', app.auth_subject_of(v_actor_id),
        'method', p_method, 'status', 'pending',
        'createdAt', to_char(v_created_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
    );
exception when unique_violation then
    return jsonb_build_object('code', 'VERIFICATION_ALREADY_PENDING');
end;
$$;

revoke all on function app.create_verification_request(text, text) from public;
grant execute on function app.create_verification_request(text, text) to tetote_app;

commit;
