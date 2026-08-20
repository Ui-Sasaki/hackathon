-- テトテ baseline schema
--
-- #19 の baseline。#4〜#11 が必要とする全テーブル、enum、制約、index、RLS を1本にまとめる。
-- merge 後はこのファイルを編集せず、変更は必ず新しい migration を追加する。
--
-- 設計の根拠は要件定義書 §5（ユーザー種別・権限）、§8（状態管理）、§9（データ要件）。
-- 要件定義書 §4「推奨システム構成」は Next.js / Vercel / Vercel Cron を前提にしており
-- 現在の FastAPI 構成と一致しないため、根拠に使っていない。

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- enum
--
-- 削除と rename は破壊的なので行わない。追加は後続 migration での末尾追加とする。
-- ---------------------------------------------------------------------------

create type account_role as enum ('member', 'admin', 'verifier');

create type user_status as enum ('active', 'suspended', 'deleted');

create type verification_status as enum (
    'unverified', 'pending', 'approved', 'rejected', 'expired'
);

create type request_status as enum (
    'draft', 'pending_review', 'published', 'matching', 'matched', 'in_progress',
    'completion_pending', 'completed', 'rejected', 'cancelled', 'expired',
    'suspended', 'disputed'
);

create type application_status as enum (
    'applied', 'selected', 'accepted', 'completed', 'not_selected', 'withdrawn', 'cancelled'
);

-- 要件定義書 §8 はマッチ専用の状態を列挙していないため、#9 / #13 と §8 の語彙から切り出す。
create type match_status as enum (
    'matched', 'in_progress', 'completion_pending', 'completed', 'disputed', 'cancelled'
);

create type risk_level as enum ('low', 'medium', 'high', 'prohibited');

create type achievement_visibility as enum ('private', 'unlisted', 'public');

create type report_severity as enum ('low', 'medium', 'high', 'critical');

create type report_status as enum ('open', 'investigating', 'resolved', 'rejected');

create type moderation_status as enum ('clean', 'flagged', 'blocked', 'pending');

-- ---------------------------------------------------------------------------
-- users
--
-- 認証は SuperTokens であり Supabase Auth ではない。auth_subject が SuperTokens の
-- 利用者 ID との対応を持ち、権限判定の正本はこの行である。
-- role は利用者の永続的な種別だけを表す。依頼者・支援者は requests / matches の
-- 所有関係から判定される文脈上のアクターであり、ここには持たない。
-- ---------------------------------------------------------------------------

create table users (
    id uuid primary key default gen_random_uuid(),
    auth_subject text not null,
    display_name text not null,
    role account_role not null default 'member',
    email_verified boolean not null default false,
    verification_status verification_status not null default 'unverified',
    area_code text,
    birth_year integer,
    status user_status not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint users_auth_subject_key unique (auth_subject),
    constraint users_display_name_length
        check (length(trim(display_name)) between 1 and 80),
    -- now() のように時間で結果が変わる式は CHECK に入れない。
    -- 「現在年以前か」はアプリケーション側で検証する。
    constraint users_birth_year_range
        check (birth_year is null or birth_year between 1900 and 2100)
);

create index users_verification_status_status_idx
    on users (verification_status, status);
create index users_area_code_idx on users (area_code);

-- ---------------------------------------------------------------------------
-- requests
-- ---------------------------------------------------------------------------

