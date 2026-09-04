begin;
create table university_email_challenges (
 id uuid primary key, user_id uuid not null references users(id) on delete cascade,
 email text not null check(email=lower(email) and email like '%@%.ac.jp'),
 code_digest text not null check(length(code_digest)=64), attempts smallint not null default 0,
 expires_at timestamptz not null, verified_at timestamptz, created_at timestamptz not null default now()
);
create index university_email_challenge_user_created on university_email_challenges(user_id,created_at desc);
alter table university_email_challenges enable row level security;
alter table university_email_challenges force row level security;
create policy university_email_challenge_owner on university_email_challenges for select to tetote_app
 using(user_id=app.current_actor() and app.is_active_actor());
grant select on university_email_challenges to tetote_app;

create function app.create_university_email_challenge(p_id uuid,p_email text,p_digest text)
returns void language plpgsql security definer set search_path=public,pg_temp as $$
begin
 if not app.is_active_actor() then raise exception 'ROLE_FORBIDDEN'; end if;
 if p_email<>lower(p_email) or p_email!~'^[^@[:space:]]+@([a-z0-9-]+\.)+ac\.jp$' then
  raise exception 'UNIVERSITY_EMAIL_REQUIRED'; end if;
 if exists(select 1 from university_email_challenges where user_id=app.current_actor()
           and created_at>now()-interval '60 seconds') then raise exception 'RATE_LIMITED'; end if;
 delete from university_email_challenges where expires_at<now()-interval '1 day';
 insert into university_email_challenges(id,user_id,email,code_digest,expires_at)
 values(p_id,app.current_actor(),p_email,p_digest,now()+interval '10 minutes');
 insert into audit_logs(actor_id,event_type,target_type,target_id,result)
 values(app.current_actor(),'university_email_code_sent','verification_request',p_id,'success');
end $$;

create function app.verify_university_email_code(p_id uuid,p_digest text)
returns text language plpgsql security definer set search_path=public,pg_temp as $$
declare c university_email_challenges%rowtype;
begin
 select * into c from university_email_challenges where id=p_id and user_id=app.current_actor() for update;
 if not found then return 'CHALLENGE_NOT_FOUND'; end if;
 if c.expires_at<=now() then return 'CODE_EXPIRED'; end if;
 if c.attempts>=5 then return 'TOO_MANY_ATTEMPTS'; end if;
 update university_email_challenges set attempts=attempts+1 where id=p_id;
 if c.code_digest<>p_digest then return 'INVALID_CODE'; end if;
 update university_email_challenges set verified_at=now() where id=p_id;
 update users set verification_status='approved',updated_at=now() where id=app.current_actor();
 insert into audit_logs(actor_id,event_type,target_type,target_id,result)
 values(app.current_actor(),'university_email_verified','verification_request',p_id,'success');
 return 'APPROVED';
end $$;
revoke all on function app.create_university_email_challenge(uuid,text,text) from public;
revoke all on function app.verify_university_email_code(uuid,text) from public;
grant execute on function app.create_university_email_challenge(uuid,text,text) to tetote_app;
grant execute on function app.verify_university_email_code(uuid,text) to tetote_app;
commit;
