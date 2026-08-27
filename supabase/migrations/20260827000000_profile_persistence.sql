-- #67: SuperTokens subject resolution and private editable profile persistence.
-- Existing migrations remain immutable; all profile changes are forward-only.

begin;

create type helper_type as enum ('student', 'worker');

create table operational_areas (
    code text primary key,
    label text not null,
    prefecture_code text not null,
    active boolean not null default true,
    sort_order integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint operational_areas_code_length
        check (length(trim(code)) between 1 and 30),
    constraint operational_areas_label_length
        check (length(trim(label)) between 1 and 80),
    constraint operational_areas_prefecture_code
        check (
            prefecture_code ~ '^[0-9]{2}$'
            and prefecture_code::integer between 1 and 47
        )
);

insert into operational_areas (code, label, prefecture_code, sort_order) values
    ('AREA-001', '大学周辺', '01', 10),
    ('AREA-002', '大学北側', '01', 20),
    ('AREA-003', '駅周辺', '01', 30);

alter table users
    add column prefecture_code text,
    add column notes text,
    add column helper_type helper_type,
    add column university text,
    add column faculty text,
    add column school_year integer,
    add column occupation text,
    add column industry text,
    add column workplace text,
    add column interest text,
    add column message text,
    add constraint users_area_code_fkey
        foreign key (area_code) references operational_areas(code) on delete restrict,
    add constraint users_prefecture_code
        check (
            prefecture_code is null
            or (
                prefecture_code ~ '^[0-9]{2}$'
                and prefecture_code::integer between 1 and 47
            )
        ),
    add constraint users_notes_length
        check (notes is null or length(notes) <= 1000),
    add constraint users_university_length
        check (university is null or length(trim(university)) between 1 and 100),
    add constraint users_faculty_length
        check (faculty is null or length(trim(faculty)) between 1 and 100),
    add constraint users_school_year_range
        check (school_year is null or school_year between 1 and 8),
    add constraint users_occupation_length
        check (occupation is null or length(trim(occupation)) between 1 and 100),
    add constraint users_industry_length
        check (industry is null or length(industry) <= 100),
    add constraint users_workplace_length
        check (workplace is null or length(workplace) <= 100),
    add constraint users_interest_length
        check (interest is null or length(interest) <= 500),
    add constraint users_message_length
        check (message is null or length(message) <= 1000),
    add constraint users_helper_details
        check (
            (helper_type is null
                and university is null and faculty is null and school_year is null
                and occupation is null and industry is null and workplace is null)
            or
            (helper_type = 'student'
                and university is not null and faculty is not null and school_year is not null
                and occupation is null and industry is null and workplace is null)
            or
            (helper_type = 'worker'
                and occupation is not null
                and university is null and faculty is null and school_year is null)
        );

-- Existing identities must never have editable profile values overwritten just
-- because a new authenticated request established actor context.
create or replace function app.ensure_user(
    p_auth_subject text,
    p_display_name text,
    p_role account_role default 'member'
)
returns uuid language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_id uuid;
begin
    insert into users (auth_subject, display_name, role)
    values (p_auth_subject, p_display_name, p_role)
    on conflict (auth_subject) do nothing
    returning id into v_id;

    if v_id is null then
        select u.id into v_id from users u where u.auth_subject = p_auth_subject;
    end if;
    return v_id;
end;
$$;

-- Called only after SuperTokens has verified the subject. It lazily provisions
-- a safe member row and returns the authorization/profile source of truth.
create or replace function app.resolve_authenticated_user(p_auth_subject text)
returns table (
    auth_subject text,
    display_name text,
    role account_role,
    email_verified boolean,
    verification_status verification_status,
    area_code text,
    prefecture_code text,
    birth_year integer,
    notes text,
    helper_type helper_type,
    university text,
    faculty text,
    school_year integer,
    occupation text,
    industry text,
    workplace text,
    interest text,
    message text,
    status user_status,
    updated_at timestamptz
) language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_display_name text;
begin
    if p_auth_subject is null or length(trim(p_auth_subject)) = 0 then
        raise exception 'authenticated subject is required' using errcode = '22023';
    end if;
    v_display_name := left(trim(p_auth_subject), 80);
    perform app.ensure_user(p_auth_subject, v_display_name, 'member');

    return query
    select u.auth_subject, u.display_name, u.role, u.email_verified,
           u.verification_status, u.area_code, u.prefecture_code, u.birth_year,
           u.notes, u.helper_type, u.university, u.faculty, u.school_year,
           u.occupation, u.industry, u.workplace, u.interest, u.message,
           u.status, u.updated_at
      from users u
     where u.auth_subject = p_auth_subject;
end;
$$;