create table requests (
    id uuid primary key default gen_random_uuid(),
    requester_id uuid not null references users (id) on delete restrict,
    title text not null,
    original_text text,
    structured_content jsonb not null default '{}'::jsonb,
    category_id text not null,
    risk_level risk_level not null default 'low',
    area_code text not null,
    approximate_latitude numeric(8, 5),
    approximate_longitude numeric(8, 5),
    scheduled_at timestamptz,
    estimated_minutes integer,
    required_helpers integer not null default 1,
    status request_status not null default 'draft',
    version integer not null default 1,
    expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint requests_title_length check (length(trim(title)) between 1 and 100),
    constraint requests_required_helpers_range check (required_helpers between 1 and 20),
    constraint requests_estimated_minutes_range
        check (estimated_minutes is null or estimated_minutes between 1 and 1440),
    constraint requests_version_positive check (version >= 1),
    constraint requests_expires_after_creation
        check (expires_at is null or expires_at > created_at),
    constraint requests_latitude_range
        check (approximate_latitude is null
               or approximate_latitude between -90 and 90),
    constraint requests_longitude_range
        check (approximate_longitude is null
               or approximate_longitude between -180 and 180),
    -- 片方だけ入っている状態を許すと、丸め漏れや部分更新のバグが見えなくなる。
    constraint requests_coordinates_paired
        check ((approximate_latitude is null) = (approximate_longitude is null)),
    constraint requests_structured_content_is_object
        check (jsonb_typeof(structured_content) = 'object')
);

-- category_id は taxonomy 表が §9 に無いため baseline では text にする。
-- 許可カテゴリはアプリケーション側の固定ルールで制限し、taxonomy の正本が
-- 決まった時点で後続 migration により FK 化する。根拠のない FK 先は作らない。

create index requests_status_created_cursor_idx
    on requests (status, created_at desc, id desc);
create index requests_status_scheduled_idx on requests (status, scheduled_at, id);
create index requests_status_expires_idx on requests (status, expires_at);
create index requests_category_status_scheduled_idx
    on requests (category_id, status, scheduled_at);
create index requests_area_status_scheduled_idx
    on requests (area_code, status, scheduled_at);
create index requests_requester_created_idx on requests (requester_id, created_at desc);
create index requests_risk_status_idx on requests (risk_level, status);

-- ---------------------------------------------------------------------------
-- applications
-- ---------------------------------------------------------------------------

create table applications (
    id uuid primary key default gen_random_uuid(),
    request_id uuid not null references requests (id) on delete restrict,
    helper_id uuid not null references users (id) on delete restrict,
    message text,
    available_at timestamptz,
    status application_status not null default 'applied',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    -- 同一依頼への重複応募を DB で禁止する（#6）。
    constraint applications_request_helper_key unique (request_id, helper_id),
    constraint applications_message_length check (message is null or length(message) <= 1000)
);

-- 「依頼者本人は自分の依頼に応募できない」はテーブル単体の CHECK では表現できない
-- （requests 行の参照が必要）。応募 RPC / API 側で検証し、DB integration test で守る。

create index applications_request_status_cursor_idx
    on applications (request_id, status, created_at, id);
create index applications_helper_status_idx
    on applications (helper_id, status, created_at desc);

-- ---------------------------------------------------------------------------
-- matches
-- ---------------------------------------------------------------------------

create table matches (
    id uuid primary key default gen_random_uuid(),
    request_id uuid not null references requests (id) on delete restrict,
    helper_id uuid not null references users (id) on delete restrict,
    application_id uuid not null references applications (id) on delete restrict,
    status match_status not null default 'matched',
    requester_confirmed boolean not null default false,
    helper_confirmed boolean not null default false,
    dispute_reason text,
    matched_at timestamptz not null default now(),
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint matches_application_key unique (application_id),
    constraint matches_request_helper_key unique (request_id, helper_id),
    constraint matches_completed_after_matched
        check (completed_at is null or completed_at >= matched_at),
    constraint matches_completed_requires_timestamp
        check (status <> 'completed' or completed_at is not null)
);

-- 定員超過の防止は単独の UNIQUE では足りない。#7 の RPC 内で requests 行をロックし、
-- accepted / selected 数を数え、required_helpers を超える場合は全変更を rollback する。
-- application の request / helper との一致も同じ RPC 内で検証する。

create index matches_request_status_idx on matches (request_id, status);
create index matches_helper_status_idx on matches (helper_id, status, matched_at desc);
create index matches_status_matched_idx on matches (status, matched_at);

commit;

begin;

-- ---------------------------------------------------------------------------
-- messages
-- ---------------------------------------------------------------------------

