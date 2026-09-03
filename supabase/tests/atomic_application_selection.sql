-- 応募選択RPCの正常系、認可、競合、定員、原子性を検査する。
begin;

select set_config(
    'app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true
);

do $$
declare
    v_first uuid;
    v_second uuid;
    v_request uuid;
    v_version integer;
    v_result jsonb;
begin
    select r.id, r.version into v_request, v_version
      from requests r where r.title = '原子選択テスト';
    select a.id into v_first from applications a
     where a.request_id = v_request order by a.created_at, a.id limit 1;
    select a.id into v_second from applications a
     where a.request_id = v_request and a.id <> v_first limit 1;

    v_result := app.select_application(v_first, v_version);
    if v_result ->> 'code' <> 'SELECTED' then
        raise exception 'FAIL 1人目の選択: %', v_result;
    end if;
    if (select status from requests where id = v_request) <> 'matching'
       or (select count(*) from matches where request_id = v_request) <> 1 then
        raise exception 'FAIL 1人目の状態更新またはmatch作成';
    end if;

    v_result := app.select_application(v_second, v_version);
    if v_result ->> 'code' <> 'REQUEST_STATE_CONFLICT' then
        raise exception 'FAIL 古いversionを拒否しなかった: %', v_result;
    end if;
    if (select count(*) from matches where request_id = v_request) <> 1 then
        raise exception 'FAIL 競合時に部分更新された';
    end if;

    v_result := app.select_application(
        v_second, (select version from requests where id = v_request));
    if v_result ->> 'code' <> 'SELECTED' then
        raise exception 'FAIL 2人目の選択: %', v_result;
    end if;
    if (select status from requests where id = v_request) <> 'matched'
       or exists (select 1 from applications where request_id = v_request and status = 'applied') then
        raise exception 'FAIL 定員到達時の終了処理';
    end if;
    if app.select_application(v_first, (select version from requests where id = v_request))
       ->> 'code' <> 'REQUEST_STATE_CONFLICT' then
        raise exception 'FAIL matched依頼の再選択を拒否しなかった';
    end if;
    raise notice 'OK   応募選択・定員予約・match作成・残応募終了を原子的に実行';
    raise notice 'OK   version競合と二重選択を結果コードで拒否';
end;
$$;

rollback;
