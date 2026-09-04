-- マッチ詳細取得に必要な当事者・利用状態・ブロック判定をRLSの外側へ漏らさない。

begin;

create or replace function app.match_is_visible(p_match_id uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
    select exists (
        select 1
          from matches m
          join requests r on r.id = m.request_id
          join users requester on requester.id = r.requester_id
          join users helper on helper.id = m.helper_id
         where m.id = p_match_id
           and (r.requester_id = app.current_actor()
                or m.helper_id = app.current_actor())
           and requester.status = 'active'
           and helper.status = 'active'
           and not app.is_blocked_pair(r.requester_id, m.helper_id)
    );
$$;

revoke all on function app.match_is_visible(uuid) from public;
grant execute on function app.match_is_visible(uuid) to tetote_app;

commit;
