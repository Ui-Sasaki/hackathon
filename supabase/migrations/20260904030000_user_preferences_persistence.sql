-- Persist user settings, saved requests, dismissed request cards, and request
-- structuring audit metadata. Existing migrations remain immutable.

begin;

create table user_settings (
    user_id uuid primary key references users (id) on delete cascade,
    notifications_enabled boolean not null default true,
    location_enabled boolean not null default true,
    font_size text not null default 'medium',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint user_settings_font_size_allowed
        check (font_size in ('small', 'medium', 'large'))
);

create table saved_requests (
    user_id uuid not null references users (id) on delete cascade,
    request_id uuid not null references requests (id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (user_id, request_id)
);

create table request_dismissals (
    user_id uuid not null references users (id) on delete cascade,
    request_id uuid not null references requests (id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (user_id, request_id)
);

create table request_structure_audits (
    id text primary key,
    model_name text not null,
    prompt_version text not null,
    schema_version text not null,
    processed_at timestamptz not null,
    created_at timestamptz not null default now(),
    constraint request_structure_audits_id_length
        check (length(trim(id)) between 1 and 80),
    constraint request_structure_audits_model_name_length
        check (length(trim(model_name)) between 1 and 120),
    constraint request_structure_audits_prompt_version_length
        check (length(trim(prompt_version)) between 1 and 80),
    constraint request_structure_audits_schema_version_length
        check (length(trim(schema_version)) between 1 and 80)
);

create index saved_requests_user_created_idx
    on saved_requests (user_id, created_at desc, request_id);
create index request_dismissals_user_created_idx
    on request_dismissals (user_id, created_at desc, request_id);
create index request_structure_audits_processed_idx
    on request_structure_audits (processed_at desc, id);

grant select, insert, update, delete on
    user_settings, saved_requests, request_dismissals
to tetote_app;

grant select, insert, delete on request_structure_audits to tetote_app;

alter table user_settings             enable row level security;
alter table saved_requests            enable row level security;
alter table request_dismissals        enable row level security;
alter table request_structure_audits  enable row level security;

alter table user_settings             force row level security;
alter table saved_requests            force row level security;
alter table request_dismissals        force row level security;
alter table request_structure_audits  force row level security;

create policy user_settings_select on user_settings for select to tetote_app
    using (app.is_active_actor() and user_id = app.current_actor());
create policy user_settings_insert on user_settings for insert to tetote_app
    with check (app.is_active_actor() and user_id = app.current_actor());
create policy user_settings_update on user_settings for update to tetote_app
    using (app.is_active_actor() and user_id = app.current_actor())
    with check (app.is_active_actor() and user_id = app.current_actor());
create policy user_settings_delete on user_settings for delete to tetote_app
    using (app.is_active_actor() and user_id = app.current_actor());

create policy saved_requests_select on saved_requests for select to tetote_app
    using (app.is_active_actor() and user_id = app.current_actor());
create policy saved_requests_insert on saved_requests for insert to tetote_app
    with check (app.is_active_actor() and user_id = app.current_actor());
create policy saved_requests_delete on saved_requests for delete to tetote_app
    using (app.is_active_actor() and user_id = app.current_actor());

create policy request_dismissals_select on request_dismissals for select to tetote_app
    using (app.is_active_actor() and user_id = app.current_actor());
create policy request_dismissals_insert on request_dismissals for insert to tetote_app
    with check (app.is_active_actor() and user_id = app.current_actor());
create policy request_dismissals_delete on request_dismissals for delete to tetote_app
    using (app.is_active_actor() and user_id = app.current_actor());

create policy request_structure_audits_select on request_structure_audits
    for select to tetote_app using (app.is_admin());

create or replace function app.save_request_structure_audit(p_audit jsonb)
returns void language plpgsql security definer
set search_path = public, pg_temp as $$
begin
    if p_audit is null or jsonb_typeof(p_audit) <> 'object' then
        raise exception 'structure audit must be an object' using errcode = '22023';
    end if;
    insert into request_structure_audits (
        id, model_name, prompt_version, schema_version, processed_at
    ) values (
        p_audit->>'id',
        p_audit->>'modelName',
        p_audit->>'promptVersion',
        p_audit->>'schemaVersion',
        (p_audit->>'processedAt')::timestamptz
    );
end;
$$;

revoke all on function app.save_request_structure_audit(jsonb) from public;
grant execute on function app.save_request_structure_audit(jsonb) to tetote_app;

commit;
