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

begin;

-- ---------------------------------------------------------------------------
-- ランタイムロール
--
-- 認証は SuperTokens であり Supabase Auth ではないため auth.uid() は使えない。
-- FastAPI は認証済みリクエストごとに transaction-local な actor UUID を設定し、
-- RLS はそこから users 行を引いて権限を判定する。
--
-- table owner / migration role をランタイムに使わない。superuser は RLS を
-- 常に迂回するので、アプリケーションからは必ず下記の NOBYPASSRLS ロールで接続する。
-- ---------------------------------------------------------------------------

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'tetote_app') then
        create role tetote_app login nosuperuser nobypassrls;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'tetote_anon') then
        create role tetote_anon login nosuperuser nobypassrls;
    end if;
end;
$$;

grant usage on schema public to tetote_app, tetote_anon;

-- 未認証ロールには業務テーブルへの権限を一切与えない。
-- RLS 以前に権限で落とす（多層防御の1層目）。
grant select, insert on
    users, requests, applications, matches, messages, reviews,
    achievement_profiles, verification_requests, reports, audit_logs, user_blocks
to tetote_app;

-- 状態遷移・選択・完了・管理処置は専用関数へ寄せるため、UPDATE / DELETE は付与しない。

-- ---------------------------------------------------------------------------
-- ヘルパー
--
-- SECURITY DEFINER は search_path を固定し、実行権限を明示的に絞る。
-- RLS を迂回する汎用 CRUD 関数は作らない。
-- ---------------------------------------------------------------------------

create schema if not exists app;
grant usage on schema app to tetote_app, tetote_anon;

create or replace function app.current_actor()
returns uuid language sql stable as $$
    select nullif(current_setting('app.actor_id', true), '')::uuid;
$$;

create or replace function app.actor_role()
returns account_role language sql stable security definer
set search_path = public, pg_temp as $$
    select u.role from users u
     where u.id = app.current_actor() and u.status = 'active';
$$;

create or replace function app.is_active_actor()
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
    select exists (select 1 from users u
                    where u.id = app.current_actor() and u.status = 'active');
$$;

create or replace function app.is_admin()
returns boolean language sql stable as $$
    select app.actor_role() = 'admin';
$$;

create or replace function app.is_verifier()
returns boolean language sql stable as $$
    select app.actor_role() = 'verifier';
$$;