create or replace function app.update_own_profile(p_patch jsonb)
returns table (
    auth_subject text,
    display_name text,
    role account_role,
    email_verified boolean,
    verification_status verification_status,
    area_code text,
    prefecture_code text,
    birth_year integer,
    notes text,
    helper_type helper_type,
    university text,
    faculty text,
    school_year integer,
    occupation text,
    industry text,
    workplace text,
    interest text,
    message text,
    status user_status,
    updated_at timestamptz
) language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_unknown_key text;
begin
    if not app.is_active_actor() then
        raise exception 'active actor required' using errcode = '42501';
    end if;
    if p_patch is null or jsonb_typeof(p_patch) <> 'object' then
        raise exception 'profile patch must be an object' using errcode = '22023';
    end if;

    select key into v_unknown_key
      from jsonb_object_keys(p_patch) as key
     where key <> all (array[
        'displayName', 'areaCode', 'prefectureCode', 'birthYear', 'notes',
        'helperType', 'university', 'faculty', 'schoolYear', 'occupation',
        'industry', 'workplace', 'interest', 'message'
     ])
     limit 1;
    if v_unknown_key is not null then
        raise exception 'profile field is not editable: %', v_unknown_key
            using errcode = '22023';
    end if;
    if p_patch ? 'displayName'
       and (p_patch->'displayName' = 'null'::jsonb
            or length(trim(p_patch->>'displayName')) = 0) then
        raise exception 'displayName cannot be null or blank' using errcode = '23514';
    end if;
    if p_patch ? 'birthYear'
       and p_patch->'birthYear' <> 'null'::jsonb
       and (p_patch->>'birthYear')::integer > extract(year from current_date)::integer then
        raise exception 'birthYear cannot be in the future' using errcode = '23514';
    end if;

    update users u set
        display_name = case when p_patch ? 'displayName'
            then trim(p_patch->>'displayName') else u.display_name end,
        area_code = case when p_patch ? 'areaCode'
            then nullif(trim(p_patch->>'areaCode'), '') else u.area_code end,
        prefecture_code = case when p_patch ? 'prefectureCode'
            then nullif(trim(p_patch->>'prefectureCode'), '') else u.prefecture_code end,
        birth_year = case when p_patch ? 'birthYear'
            then (p_patch->>'birthYear')::integer else u.birth_year end,
        notes = case when p_patch ? 'notes' then p_patch->>'notes' else u.notes end,
        helper_type = case when p_patch ? 'helperType'
            then (p_patch->>'helperType')::helper_type else u.helper_type end,
        university = case
            when p_patch ? 'helperType' and p_patch->>'helperType' is distinct from 'student' then null
            when p_patch ? 'university' then nullif(trim(p_patch->>'university'), '')
            else u.university end,
        faculty = case
            when p_patch ? 'helperType' and p_patch->>'helperType' is distinct from 'student' then null
            when p_patch ? 'faculty' then nullif(trim(p_patch->>'faculty'), '')
            else u.faculty end,
        school_year = case
            when p_patch ? 'helperType' and p_patch->>'helperType' is distinct from 'student' then null
            when p_patch ? 'schoolYear' then (p_patch->>'schoolYear')::integer
            else u.school_year end,
        occupation = case
            when p_patch ? 'helperType' and p_patch->>'helperType' is distinct from 'worker' then null
            when p_patch ? 'occupation' then nullif(trim(p_patch->>'occupation'), '')
            else u.occupation end,
        industry = case
            when p_patch ? 'helperType' and p_patch->>'helperType' is distinct from 'worker' then null
            when p_patch ? 'industry' then p_patch->>'industry'
            else u.industry end,
        workplace = case
            when p_patch ? 'helperType' and p_patch->>'helperType' is distinct from 'worker' then null
            when p_patch ? 'workplace' then p_patch->>'workplace'
            else u.workplace end,
        interest = case when p_patch ? 'interest'
            then p_patch->>'interest' else u.interest end,
        message = case when p_patch ? 'message'
            then p_patch->>'message' else u.message end,
        updated_at = now()
    where u.id = app.current_actor();

    return query
    select u.auth_subject, u.display_name, u.role, u.email_verified,
           u.verification_status, u.area_code, u.prefecture_code, u.birth_year,
           u.notes, u.helper_type, u.university, u.faculty, u.school_year,
           u.occupation, u.industry, u.workplace, u.interest, u.message,
           u.status, u.updated_at
      from users u
     where u.id = app.current_actor();
end;
$$;

create or replace function app.list_active_operational_areas()
returns table (code text, label text, prefecture_code text, sort_order integer)
language sql stable security definer
set search_path = public, pg_temp as $$
    select a.code, a.label, a.prefecture_code, a.sort_order
      from operational_areas a
     where a.active
     order by a.sort_order, a.code;
$$;

revoke all on table operational_areas from public, tetote_app, tetote_anon;
revoke all on function app.resolve_authenticated_user(text) from public;
revoke all on function app.update_own_profile(jsonb) from public;
revoke all on function app.list_active_operational_areas() from public;
grant execute on function app.resolve_authenticated_user(text) to tetote_app;
grant execute on function app.update_own_profile(jsonb) to tetote_app;
grant execute on function app.list_active_operational_areas() to tetote_app;

commit;
