-- RLS 検証用の土台データ。superuser で投入する（superuser は RLS を常に迂回する）。
-- そのため検証本体は必ず非特権ロール tetote_app で行うこと。

insert into users (id, auth_subject, display_name, area_code, role) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'st_owner',   '依頼 太郎', 'AREA-001', 'member'),
  ('aaaaaaaa-0000-0000-0000-000000000002', 'st_helper',  '支援 花子', 'AREA-001', 'member'),
  ('aaaaaaaa-0000-0000-0000-000000000003', 'st_stranger','無関係 次郎','AREA-001', 'member'),
  ('aaaaaaaa-0000-0000-0000-000000000004', 'st_blocked', 'ブロック相手','AREA-001','member'),
  ('aaaaaaaa-0000-0000-0000-000000000009', 'st_admin',   '管理 三郎', 'AREA-001', 'admin');

-- 公開中の依頼、取消済みの依頼、ブロック相手が出した公開依頼
insert into requests (id, requester_id, title, category_id, area_code, status) values
  ('bbbbbbbb-0000-0000-0000-000000000001','aaaaaaaa-0000-0000-0000-000000000001',
   '犬の散歩', 'pet_support','AREA-001','published'),
  ('bbbbbbbb-0000-0000-0000-000000000002','aaaaaaaa-0000-0000-0000-000000000001',
   '取消した依頼','pet_support','AREA-001','cancelled'),
  ('bbbbbbbb-0000-0000-0000-000000000003','aaaaaaaa-0000-0000-0000-000000000004',
   'ブロック相手の依頼','pet_support','AREA-001','published');

insert into applications (id, request_id, helper_id) values
  ('cccccccc-0000-0000-0000-000000000001','bbbbbbbb-0000-0000-0000-000000000001',
   'aaaaaaaa-0000-0000-0000-000000000002');

insert into matches (id, request_id, helper_id, application_id) values
  ('dddddddd-0000-0000-0000-000000000001','bbbbbbbb-0000-0000-0000-000000000001',
   'aaaaaaaa-0000-0000-0000-000000000002','cccccccc-0000-0000-0000-000000000001');

insert into messages (match_id, sender_id, body) values
  ('dddddddd-0000-0000-0000-000000000001','aaaaaaaa-0000-0000-0000-000000000001','よろしくお願いします');

-- 依頼者がブロック相手をブロックしている
insert into user_blocks (blocker_id, blocked_id) values
  ('aaaaaaaa-0000-0000-0000-000000000001','aaaaaaaa-0000-0000-0000-000000000004');

-- 未承認の実績プロフィール（本人以外から見えてはいけない）
insert into achievement_profiles (user_id, generated_text, model_name, prompt_version,
                                  generated_at, visibility)
values ('aaaaaaaa-0000-0000-0000-000000000002','12件の支援を行いました','claude-x','v1',
        now(),'public');

insert into audit_logs (actor_id, event_type, target_type, result)
values ('aaaaaaaa-0000-0000-0000-000000000009','request.suspend','request','ok');

grant select, insert on all tables in schema public to tetote_app;
