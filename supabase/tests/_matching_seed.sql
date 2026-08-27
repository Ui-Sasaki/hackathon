-- Matching persistence fixtures. Loaded as the database owner before RLS tests.
insert into users (id, auth_subject, display_name, email_verified, verification_status, area_code)
values
('10000000-0000-0000-0000-000000000001', 'st_match_owner', 'マッチ依頼者', true, 'approved', 'AREA-001'),
('10000000-0000-0000-0000-000000000002', 'st_match_helper_a', '支援者A', true, 'approved', 'AREA-001'),
('10000000-0000-0000-0000-000000000003', 'st_match_helper_b', '支援者B', true, 'approved', 'AREA-001'),
('10000000-0000-0000-0000-000000000004', 'st_match_outsider', '第三者', true, 'approved', 'AREA-001');

insert into requests (
    id, requester_id, title, category_id, area_code, status, required_helpers, version
) values
('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001',
 'マッチ永続化テスト', 'other', 'AREA-001', 'published', 1, 1),
('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000001',
 'マッチ同時選択テスト', 'other', 'AREA-001', 'published', 1, 1),
('20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000001',
 '依頼取消テスト', 'other', 'AREA-001', 'published', 1, 1);

insert into applications (
    id, request_id, helper_id, message, available_at
) values
('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001',
 '10000000-0000-0000-0000-000000000002', '通常経路', now()),
('30000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000002',
 '10000000-0000-0000-0000-000000000002', '同時選択A', now()),
('30000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000002',
 '10000000-0000-0000-0000-000000000003', '同時選択B', now()),
('30000000-0000-0000-0000-000000000004', '20000000-0000-0000-0000-000000000003',
 '10000000-0000-0000-0000-000000000002', '取消対象', now());
