insert into users (
    id, auth_subject, display_name, email_verified, verification_status, area_code
) values (
    'aaaaaaaa-1000-0000-0000-000000000001',
    'st_application_helper', '応募 支援者', true, 'unverified', 'AREA-001'
);

insert into requests (
    id, requester_id, title, category_id, area_code, status, expires_at,
    verification_required, created_at
) values
('aaaaaaaa-2000-0000-0000-000000000001',
 (select id from users where auth_subject = 'st_owner'),
 '応募永続化テスト', 'other', 'AREA-001', 'published', now() + interval '1 day', false, now()),
('aaaaaaaa-2000-0000-0000-000000000002',
 (select id from users where auth_subject = 'st_owner'),
 '期限切れ応募テスト', 'other', 'AREA-001', 'published', now() - interval '1 day', false,
 now() - interval '2 days'),
('aaaaaaaa-2000-0000-0000-000000000003',
 (select id from users where auth_subject = 'st_owner'),
 '本人確認必須応募テスト', 'other', 'AREA-001', 'published', now() + interval '1 day', true, now());