create table messages (
    id uuid primary key default gen_random_uuid(),
    match_id uuid not null references matches (id) on delete restrict,
    sender_id uuid not null references users (id) on delete restrict,
    body text not null,
    moderation moderation_status not null default 'clean',
    sent_at timestamptz not null default now(),
    read_at timestamptz,
    constraint messages_body_length check (length(trim(body)) between 1 and 4000),
    constraint messages_read_after_sent check (read_at is null or read_at >= sent_at)
);

create index messages_match_cursor_idx on messages (match_id, sent_at, id);
create index messages_match_unread_idx on messages (match_id, read_at);
create index messages_sender_sent_idx on messages (sender_id, sent_at desc);

-- ---------------------------------------------------------------------------
-- reviews
-- ---------------------------------------------------------------------------

create table reviews (
    id uuid primary key default gen_random_uuid(),
    match_id uuid not null references matches (id) on delete restrict,
    reviewer_id uuid not null references users (id) on delete restrict,
    reviewee_id uuid not null references users (id) on delete restrict,
    evaluation jsonb not null default '{}'::jsonb,
    comment text,
    created_at timestamptz not null default now(),
    -- 同一マッチにつきレビュアー1件（#10）。
    constraint reviews_match_reviewer_key unique (match_id, reviewer_id),
    constraint reviews_reviewer_is_not_reviewee check (reviewer_id <> reviewee_id),
    constraint reviews_evaluation_is_object check (jsonb_typeof(evaluation) = 'object'),
    constraint reviews_comment_length check (comment is null or length(comment) <= 2000)
);

-- 「完了済みマッチだけ」「reviewee が相手当事者であること」は matches 行の参照が要るため
-- テーブル単体の CHECK では表現できない。投稿 RPC / API 側で検証する。

create index reviews_reviewee_created_idx on reviews (reviewee_id, created_at desc);
create index reviews_match_created_idx on reviews (match_id, created_at);

-- ---------------------------------------------------------------------------
-- achievement_profiles
--
-- 事実データの正本は matches / requests / reviews であり、generated_text へ埋め込まない。
-- AI provider を外しても DB 契約が残る形にしておく（#10 / 学生調査の結果に依存しない）。
-- ---------------------------------------------------------------------------

create table achievement_profiles (
    user_id uuid primary key references users (id) on delete restrict,
    generated_text text,
    model_name text,
    prompt_version text,
    generated_at timestamptz,
    approved_at timestamptz,
    visibility achievement_visibility not null default 'private',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint achievement_generated_text_length
        check (generated_text is null or length(generated_text) <= 10000),
    -- 生成文があるなら、どのモデルのどのプロンプトでいつ作ったかを必ず持つ。
    constraint achievement_generation_metadata_complete
        check (generated_text is null
               or (model_name is not null
                   and prompt_version is not null
                   and generated_at is not null)),
    constraint achievement_approved_requires_generation
        check (approved_at is null or generated_at is not null)
);

create index achievement_visibility_approved_idx
    on achievement_profiles (visibility, approved_at);
create index achievement_generated_at_idx on achievement_profiles (generated_at);

-- ---------------------------------------------------------------------------
-- verification_requests
--
-- 画像本体は private bucket に置き、この表は metadata だけを持つ。
-- storage_object_key に public URL を保存しない。
-- ---------------------------------------------------------------------------

create table verification_requests (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users (id) on delete restrict,
    reviewer_id uuid references users (id) on delete set null,
    status verification_status not null default 'pending',
    storage_object_key text,
    note text,
    reviewed_at timestamptz,
    deletion_due_at timestamptz,
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    -- unverified は利用者の状態であって申請の状態ではない。
    constraint verification_status_is_not_unverified check (status <> 'unverified'),
    constraint verification_reviewer_requires_timestamp
        check (reviewer_id is null or reviewed_at is not null),
    constraint verification_decided_requires_timestamp
        check (status not in ('approved', 'rejected') or reviewed_at is not null),
    constraint verification_stored_object_requires_due_date
        check (storage_object_key is null or deletion_due_at is not null),
    constraint verification_deleted_after_due
        check (deleted_at is null or deleted_at >= deletion_due_at)
);

