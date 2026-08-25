insert into users (
    auth_subject, display_name, email_verified, verification_status, area_code
) values ('st_application_helper', '応募 支援者', true, 'unverified', 'AREA-001');

insert into requests (
    requester_id, title, category_id, area_code, status, expires_at,
    verification_required
) values
((select id from users where auth_subject = 'st_owner'),
 '応募永続化テスト', 'other', 'AREA-001', 'published', now() + interval '1 day', false),
((select id from users where auth_subject = 'st_owner'),
 '期限切れ応募テスト', 'other', 'AREA-001', 'published', now() - interval '1 day', false),
((select id from users where auth_subject = 'st_owner'),
 '本人確認必須応募テスト', 'other', 'AREA-001', 'published', now() + interval '1 day', true);
