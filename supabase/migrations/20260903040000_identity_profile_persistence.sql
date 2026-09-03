-- SuperTokens subject resolution and authenticated profile persistence.
-- Existing migrations remain immutable; this correction is forward-only.

begin;

create table operational_areas (
    code text primary key,
    label text not null,
    active boolean not null default true,
    sort_order integer not null default 0,
    constraint operational_areas_code_length check (length(trim(code)) between 1 and 30),
    constraint operational_areas_label_length check (length(trim(label)) between 1 and 80)
);

insert into operational_areas (code, label, sort_order) values
    ('AREA-001', '大学周辺', 10),
    ('AREA-002', '大学北側', 20),
    ('AREA-003', '駅周辺', 30);

alter table users
    add column region text,
    add column age text,
    add column notes text,
    add column helper_type text,
    add column university text,
    add column faculty text,
    add column school_year text,
    add column occupation text,
    add column industry text,
    add column workplace text,
    add column gender text,
    add column interest text,
    add column message text,
    add constraint users_area_code_fkey foreign key (area_code)
        references operational_areas(code) on delete restrict,
    add constraint users_region_length check (region is null or length(trim(region)) between 1 and 20),
    add constraint users_age_length check (age is null or length(trim(age)) between 1 and 30),
    add constraint users_notes_length check (notes is null or length(notes) <= 500),
    add constraint users_helper_type check (helper_type is null or helper_type in ('student', 'worker')),
    add constraint users_university_length check (university is null or length(trim(university)) between 1 and 100),
    add constraint users_faculty_length check (faculty is null or length(trim(faculty)) between 1 and 100),
    add constraint users_school_year_length check (school_year is null or length(trim(school_year)) between 1 and 30),
    add constraint users_occupation_length check (occupation is null or length(trim(occupation)) between 1 and 100),
    add constraint users_industry_length check (industry is null or length(industry) <= 100),
    add constraint users_workplace_length check (workplace is null or length(workplace) <= 100),
    add constraint users_gender_length check (gender is null or length(gender) <= 30),
    add constraint users_interest_length check (interest is null or length(interest) <= 200),
    add constraint users_message_length check (message is null or length(message) <= 500),
    add constraint users_helper_details check (
        (helper_type is null and university is null and faculty is null and school_year is null
            and occupation is null and industry is null and workplace is null)
        or (helper_type = 'student' and university is not null and faculty is not null
            and school_year is not null and occupation is null and industry is null and workplace is null)
        or (helper_type = 'worker' and occupation is not null
            and university is null and faculty is null and school_year is null)
    );

-- Establishing actor context must never overwrite user-owned or privileged data.
create or replace function app.ensure_user(
    p_auth_subject text, p_display_name text, p_role account_role default 'member'
) returns uuid language plpgsql security definer
set search_path = public, pg_temp as $$
declare v_id uuid;
begin
    insert into users (auth_subject, display_name, role)
    values (p_auth_subject, p_display_name, p_role)
    on conflict (auth_subject) do nothing
    returning id into v_id;
    if v_id is null then
        select id into v_id from users where auth_subject = p_auth_subject;
    end if;
    return v_id;
end;
$$;

create or replace function app.own_profile()
returns table (
    auth_subject text, display_name text, role account_role, email_verified boolean,
    verification_status verification_status, area_code text, region text, age text,
    notes text, helper_type text, university text, faculty text, school_year text,
    occupation text, industry text, workplace text, gender text, interest text,
    message text, status user_status, updated_at timestamptz
) language sql stable security definer set search_path = public, pg_temp as $$
    select u.auth_subject, u.display_name, u.role, u.email_verified,
           u.verification_status, u.area_code, u.region, u.age, u.notes,
           u.helper_type, u.university, u.faculty, u.school_year, u.occupation,
           u.industry, u.workplace, u.gender, u.interest, u.message, u.status, u.updated_at
      from users u where u.id = app.current_actor() and app.is_active_actor();
$$;

create or replace function app.resolve_authenticated_user(p_auth_subject text)
returns table (
    auth_subject text, display_name text, role account_role, email_verified boolean,
    verification_status verification_status, area_code text, region text, age text,
    notes text, helper_type text, university text, faculty text, school_year text,
    occupation text, industry text, workplace text, gender text, interest text,
    message text, status user_status, updated_at timestamptz
) language plpgsql security definer set search_path = public, pg_temp as $$
begin
    if p_auth_subject is null or length(trim(p_auth_subject)) = 0 then
        raise exception 'authenticated subject is required' using errcode = '22023';
    end if;
    perform app.ensure_user(p_auth_subject, left(trim(p_auth_subject), 50), 'member');
    return query
    select u.auth_subject, u.display_name, u.role, u.email_verified,
           u.verification_status, u.area_code, u.region, u.age, u.notes,
           u.helper_type, u.university, u.faculty, u.school_year, u.occupation,
           u.industry, u.workplace, u.gender, u.interest, u.message, u.status, u.updated_at
      from users u where u.auth_subject = p_auth_subject;
