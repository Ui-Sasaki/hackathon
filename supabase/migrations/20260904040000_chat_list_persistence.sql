-- チャット一覧に必要な安全な概要だけを、認証済み当事者へ返す。

begin;

create or replace function app.list_own_chat_matches()
returns table (
    id uuid,
    request_id uuid,
    requester_auth_subject text,
    helper_auth_subject text,
    status match_status,
    requester_confirmed boolean,
    helper_confirmed boolean,
    matched_at timestamptz,
    completed_at timestamptz,
    dispute_reason text,
    disputed_at timestamptz,
    counterpart_display_name text,
    request_title text,
    request_scheduled_at timestamptz,
    request_area_code text
) language sql stable security definer
set search_path = public, pg_temp as $$
    select m.id, m.request_id,
           requester.auth_subject, helper.auth_subject,
           m.status, m.requester_confirmed, m.helper_confirmed,
           m.matched_at, m.completed_at, m.dispute_reason, m.disputed_at,
           case when r.requester_id = app.current_actor()
                then helper.display_name else requester.display_name end,
           r.title, r.scheduled_at, r.area_code
      from matches m
      join requests r on r.id = m.request_id
      join users requester on requester.id = r.requester_id
      join users helper on helper.id = m.helper_id
     where app.match_is_visible(m.id)
     order by m.matched_at desc, m.id desc;
$$;

revoke all on function app.list_own_chat_matches() from public;
grant execute on function app.list_own_chat_matches() to tetote_app;

commit;