create index verification_user_created_idx on verification_requests (user_id, created_at desc);
-- 同時に複数の未処理申請を作らせない。
create unique index verification_one_pending_per_user_idx
    on verification_requests (user_id) where status = 'pending';
create index verification_queue_idx on verification_requests (status, created_at);
create index verification_pending_deletion_idx
    on verification_requests (deletion_due_at)
    where deleted_at is null and storage_object_key is not null;
create index verification_reviewer_idx on verification_requests (reviewer_id, reviewed_at desc);

-- ---------------------------------------------------------------------------
-- reports
--
-- target は polymorphic なので通常の FK を張れない。存在確認は insert RPC で行う。
-- ---------------------------------------------------------------------------

create table reports (
    id uuid primary key default gen_random_uuid(),
    reporter_id uuid not null references users (id) on delete restrict,
    handled_by uuid references users (id) on delete set null,
    target_type text not null,
    target_id uuid not null,
    reason text not null,
    description text not null,
    severity report_severity not null default 'low',
    status report_status not null default 'open',
    resolved_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint reports_target_type_allowed
        check (target_type in ('user', 'request', 'application', 'match', 'message', 'review')),
    constraint reports_description_length check (length(description) between 1 and 4000),
    constraint reports_closed_requires_handler
        check (status not in ('resolved', 'rejected')
               or (resolved_at is not null and handled_by is not null))
);

create index reports_triage_idx on reports (status, severity desc, created_at);
create index reports_target_idx on reports (target_type, target_id, status);
create index reports_reporter_idx on reports (reporter_id, created_at desc);
create index reports_handler_idx on reports (handled_by, status);

-- ---------------------------------------------------------------------------
-- audit_logs
--
-- append-only。UPDATE と DELETE は全アクターに対して拒否する（RLS で後述）。
-- ip_hash は生 IP ではなく salted hash。salt は DB にも文書にも保存しない。
-- ---------------------------------------------------------------------------

create table audit_logs (
    id uuid primary key default gen_random_uuid(),
    actor_id uuid references users (id) on delete set null,
    event_type text not null,
    target_type text not null,
    target_id uuid,
    result text not null,
    detail jsonb not null default '{}'::jsonb,
    ip_hash text,
    user_agent text,
    created_at timestamptz not null default now(),
    constraint audit_event_type_not_blank check (length(trim(event_type)) > 0),
    constraint audit_target_type_not_blank check (length(trim(target_type)) > 0),
    constraint audit_result_not_blank check (length(trim(result)) > 0),
    constraint audit_detail_is_object check (jsonb_typeof(detail) = 'object'),
    constraint audit_user_agent_length check (user_agent is null or length(user_agent) <= 512)
);

create index audit_created_idx on audit_logs (created_at desc, id desc);
create index audit_actor_idx on audit_logs (actor_id, created_at desc);
create index audit_target_idx on audit_logs (target_type, target_id, created_at desc);
create index audit_event_idx on audit_logs (event_type, created_at desc);

-- ---------------------------------------------------------------------------
-- user_blocks
--
-- 要件定義書 §9 に無いが #11 / #14 に必須。誰が誰をブロックしたかを利用者単位で持つ。
-- 双方向判定は exists(blocker=a, blocked=b) or exists(blocker=b, blocked=a)。
-- ---------------------------------------------------------------------------

create table user_blocks (
    blocker_id uuid not null references users (id) on delete restrict,
    blocked_id uuid not null references users (id) on delete restrict,
    created_at timestamptz not null default now(),
    constraint user_blocks_pkey primary key (blocker_id, blocked_id),
    constraint user_blocks_no_self check (blocker_id <> blocked_id)
);

create index user_blocks_reverse_idx on user_blocks (blocked_id, blocker_id);

commit;
