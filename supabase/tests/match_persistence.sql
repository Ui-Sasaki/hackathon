-- 原子選択で作成したmatchの取得範囲と状態整合性を検査する。
begin;

select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000001', true);

do $$
declare
    v_application uuid := 'eeeeeeee-2000-0000-0000-000000000001';
    v_match uuid;
    v_result jsonb;
begin
    v_result := app.select_application(v_application, 7);
    v_match := (v_result ->> 'matchId')::uuid;
    if v_result ->> 'code' <> 'SELECTED'
       or not app.match_is_visible(v_match)
       or (select status from applications where id = v_application) <> 'selected'
       or (select status from requests where title = '原子選択テスト') <> 'matching' then
        raise exception 'FAIL match/application/requestの永続化が不整合: %', v_result;
    end if;
    raise notice 'OK   match/application/requestを整合して永続化';
end;
$$;

-- 無関係な利用者には見せない。
select set_config('app.actor_id', 'aaaaaaaa-0000-0000-0000-000000000003', true);
do $$
begin
    if app.match_is_visible((select id from matches order by created_at desc limit 1)) then
        raise exception 'FAIL 無関係な利用者がmatchを取得できた';
    end if;
    raise notice 'OK   match取得を依頼者と選択支援者に限定';
end;
$$;

rollback;
