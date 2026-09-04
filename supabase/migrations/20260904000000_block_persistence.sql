-- ブロック関係と監査ログを、actor context付きの単一transactionで更新する。

begin;

create or replace function app.set_own_block(
    p_blocked_auth_subject text,
    p_blocked boolean
)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_actor_id uuid := app.current_actor();
    v_blocked_id uuid;
    v_audit_id uuid;
    v_updated_at timestamptz := clock_timestamp();
begin
    if not app.is_active_actor() then
        return jsonb_build_object('code', 'ROLE_FORBIDDEN');
    end if;
    if p_blocked is null then
        return jsonb_build_object('code', 'BAD_REQUEST');
    end if;

    select u.id into v_blocked_id
      from users u
     where u.auth_subject = p_blocked_auth_subject
       and u.status <> 'deleted';
    if not found then
        return jsonb_build_object('code', 'USER_PROFILE_NOT_FOUND');
    end if;
    if v_blocked_id = v_actor_id then
        return jsonb_build_object('code', 'SELF_BLOCK_NOT_ALLOWED');
    end if;

    if p_blocked then
        insert into user_blocks (blocker_id, blocked_id, created_at)
        values (v_actor_id, v_blocked_id, v_updated_at)
        on conflict (blocker_id, blocked_id) do nothing;
    else
        delete from user_blocks
         where blocker_id = v_actor_id and blocked_id = v_blocked_id;
    end if;

    insert into audit_logs (
        actor_id, event_type, target_type, target_id, result, detail, created_at
    ) values (
        v_actor_id,
        case when p_blocked then 'user_blocked' else 'user_unblocked' end,
        'user', v_blocked_id, 'success', '{}'::jsonb, v_updated_at
    ) returning id into v_audit_id;

    return jsonb_build_object(
        'code', 'OK',
        'userId', p_blocked_auth_subject,
        'blocked', p_blocked,
        'auditId', v_audit_id,
        'updatedAt', to_char(v_updated_at at time zone 'UTC',
                            'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
    );
end;
$$;

revoke all on function app.set_own_block(text, boolean) from public;
grant execute on function app.set_own_block(text, boolean) to tetote_app;

commit;
