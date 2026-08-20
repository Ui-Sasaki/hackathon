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
