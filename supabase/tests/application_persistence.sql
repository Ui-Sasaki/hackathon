-- #20 応募永続化の制約・RLS・状態遷移検査。tetote_app で実行する。
begin;

select set_config(
    'app.actor_id', 'eeeeeeee-0000-0000-0000-000000000001', true
);

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
        insert into applications (request_id, helper_id) values
            ('eeeeeeee-1000-0000-0000-000000000002', app.current_actor());
        raise exception 'FAIL 期限切れ応募が成功した';
    exception when insufficient_privilege then
        raise notice 'OK   期限切れ応募をRLSで拒否';
    end;

    begin
        insert into applications (request_id, helper_id) values
            ('eeeeeeee-1000-0000-0000-000000000003', app.current_actor());
        raise exception 'FAIL 未確認ユーザーの応募が成功した';
    exception when insufficient_privilege then
        raise notice 'OK   本人確認必須応募をRLSで拒否';
    end;
end;
$$;

rollback;
