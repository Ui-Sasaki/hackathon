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

create or replace function app.application_helper_profile(p_helper_id uuid)
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
    from users u where u.id = p_helper_id;
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