end;
$$;

-- Business transactions may resolve only an already provisioned subject.
-- Provisioning with a caller-selected role remains an internal migration helper.
create or replace function app.authenticated_user_id(p_auth_subject text)
returns uuid language sql stable security definer set search_path = public, pg_temp as $$
    select u.id from users u where u.auth_subject = p_auth_subject;
$$;

-- Applicant lists expose only the explicitly public profile projection.  In
-- particular, an unapproved achievement must not be observable even as a count.
create or replace function app.application_helper_profile(p_helper_id uuid)
returns jsonb language sql stable security definer
set search_path = public, pg_temp as $$
    select jsonb_build_object(
        'display_name', u.display_name,
        'verification_status', u.verification_status,
        'email_verified', u.email_verified,
        'achievement_count', (
            select count(*) from achievement_profiles ap
             where ap.user_id = u.id
               and ap.approved_at is not null
               and ap.visibility = 'public'
        )
    )
    from users u where u.id = p_helper_id;
$$;

create or replace function app.update_own_profile(p_patch jsonb)
returns setof users language plpgsql security definer set search_path = public, pg_temp as $$
declare v_unknown text;
begin
    if not app.is_active_actor() then raise exception 'active actor required' using errcode = '42501'; end if;
    if p_patch is null or jsonb_typeof(p_patch) <> 'object' then
        raise exception 'profile patch must be an object' using errcode = '22023';
    end if;
    select key into v_unknown from jsonb_object_keys(p_patch) key
     where key <> all(array['displayName','areaCode','region','age','notes','helperType',
       'university','faculty','schoolYear','occupation','industry','workplace','gender','interest','message']) limit 1;
    if v_unknown is not null then raise exception 'profile field is not editable' using errcode = '22023'; end if;
    if p_patch ? 'displayName' and (p_patch->'displayName' = 'null'::jsonb or length(trim(p_patch->>'displayName')) = 0) then
        raise exception 'displayName cannot be blank' using errcode = '23514';
    end if;
    update users u set
      display_name=case when p_patch?'displayName' then trim(p_patch->>'displayName') else u.display_name end,
      area_code=case when p_patch?'areaCode' then nullif(trim(p_patch->>'areaCode'),'') else u.area_code end,
      region=case when p_patch?'region' then p_patch->>'region' else u.region end,
      age=case when p_patch?'age' then p_patch->>'age' else u.age end,
      notes=case when p_patch?'notes' then p_patch->>'notes' else u.notes end,
      helper_type=case when p_patch?'helperType' then p_patch->>'helperType' else u.helper_type end,
      university=case when p_patch?'university' then p_patch->>'university' else u.university end,
      faculty=case when p_patch?'faculty' then p_patch->>'faculty' else u.faculty end,
      school_year=case when p_patch?'schoolYear' then p_patch->>'schoolYear' else u.school_year end,
      occupation=case when p_patch?'occupation' then p_patch->>'occupation' else u.occupation end,
      industry=case when p_patch?'industry' then p_patch->>'industry' else u.industry end,
      workplace=case when p_patch?'workplace' then p_patch->>'workplace' else u.workplace end,
      gender=case when p_patch?'gender' then p_patch->>'gender' else u.gender end,
      interest=case when p_patch?'interest' then p_patch->>'interest' else u.interest end,
      message=case when p_patch?'message' then p_patch->>'message' else u.message end,
      updated_at=now()
    where u.id=app.current_actor();
    return query select u.* from users u where u.id=app.current_actor();
end;
$$;

revoke all on table operational_areas from public, tetote_app, tetote_anon;
revoke all on function app.ensure_user(text, text, account_role) from public, tetote_app, tetote_anon;
revoke all on function app.own_profile(), app.resolve_authenticated_user(text), app.authenticated_user_id(text), app.update_own_profile(jsonb), app.application_helper_profile(uuid) from public;
grant execute on function app.own_profile(), app.resolve_authenticated_user(text), app.authenticated_user_id(text), app.update_own_profile(jsonb), app.application_helper_profile(uuid) to tetote_app;

commit;