-- ブロックは「どちら向きでも関係あり」で判定する。
create or replace function app.is_blocked_pair(a uuid, b uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
    select exists (
        select 1 from user_blocks ub
         where (ub.blocker_id = a and ub.blocked_id = b)
            or (ub.blocker_id = b and ub.blocked_id = a)
    );
$$;

create or replace function app.is_match_party(p_match_id uuid, p_actor uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
    select exists (
        select 1 from matches m
          join requests r on r.id = m.request_id
         where m.id = p_match_id
           and (m.helper_id = p_actor or r.requester_id = p_actor)
    );
$$;

-- ポリシー同士の相互参照による無限再帰を避けるため、テーブルをまたぐ判定は
-- すべて SECURITY DEFINER のヘルパー経由にする。ポリシーの中で他テーブルを
-- 直接 select すると、そのテーブルのポリシーが再帰的に評価される。
create or replace function app.request_owner(p_request_id uuid)
returns uuid language sql stable security definer
set search_path = public, pg_temp as $$
    select r.requester_id from requests r where r.id = p_request_id;
$$;

create or replace function app.request_is_open(p_request_id uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
    select exists (
        select 1 from requests r
         where r.id = p_request_id
           and r.status = 'published'
           and (r.expires_at is null or r.expires_at > now())
    );
$$;

create or replace function app.actor_has_match_on_request(p_request_id uuid, p_actor uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
    select exists (
        select 1 from matches m
         where m.request_id = p_request_id and m.helper_id = p_actor
    );
$$;

create or replace function app.profile_is_public(p_user_id uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
    select exists (
        select 1 from achievement_profiles ap
         where ap.user_id = p_user_id
           and ap.approved_at is not null
           and ap.visibility = 'public'
    );
$$;

create or replace function app.request_is_public(p_status request_status, p_expires timestamptz)
returns boolean language sql immutable as $$
    select p_status = 'published' and (p_expires is null or p_expires > now());
$$;

revoke all on function app.actor_role(), app.is_active_actor(), app.is_blocked_pair(uuid, uuid),
    app.is_match_party(uuid, uuid), app.request_owner(uuid), app.request_is_open(uuid),
    app.actor_has_match_on_request(uuid, uuid), app.profile_is_public(uuid) from public;
grant execute on function app.current_actor(), app.actor_role(), app.is_active_actor(),
    app.is_admin(), app.is_verifier(), app.is_blocked_pair(uuid, uuid),
    app.is_match_party(uuid, uuid), app.request_is_public(request_status, timestamptz),
    app.request_owner(uuid), app.request_is_open(uuid),
    app.actor_has_match_on_request(uuid, uuid), app.profile_is_public(uuid)
to tetote_app;

-- ---------------------------------------------------------------------------
-- RLS 有効化
--
-- FORCE を付けることでテーブル所有者にもポリシーを適用する。
-- ---------------------------------------------------------------------------

alter table users                 enable row level security;
alter table requests              enable row level security;
alter table applications          enable row level security;
alter table matches               enable row level security;
alter table messages              enable row level security;
alter table reviews               enable row level security;
alter table achievement_profiles  enable row level security;
alter table verification_requests enable row level security;
alter table reports               enable row level security;
alter table audit_logs            enable row level security;
alter table user_blocks           enable row level security;

alter table users                 force row level security;
alter table requests              force row level security;
alter table applications          force row level security;
alter table matches               force row level security;
alter table messages              force row level security;
alter table reviews               force row level security;
alter table achievement_profiles  force row level security;
alter table verification_requests force row level security;
alter table reports               force row level security;
alter table audit_logs            force row level security;
alter table user_blocks           force row level security;

-- 未認証ロールにはポリシーを一切作らない。権限も無いので二重に落ちる。
--
-- すべてのポリシーは app.is_active_actor() を先頭条件に置く。actor が未設定なら
-- app.current_actor() は NULL になり、NULL 比較は真にならないが、
-- 「公開中の依頼なら誰でも読める」のような actor に依存しない条件は
-- それだけでは閉じない。要件定義書 §5 の権限表に未認証の列は無いので、
-- 業務テーブルは actor が確定していない限り一律 deny にする。

-- users -----------------------------------------------------------------
create policy users_select_self on users for select to tetote_app
    using (
        app.is_active_actor()
        and (id = app.current_actor() or app.is_admin())
    );

-- requests --------------------------------------------------------------
create policy requests_select on requests for select to tetote_app
    using (
        app.is_active_actor()
        and (
            app.is_admin()
            or requester_id = app.current_actor()
            or (
                app.request_is_public(status, expires_at)
                and not app.is_blocked_pair(requester_id, app.current_actor())
            )
            or app.actor_has_match_on_request(id, app.current_actor())
        )
    );

create policy requests_insert on requests for insert to tetote_app
    with check (app.is_active_actor() and requester_id = app.current_actor());

-- applications ----------------------------------------------------------
create policy applications_select on applications for select to tetote_app
    using (
        app.is_active_actor()
        and (
            app.is_admin()
            or helper_id = app.current_actor()
            or (
                app.request_owner(request_id) = app.current_actor()
                and not app.is_blocked_pair(helper_id, app.current_actor())
            )
        )
    );

create policy applications_insert on applications for insert to tetote_app
    with check (
        app.is_active_actor()
        and helper_id = app.current_actor()
        and app.request_owner(request_id) <> app.current_actor()
        and app.request_is_open(request_id)
        and not app.is_blocked_pair(app.request_owner(request_id), app.current_actor())
    );

-- matches ---------------------------------------------------------------
-- ブロック後も当事者は自分のマッチを閲覧できる。完了・dispute・通報の証拠を失わないため。
create policy matches_select on matches for select to tetote_app
    using (
        app.is_active_actor()
        and (
            app.is_admin()
            or helper_id = app.current_actor()
            or app.request_owner(request_id) = app.current_actor()
        )
    );

-- messages --------------------------------------------------------------
create policy messages_select on messages for select to tetote_app
    using (
        app.is_active_actor()
        and (app.is_admin() or app.is_match_party(match_id, app.current_actor()))
    );

create policy messages_insert on messages for insert to tetote_app
    with check (
        app.is_active_actor()
        and sender_id = app.current_actor()
        and app.is_match_party(match_id, app.current_actor())
    );

-- reviews ---------------------------------------------------------------
create policy reviews_select on reviews for select to tetote_app
    using (
        app.is_active_actor()
        and (
            app.is_admin()
            or reviewer_id = app.current_actor()
            or reviewee_id = app.current_actor()
            or app.profile_is_public(reviewee_id)
        )
    );

create policy reviews_insert on reviews for insert to tetote_app
    with check (
        app.is_active_actor()
        and reviewer_id = app.current_actor()
        and app.is_match_party(match_id, app.current_actor())
    );

-- achievement_profiles --------------------------------------------------
-- 本人の承認前は visibility にかかわらず外部から読めない。
create policy achievements_select on achievement_profiles for select to tetote_app
    using (
        app.is_active_actor()
        and (
            app.is_admin()
            or user_id = app.current_actor()
            or (
                approved_at is not null
                and visibility = 'public'
                and not app.is_blocked_pair(user_id, app.current_actor())
            )
        )
    );

-- verification_requests -------------------------------------------------
create policy verifications_select on verification_requests for select to tetote_app
    using (
        app.is_active_actor()
        and (app.is_admin() or app.is_verifier() or user_id = app.current_actor())
    );

create policy verifications_insert on verification_requests for insert to tetote_app
    with check (app.is_active_actor() and user_id = app.current_actor());

-- reports ---------------------------------------------------------------
create policy reports_select on reports for select to tetote_app
    using (
        app.is_active_actor()
        and (app.is_admin() or reporter_id = app.current_actor())
    );

create policy reports_insert on reports for insert to tetote_app
    with check (app.is_active_actor() and reporter_id = app.current_actor());

-- audit_logs ------------------------------------------------------------
-- append-only。UPDATE / DELETE のポリシーも権限も与えない。
create policy audit_select on audit_logs for select to tetote_app
    using (
        app.is_active_actor()
        and (app.is_admin()
             or (app.is_verifier() and target_type = 'verification_request'))
    );

create policy audit_insert on audit_logs for insert to tetote_app
    with check (
        app.is_active_actor()
        and (actor_id is null or actor_id = app.current_actor())
    );

-- user_blocks -----------------------------------------------------------
-- 誰にブロックされているかは相手に見せない。自分がブロックした関係だけを読める。
create policy blocks_select on user_blocks for select to tetote_app
    using (
        app.is_active_actor()
        and (app.is_admin() or blocker_id = app.current_actor())
    );

create policy blocks_insert on user_blocks for insert to tetote_app
    with check (app.is_active_actor() and blocker_id = app.current_actor());

commit;
