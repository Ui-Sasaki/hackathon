-- 完了確認とdisputeの原子状態遷移を検査する。
begin;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);
select set_config(
    'test.completion_match_id',
    (app.select_application('eeeeeeee-2000-0000-0000-000000000001', 7) ->> 'matchId'),
    true
);

do $$
declare
    v_match uuid := current_setting('test.completion_match_id')::uuid;
    v_result jsonb;
    v_match_status match_status;
    v_request_status request_status;
begin
    v_result := app.complete_match(v_match);
    select status into v_match_status from matches where id = v_match;
    select r.status into v_request_status
      from requests r join matches m on m.request_id = r.id where m.id = v_match;
    if v_result ->> 'code' <> 'CONFIRMED'
       or v_match_status <> 'completion_pending'
       or v_request_status <> 'completion_pending' then
        raise exception 'FAIL 片方の完了確認 result=% match=% request=%',
            v_result, v_match_status, v_request_status;
    end if;
    if app.complete_match(v_match) ->> 'code' <> 'COMPLETION_ALREADY_CONFIRMED' then
        raise exception 'FAIL 重複完了確認を拒否しなかった';
    end if;
    raise notice 'OK   片方の確認を保存しcompletion_pendingへ遷移';
    raise notice 'OK   重複完了確認を競合として拒否';
end;
$$;

select set_config('app.actor_id', 'ffffffff-0000-0000-0000-000000000001', true);
do $$
declare
    v_match uuid := current_setting('test.completion_match_id')::uuid;
    v_result jsonb;
    v_match_status match_status;
    v_application_status application_status;
    v_request_status request_status;
begin
    v_result := app.complete_match(v_match);
    select status into v_match_status from matches where id = v_match;
    select status into v_application_status from applications
     where id = 'eeeeeeee-2000-0000-0000-000000000001';
    select r.status into v_request_status
      from requests r join matches m on m.request_id = r.id where m.id = v_match;
    if v_result ->> 'code' <> 'CONFIRMED'
       or v_match_status <> 'completed'
       or v_application_status <> 'completed'
       or v_request_status <> 'completed' then
        raise exception 'FAIL 双方完了後の原子遷移 result=% match=% application=% request=%',
            v_result, v_match_status, v_application_status, v_request_status;
    end if;
    raise notice 'OK   双方確認後にmatch/application/requestをcompletedへ原子遷移';
end;
$$;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);
do $$
declare
    v_match uuid;
    v_result jsonb;
begin
    select m.id into v_match from matches m join requests r on r.id = m.request_id
     where r.title = '同時選択テスト';
    v_result := app.dispute_match(v_match, '作業内容について認識の相違があります');
    if v_result ->> 'code' <> 'DISPUTED'
       or v_result ->> 'auditLogId' is null
       or (select status from matches where id = v_match) <> 'disputed'
       or (select r.status from requests r join matches m on m.request_id = r.id
            where m.id = v_match) <> 'disputed' then
        raise exception 'FAIL disputeの原子遷移または監査ログ result=%', v_result;
    end if;
    if app.dispute_match(v_match, '重複した申告を拒否してください')
       ->> 'code' <> 'MATCH_NOT_DISPUTABLE' then
        raise exception 'FAIL dispute重複を拒否しなかった';
    end if;
    raise notice 'OK   disputeでmatch/request/監査ログを原子更新';
    raise notice 'OK   不正状態遷移を競合として拒否';
end;
$$;

rollback;
