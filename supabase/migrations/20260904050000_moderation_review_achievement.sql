begin;

create or replace function app.admin_decide_verification(p_id uuid,p_decision text,p_note text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$
declare v verification_requests%rowtype; begin
 if app.actor_role() not in ('admin','verifier') then return jsonb_build_object('code','ROLE_FORBIDDEN'); end if;
 if p_decision not in ('approved','rejected') then return jsonb_build_object('code','BAD_REQUEST'); end if;
 select * into v from verification_requests where id=p_id for update;
 if not found then return jsonb_build_object('code','VERIFICATION_NOT_FOUND'); end if;
 if v.status<>'pending' then return jsonb_build_object('code','VERIFICATION_STATE_CONFLICT'); end if;
 update verification_requests set status=p_decision::verification_status,reviewer_id=app.current_actor(),reviewed_at=now(),note=p_note,deletion_due_at=case when storage_object_key is null then null else now()+interval '7 days' end,updated_at=now() where id=p_id returning * into v;
 update users set verification_status=p_decision::verification_status,updated_at=now() where id=v.user_id;
 insert into audit_logs(actor_id,event_type,target_type,target_id,result,detail) values(app.current_actor(),'verification_'||p_decision,'verification_request',p_id,'success',jsonb_build_object('note',p_note));
 return jsonb_build_object('code','UPDATED','item',jsonb_build_object('id',v.id,'userId',app.auth_subject_of(v.user_id),'method',v.method,'status',v.status,'createdAt',v.created_at,'reviewedAt',v.reviewed_at,'deletionDueAt',v.deletion_due_at)); end $$;

create or replace function app.admin_set_user_status(p_subject text,p_status text,p_reason text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$ declare v_id uuid; begin
 if not app.is_admin() then return jsonb_build_object('code','ROLE_FORBIDDEN'); end if;
 select id into v_id from users where auth_subject=p_subject;
 if v_id is null then return jsonb_build_object('code','USER_NOT_FOUND'); end if;
 if v_id=app.current_actor() then return jsonb_build_object('code','SELF_STATUS_CHANGE_FORBIDDEN'); end if;
 update users set status=p_status::user_status,updated_at=now() where id=v_id;
 insert into audit_logs(actor_id,event_type,target_type,target_id,result,detail) values(app.current_actor(),'user_'||p_status,'user',v_id,'success',jsonb_build_object('reason',p_reason)); return jsonb_build_object('code','UPDATED'); end $$;

create or replace function app.create_review(p_match uuid,p_eval jsonb,p_comment text)
returns jsonb language plpgsql security definer set search_path=public,pg_temp as $$ declare m matches%rowtype; r requests%rowtype; v_reviewee uuid; v_id uuid; begin
 select * into m from matches where id=p_match for update; if not found then return jsonb_build_object('code','MATCH_NOT_FOUND'); end if;
 select * into r from requests where id=m.request_id;
 if app.current_actor() not in (m.helper_id,r.requester_id) then return jsonb_build_object('code','ROLE_FORBIDDEN'); end if;
 if m.status<>'completed' then return jsonb_build_object('code','MATCH_NOT_COMPLETED'); end if;
 v_reviewee:=case when app.current_actor()=m.helper_id then r.requester_id else m.helper_id end;
 insert into reviews(match_id,reviewer_id,reviewee_id,evaluation,comment) values(p_match,app.current_actor(),v_reviewee,p_eval,p_comment) returning id into v_id;
 return jsonb_build_object('code','CREATED','id',v_id,'matchId',p_match,'reviewerId',app.auth_subject_of(app.current_actor()),'revieweeId',app.auth_subject_of(v_reviewee),'evaluation',p_eval,'comment',p_comment,'createdAt',now());
 exception when unique_violation then return jsonb_build_object('code','DUPLICATE_REVIEW'); end $$;

revoke all on function app.admin_decide_verification(uuid,text,text),app.admin_set_user_status(text,text,text),app.create_review(uuid,jsonb,text) from public;
grant execute on function app.admin_decide_verification(uuid,text,text),app.admin_set_user_status(text,text,text),app.create_review(uuid,jsonb,text) to tetote_app;
commit;
