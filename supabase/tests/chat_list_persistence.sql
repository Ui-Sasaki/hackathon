-- チャット一覧の当事者認可、表示用概要、ブロック除外を検査する。
begin;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000002', true);

do $$
declare
    v_count integer;
    v_counterpart text;
    v_title text;
begin
    select count(*), max(counterpart_display_name), max(request_title)
      into v_count, v_counterpart, v_title
      from app.list_own_chat_matches();
    if v_count <> 1 or v_counterpart <> '依頼 太郎' or v_title <> '犬の散歩' then
        raise exception 'FAIL 当事者向けチャット一覧の概要が不正 count=% counterpart=% title=%',
            v_count, v_counterpart, v_title;
    end if;
    raise notice 'OK   当事者へ相手名と依頼概要を返す';
end;
$$;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000003', true);
do $$
begin
    if exists (select 1 from app.list_own_chat_matches()) then
        raise exception 'FAIL 当事者以外へチャット一覧が公開された';
    end if;
    raise notice 'OK   当事者以外へチャット一覧を公開しない';
end;
$$;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000002', true);
insert into user_blocks (blocker_id, blocked_id)
values (app.current_actor(), 'aaaaaaaa-0000-0000-0000-000000000001');

do $$
begin
    if exists (select 1 from app.list_own_chat_matches()) then
        raise exception 'FAIL ブロック相手とのチャットが一覧に残った';
    end if;
    raise notice 'OK   ブロック相手とのチャットを一覧から除外';
end;
$$;

rollback;
