insert into users (
    id, auth_subject, display_name, email_verified, verification_status, area_code
) values
('ffffffff-0000-0000-0000-000000000001',
 'st_selection_helper_1', '選択 支援者1', true, 'approved', 'AREA-001'),
('ffffffff-0000-0000-0000-000000000002',
 'st_selection_helper_2', '選択 支援者2', true, 'approved', 'AREA-001'),
('ffffffff-0000-0000-0000-000000000003',
 'st_selection_helper_3', '選択 支援者3', true, 'approved', 'AREA-001');

insert into requests (
    requester_id, title, category_id, area_code, status, expires_at,
    verification_required, required_helpers, version
) values
((select id from users where auth_subject = 'st_owner'),
 '原子選択テスト', 'other', 'AREA-001', 'published', now() + interval '1 day',
 false, 2, 7),
((select id from users where auth_subject = 'st_owner'),
 '同時選択テスト', 'other', 'AREA-001', 'published', now() + interval '1 day',
 false, 1, 11);

insert into applications (id, request_id, helper_id, message)
select case u.auth_subject
           when 'st_selection_helper_1' then 'eeeeeeee-2000-0000-0000-000000000001'::uuid
           when 'st_selection_helper_2' then 'eeeeeeee-2000-0000-0000-000000000002'::uuid
           else 'eeeeeeee-2000-0000-0000-000000000003'::uuid
       end, r.id, u.id, '選択してください'
  from requests r
  cross join users u
 where r.title = '原子選択テスト'
   and u.auth_subject in ('st_selection_helper_1', 'st_selection_helper_2', 'st_selection_helper_3');

insert into applications (id, request_id, helper_id, message)
select case u.auth_subject
           when 'st_selection_helper_1' then 'eeeeeeee-3000-0000-0000-000000000001'::uuid
           else 'eeeeeeee-3000-0000-0000-000000000002'::uuid
       end, r.id, u.id, '同時実行応募'
  from requests r
  cross join users u
 where r.title = '同時選択テスト'
   and u.auth_subject in ('st_selection_helper_1', 'st_selection_helper_2');
