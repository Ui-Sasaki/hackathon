-- Matching/chat transition, RLS and no-partial-write tests. Run as tetote_app.
begin;

select set_config('app.actor_id', '10000000-0000-0000-0000-000000000001', true);

do $$
declare
    v_result jsonb;
begin
    v_result := app.select_application(
        '30000000-0000-0000-0000-000000000001',
        '20000000-0000-0000-0000-000000000001', 1
    );
    if v_result ->> 'code' <> 'OK' then
        raise exception 'FAIL 選択が成功しない: %', v_result;
    end if;
    if (select status from requests where id = '20000000-0000-0000-0000-000000000001') <> 'matched'
       or (select status from applications where id = '30000000-0000-0000-0000-000000000001') <> 'selected' then
        raise exception 'FAIL 選択後の状態が原子的に保存されていない';
    end if;
    raise notice 'OK   選択・match作成・依頼状態を原子的に保存';
end;
$$;

select set_config(
    'test.match_id',
    (select id::text from matches
      where request_id = '20000000-0000-0000-0000-000000000001'),
    true
);

-- A non-party cannot discover the match or its messages through RLS.
select set_config('app.actor_id', '10000000-0000-0000-0000-000000000004', true);
do $$
declare
    v_result jsonb;
begin
    if exists (
        select 1 from matches where request_id = '20000000-0000-0000-0000-000000000001'
    ) or exists (
        select 1 from messages msg join matches m on m.id = msg.match_id
         where m.request_id = '20000000-0000-0000-0000-000000000001'
    ) then
        raise exception 'FAIL 非当事者がmatch/chatを閲覧できた';
    end if;
    v_result := app.send_message(
        current_setting('test.match_id')::uuid, '第三者は送信できない'
    );
    if v_result ->> 'code' <> 'ROLE_FORBIDDEN' then
        raise exception 'FAIL 非当事者のchat送信が拒否されない: %', v_result;
    end if;
    if has_function_privilege(
        current_user, 'app.application_helper_profile(uuid)', 'EXECUTE'
    ) or app.application_helper_profile_for_application(
        '30000000-0000-0000-0000-000000000001'
    ) is not null then
        raise exception 'FAIL 応募者プロフィール関数の参照範囲が過剰';
    end if;
    raise notice 'OK   RLS/RPCで非当事者のmatch/chat取得・送信を拒否';
    raise notice 'OK   応募ID限定プロフィール関数と旧関数の権限取消を確認';
end;
$$;

-- The helper can send; the server supplies sent_at and the requester marks it read.
select set_config('app.actor_id', '10000000-0000-0000-0000-000000000002', true);
do $$
declare
    v_match_id uuid;
    v_result jsonb;
begin
    select id into v_match_id from matches
     where request_id = '20000000-0000-0000-0000-000000000001';
    v_result := app.send_message(v_match_id, '支援できます');
    if v_result ->> 'code' <> 'OK' or not exists (
        select 1 from messages where id = (v_result ->> 'messageId')::uuid
          and sender_id = app.current_actor() and sent_at is not null
    ) then
        raise exception 'FAIL 当事者メッセージがserver時刻で保存されない';
    end if;
    raise notice 'OK   当事者メッセージをserver時刻で保存';
end;
$$;

select set_config('app.actor_id', '10000000-0000-0000-0000-000000000001', true);
do $$
declare
    v_match_id uuid;
    v_before integer;
    v_result jsonb;
begin
    select id into v_match_id from matches
     where request_id = '20000000-0000-0000-0000-000000000001';
    v_result := app.mark_messages_read(v_match_id);
    if v_result ->> 'code' <> 'OK' or exists (
        select 1 from messages where match_id = v_match_id and read_at is null
    ) then
        raise exception 'FAIL 既読更新が保存されない';
    end if;

    insert into user_blocks (blocker_id, blocked_id)
    values (app.current_actor(), '10000000-0000-0000-0000-000000000002');
    select count(*) into v_before from messages where match_id = v_match_id;
    v_result := app.send_message(v_match_id, 'ブロック後は送れない');
    if v_result ->> 'code' <> 'MESSAGE_FORBIDDEN'
       or (select count(*) from messages where match_id = v_match_id) <> v_before then
        raise exception 'FAIL ブロック後送信でDBが変更された: %', v_result;
    end if;
    raise notice 'OK   block後の送信をDB無変更で拒否';
end;
$$;

-- Duplicate completion and terminal-state transitions must not mutate rows.
do $$
declare
    v_match_id uuid;
    v_result jsonb;
begin
    select id into v_match_id from matches
     where request_id = '20000000-0000-0000-0000-000000000001';
    v_result := app.complete_match(v_match_id, 'requester');
    if v_result ->> 'code' <> 'OK' then
        raise exception 'FAIL 依頼者完了が成功しない: %', v_result;
    end if;
    v_result := app.complete_match(v_match_id, 'requester');
    if v_result ->> 'code' <> 'MATCH_NOT_COMPLETABLE'
       or (select helper_confirmed from matches where id = v_match_id) then
        raise exception 'FAIL 重複完了でDBが変更された: %', v_result;
    end if;
    raise notice 'OK   重複完了をDB無変更で拒否';
end;
$$;

select set_config('app.actor_id', '10000000-0000-0000-0000-000000000002', true);
do $$
declare
    v_match_id uuid;
    v_result jsonb;
    v_completed_at timestamptz;
begin
    select id into v_match_id from matches
     where request_id = '20000000-0000-0000-0000-000000000001';
    v_result := app.complete_match(v_match_id, 'helper');
    select completed_at into v_completed_at from matches where id = v_match_id;
    if v_result ->> 'code' <> 'OK' or v_completed_at is null then
        raise exception 'FAIL 双方完了が保存されない: %', v_result;
    end if;
    v_result := app.dispute_match(v_match_id, '完了後には遷移できない理由');
    if v_result ->> 'code' <> 'MATCH_NOT_DISPUTABLE'
       or (select status from matches where id = v_match_id) <> 'completed'
       or (select completed_at from matches where id = v_match_id) <> v_completed_at then
        raise exception 'FAIL completed後disputeでDBが変更された: %', v_result;
    end if;
    raise notice 'OK   completed後の不正遷移をDB無変更で拒否';
end;
$$;

-- Request cancellation closes pending applications in the same RPC.
select set_config('app.actor_id', '10000000-0000-0000-0000-000000000001', true);
do $$
begin
    perform app.set_request_status(
        '20000000-0000-0000-0000-000000000003', 'cancelled', 1, true
    );
    if (select status from requests where id = '20000000-0000-0000-0000-000000000003') <> 'cancelled'
       or (select status from applications where id = '30000000-0000-0000-0000-000000000004') <> 'cancelled' then
        raise exception 'FAIL 依頼取消と応募取消が原子的でない';
    end if;
    raise notice 'OK   依頼取消と未処理応募取消を原子的に保存';
end;
$$;

rollback;
