-- チャットの永続化、server-owned fields、既読、認可、ブロックを検査する。
begin;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);

do $$
declare
    v_result jsonb;
    v_match uuid;
    v_message uuid;
begin
    v_result := app.select_application(
        'eeeeeeee-2000-0000-0000-000000000001', 7
    );
    v_match := (v_result ->> 'matchId')::uuid;
    v_result := app.send_match_message(v_match, '依頼者からのメッセージ', 'clean');
    v_message := (v_result ->> 'messageId')::uuid;
    if v_result ->> 'code' <> 'SENT'
       or (select sender_id from messages where id = v_message) <> app.current_actor()
       or (select sent_at from messages where id = v_message) is null then
        raise exception 'FAIL sender IDまたは送信日時がDBで保存されていない';
    end if;
    perform set_config('test.match_id', v_match::text, true);
    raise notice 'OK   sender IDと送信日時をDBで決定して保存';
end;
$$;

select set_config('app.actor_id', 'ffffffff-0000-0000-0000-000000000001', true);
do $$
declare
    v_match uuid := current_setting('test.match_id')::uuid;
    v_marked integer;
    v_unread integer;
begin
    v_marked := app.mark_match_messages_read(v_match);
    select count(*) into v_unread
      from messages where match_id = v_match and read_at is null;
    if v_marked <> 1 or v_unread <> 0 then
        raise exception 'FAIL 既読状態が保存されていない marked=% unread=%',
            v_marked, v_unread;
    end if;
    raise notice 'OK   選択支援者だけが取得でき、既読状態を保存';

    insert into user_blocks (blocker_id, blocked_id)
    values (app.current_actor(), 'aaaaaaaa-0000-0000-0000-000000000001');
    if app.match_is_visible(v_match)
       or app.send_match_message(v_match, '送信不可', 'clean') ->> 'code' <> 'MATCH_NOT_FOUND' then
        raise exception 'FAIL ブロック後も取得または送信できた';
    end if;
    raise notice 'OK   ブロック後の取得・送信を拒否';
end;
$$;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000003', true);
do $$
begin
    if app.send_match_message(current_setting('test.match_id')::uuid, '部外者', 'clean')
       ->> 'code' <> 'MATCH_NOT_FOUND' then
        raise exception 'FAIL 当事者以外が送信できた';
    end if;
    raise notice 'OK   マッチ当事者以外の取得・送信を拒否';
end;
$$;

rollback;
