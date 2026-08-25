-- #20 応募永続化の制約・RLS・状態遷移検査。tetote_app で実行する。
begin;

select set_config('app.actor_id',
    'aaaaaaaa-0000-0000-0000-000000000020', true);

-- 公開・期限内の依頼には本人名義で応募できる。
insert into applications (request_id, helper_id, message, available_at)
select r.id, app.current_actor(), '対応できます', now() + interval '1 hour'
  from requests r where r.title = '応募永続化テスト';

do $$
begin
    begin
        insert into applications (request_id, helper_id)
        select r.id, app.current_actor() from requests r where r.title = '応募永続化テスト';
        raise exception 'FAIL 重複応募が成功した';
    exception when unique_violation then
        raise notice 'OK   重複応募を一意制約で拒否';
    end;
end;
$$;

select app.withdraw_application(
    (select a.id from applications a
      join requests r on r.id = a.request_id where r.title = '応募永続化テスト')
);

do $$
begin
    if not exists (
        select 1 from applications a join requests r on r.id = a.request_id
         where r.title = '応募永続化テスト' and a.status = 'withdrawn'
    ) then
        raise exception 'FAIL 取り下げ状態が保存されていない';
    end if;
    if app.withdraw_application(
        (select a.id from applications a join requests r on r.id = a.request_id
          where r.title = '応募永続化テスト')
    ) is not null then
        raise exception 'FAIL withdrawnから再遷移できた';
    end if;
    raise notice 'OK   appliedからwithdrawnだけを許可';
end;
$$;

do $$
begin
    begin
        insert into applications (request_id, helper_id)
        values ('bbbbbbbb-0000-0000-0000-000000000021', app.current_actor());
        raise exception 'FAIL 期限切れ応募が成功した';
    exception when insufficient_privilege then
        raise notice 'OK   期限切れ応募をRLSで拒否';
    end;

    begin
        insert into applications (request_id, helper_id)
        values ('bbbbbbbb-0000-0000-0000-000000000022', app.current_actor());
        raise exception 'FAIL 未確認ユーザーの応募が成功した';
    exception when insufficient_privilege then
        raise notice 'OK   本人確認必須応募をRLSで拒否';
    end;
end;
$$;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);
do $$
begin
    begin
        insert into applications (request_id, helper_id)
        values ('bbbbbbbb-0000-0000-0000-000000000020', app.current_actor());
        raise exception 'FAIL 自分の依頼への応募が成功した';
    exception when insufficient_privilege then
        raise notice 'OK   自分の依頼への応募をRLSで拒否';
    end;
end;
$$;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000021', true);
insert into applications (request_id, helper_id, message, available_at)
values ('bbbbbbbb-0000-0000-0000-000000000020', app.current_actor(),
        '選択してください', now() + interval '1 hour');

-- 依頼取消と応募取消は、後続処理が失敗した場合にまとめてrollbackされる。
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000020', true);
insert into applications (request_id, helper_id)
values ('bbbbbbbb-0000-0000-0000-000000000001', app.current_actor());
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);
do $$
begin
    begin
        perform app.set_request_status(
            'bbbbbbbb-0000-0000-0000-000000000001', 'cancelled', null, true
        );
        raise exception '後続処理失敗';
    exception when raise_exception then
        null;
    end;
    if (select status from requests
         where id = 'bbbbbbbb-0000-0000-0000-000000000001') <> 'published' then
        raise exception 'FAIL 依頼状態がrollbackされていない';
    end if;
    if (select status from applications
         where request_id = 'bbbbbbbb-0000-0000-0000-000000000001'
           and helper_id = 'aaaaaaaa-0000-0000-0000-000000000020') <> 'applied' then
        raise exception 'FAIL 応募状態がrollbackされていない';
    end if;
    raise notice 'OK   依頼取消と応募取消を同一トランザクションでrollback';
end;
$$;

-- 応募者選択は応募・マッチ・依頼を一括更新し、古いversionを拒否する。
do $$
declare
    v_application_id uuid;
    v_result jsonb;
begin
    select id into v_application_id from applications
     where request_id = 'bbbbbbbb-0000-0000-0000-000000000020'
       and helper_id = 'aaaaaaaa-0000-0000-0000-000000000021';
    v_result := app.select_application(
        v_application_id,
        'bbbbbbbb-0000-0000-0000-000000000020',
        (select version from requests where id = 'bbbbbbbb-0000-0000-0000-000000000020')
    );
    if v_result ->> 'code' <> 'OK' then
        raise exception 'FAIL 応募者選択が失敗した: %', v_result;
    end if;
    if (select status from applications where id = v_application_id) <> 'selected'
       or not exists (select 1 from matches where application_id = v_application_id)
       or (select status from requests
            where id = 'bbbbbbbb-0000-0000-0000-000000000020') <> 'matched' then
        raise exception 'FAIL 応募・マッチ・依頼が一括更新されていない';
    end if;
    v_result := app.select_application(
        v_application_id,
        'bbbbbbbb-0000-0000-0000-000000000020', 1
    );
    if v_result ->> 'code' <> 'REQUEST_STATE_CONFLICT' then
        raise exception 'FAIL 古いversionが拒否されなかった: %', v_result;
    end if;
    raise notice 'OK   応募者選択をDBトランザクションとversionで排他制御';
end;
$$;

-- チャット既読と双方完了もDBへ永続化する。
do $$
declare
    v_match_id uuid;
    v_message_id uuid;
    v_result jsonb;
begin
    select id into v_match_id from matches
     where request_id = 'bbbbbbbb-0000-0000-0000-000000000020';
    v_message_id := app.send_message(v_match_id, 'よろしくお願いします');
    if v_message_id is null then
        raise exception 'FAIL マッチ当事者がメッセージを送信できない';
    end if;

    perform set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000021', true);
    perform app.mark_messages_read(v_match_id);
    if (select read_at from messages where id = v_message_id) is null then
        raise exception 'FAIL 既読時刻が保存されていない';
    end if;
    v_result := app.complete_match(v_match_id, 'helper');
    if v_result ->> 'code' <> 'OK' then
        raise exception 'FAIL 支援者の完了確認に失敗: %', v_result;
    end if;

    perform set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);
    v_result := app.complete_match(v_match_id, 'requester');
    if v_result ->> 'code' <> 'OK'
       or (select status from matches where id = v_match_id) <> 'completed'
       or (select status from requests
            where id = 'bbbbbbbb-0000-0000-0000-000000000020') <> 'completed' then
        raise exception 'FAIL 双方完了がマッチと依頼へ保存されていない: %', v_result;
    end if;
    raise notice 'OK   チャット既読と双方完了をPostgreSQLへ永続化';
end;
$$;

rollback;
