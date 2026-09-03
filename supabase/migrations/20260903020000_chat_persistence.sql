-- チャット送信者・送信時刻・既読をDBで決定し、当事者とブロック状態を再検証する。

begin;

create or replace function app.send_match_message(
    p_match_id uuid,
    p_body text,
    p_moderation moderation_status default 'clean'
)
returns jsonb language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_message_id uuid;
begin
    if not app.match_is_visible(p_match_id) then
        return jsonb_build_object('code', 'MATCH_NOT_FOUND');
    end if;
    if length(trim(p_body)) not between 1 and 4000 then
        return jsonb_build_object('code', 'INVALID_MESSAGE');
    end if;
    insert into messages (match_id, sender_id, body, moderation, sent_at)
    values (p_match_id, app.current_actor(), p_body, p_moderation, now())
    returning id into v_message_id;
    return jsonb_build_object('code', 'SENT', 'messageId', v_message_id);
end;
$$;

create or replace function app.mark_match_messages_read(p_match_id uuid)
returns integer language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_count integer;
begin
    if not app.match_is_visible(p_match_id) then
        return 0;
    end if;
    update messages
       set read_at = now()
     where match_id = p_match_id
       and sender_id <> app.current_actor()
       and read_at is null;
    get diagnostics v_count = row_count;
    return v_count;
end;
$$;

revoke all on function app.send_match_message(uuid, text, moderation_status) from public;
revoke all on function app.mark_match_messages_read(uuid) from public;
grant execute on function app.send_match_message(uuid, text, moderation_status) to tetote_app;
grant execute on function app.mark_match_messages_read(uuid) to tetote_app;

commit;
