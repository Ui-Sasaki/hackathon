-- baseline schema の制約が実際に拒否することを確認する。
-- 使い方: psql -v ON_ERROR_STOP=1 -f supabase/tests/baseline_constraints.sql
--
-- 各検査は「この操作は失敗しなければならない」を表明する。成功してしまった場合は
-- exception を投げて全体を失敗させる。制約を書いただけで効いていない状態を検出するのが目的。

begin;

create or replace function assert_rejected(stmt text, label text)
returns void language plpgsql as $$
begin
    begin
        execute stmt;
    exception when others then
        raise notice 'OK   %  (% )', label, sqlstate;
        return;
    end;
    raise exception 'FAIL % : 拒否されるべき操作が成功した', label;
end;
$$;

-- 検査用の土台データ
insert into users (id, auth_subject, display_name, area_code)
values ('11111111-1111-1111-1111-111111111111', 'st_a', '依頼 太郎', 'AREA-001'),
       ('22222222-2222-2222-2222-222222222222', 'st_b', '支援 花子', 'AREA-001');

insert into requests (id, requester_id, title, category_id, area_code, status)
values ('33333333-3333-3333-3333-333333333333',
        '11111111-1111-1111-1111-111111111111', '犬の散歩', 'pet_support', 'AREA-001', 'published');

insert into applications (id, request_id, helper_id)
values ('44444444-4444-4444-4444-444444444444',
        '33333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222');

-- 1. 同一依頼への重複応募（#6）
select assert_rejected($x$
  insert into applications (request_id, helper_id)
  values ('33333333-3333-3333-3333-333333333333','22222222-2222-2222-2222-222222222222')
$x$, '重複応募');

-- 2. 座標の片側だけ（位置情報の部分更新バグ検出）
select assert_rejected($x$
  insert into requests (requester_id, title, category_id, area_code, approximate_latitude)
  values ('11111111-1111-1111-1111-111111111111','片側座標','pet_support','AREA-001', 35.6)
$x$, '座標の片側のみ');

-- 3. 緯度の範囲外
select assert_rejected($x$
  insert into requests (requester_id, title, category_id, area_code,
                        approximate_latitude, approximate_longitude)
  values ('11111111-1111-1111-1111-111111111111','範囲外','pet_support','AREA-001', 200, 100)
$x$, '緯度が範囲外');

-- 4. 自分自身のブロック（#14）
select assert_rejected($x$
  insert into user_blocks (blocker_id, blocked_id)
  values ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111111')
$x$, '自分自身のブロック');

-- 5. 自分自身へのレビュー（#10）
select assert_rejected($x$
  insert into reviews (match_id, reviewer_id, reviewee_id)
  values ('55555555-5555-5555-5555-555555555555',
          '11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111111')
$x$, '自分自身へのレビュー');

-- 6. 生成文があるのに model / prompt 版が無い（#10 のトレーサビリティ）
select assert_rejected($x$
  insert into achievement_profiles (user_id, generated_text)
  values ('22222222-2222-2222-2222-222222222222','12件の支援を行いました')
$x$, '生成メタデータの欠落');

-- 7. completed なのに completed_at が無い（#9）
insert into matches (id, request_id, helper_id, application_id)
values ('66666666-6666-6666-6666-666666666666','33333333-3333-3333-3333-333333333333',
        '22222222-2222-2222-2222-222222222222','44444444-4444-4444-4444-444444444444');
select assert_rejected($x$
  update matches set status='completed'
   where id='66666666-6666-6666-6666-666666666666'
$x$, '完了時刻なしの completed');

-- 8. 未処理の本人確認申請が1利用者に2件（partial unique index）
insert into verification_requests (user_id, status)
values ('22222222-2222-2222-2222-222222222222','pending');
select assert_rejected($x$
  insert into verification_requests (user_id, status)
  values ('22222222-2222-2222-2222-222222222222','pending')
$x$, '未処理の本人確認申請が2件');

-- 9. 申請 status に unverified（利用者の状態であって申請の状態ではない）
select assert_rejected($x$
  insert into verification_requests (user_id, status)
  values ('11111111-1111-1111-1111-111111111111','unverified')
$x$, '申請 status が unverified');

-- 10. 通報の target_type が許可外
select assert_rejected($x$
  insert into reports (reporter_id, target_type, target_id, reason, description)
  values ('11111111-1111-1111-1111-111111111111','payment',
          '33333333-3333-3333-3333-333333333333','spam','説明')
$x$, '通報の target_type が許可外');

-- 11. resolved なのに処理者が無い（#11 の監査可能性）
insert into reports (id, reporter_id, target_type, target_id, reason, description)
values ('77777777-7777-7777-7777-777777777777','11111111-1111-1111-1111-111111111111',
        'request','33333333-3333-3333-3333-333333333333','spam','説明');
select assert_rejected($x$
  update reports set status='resolved', resolved_at=now()
   where id='77777777-7777-7777-7777-777777777777'
$x$, '処理者なしの resolved');

-- 12. 監査ログの event_type が空
select assert_rejected($x$
  insert into audit_logs (event_type, target_type, result)
  values ('   ','request','ok')
$x$, '空の event_type');

-- 13. FK 違反（存在しない利用者の依頼）
select assert_rejected($x$
  insert into requests (requester_id, title, category_id, area_code)
  values ('99999999-9999-9999-9999-999999999999','幽霊','pet_support','AREA-001')
$x$, '存在しない requester への FK');

-- 14. auth_subject の重複（SuperTokens ID の一意性）
select assert_rejected($x$
  insert into users (auth_subject, display_name) values ('st_a','別人')
$x$, 'auth_subject の重複');

-- 正常系: 上記の土台データが全て入っていること
do $$
declare n integer;
begin
    select count(*) into n from users;
    if n <> 2 then raise exception 'FAIL 土台データ: users が % 件', n; end if;
    raise notice 'OK   正常系の投入';
end;
$$;

rollback;
