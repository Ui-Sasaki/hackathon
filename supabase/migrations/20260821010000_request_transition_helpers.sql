-- #4 が必要とする、requests の状態遷移用の narrow な関数群。
--
-- baseline は tetote_app に requests への UPDATE/DELETE を意図的に与えていない
-- （「状態遷移・選択・完了・管理処置は専用関数へ寄せる」設計、S4_DB_RLS.md §5.1）。
-- ここではその設計に従い、生の UPDATE を許可する代わりに、行える変更を
-- 狭く限定した2つの SECURITY DEFINER 関数だけを公開する。

begin;

-- 依頼者本人による部分更新。version が一致した行だけを更新し、一致しなければ
-- 何も更新せず NULL を返す（呼び出し側が REQUEST_STATE_CONFLICT を判定する）。
-- 所有者チェックは呼び出し側（request_or_404 の読み取り結果）が既に行っている。
create or replace function app.update_request(
    p_id uuid,
    p_expected_version integer,
    p_title text default null,
    p_original_text text default null,
    p_scheduled_at timestamptz default null,
    p_estimated_minutes integer default null,
    p_required_helpers integer default null
)
returns uuid language sql security definer
set search_path = public, pg_temp as $$
    update requests set
        title = coalesce(p_title, title),
        original_text = coalesce(p_original_text, original_text),
        scheduled_at = coalesce(p_scheduled_at, scheduled_at),
        estimated_minutes = coalesce(p_estimated_minutes, estimated_minutes),
        required_helpers = coalesce(p_required_helpers, required_helpers),
        version = version + 1
     where id = p_id and version = p_expected_version
    returning id;
$$;

revoke all on function app.update_request(
    uuid, integer, text, text, timestamptz, integer, integer
) from public;
grant execute on function app.update_request(
    uuid, integer, text, text, timestamptz, integer, integer
) to tetote_app;

-- status だけを変更する汎用の遷移。
--
-- p_expected_version が null なら version は検査しない（通報による停止など、
-- 呼び出し元が別の方法で正当性を確認済みの経路向け）。非 null なら、一致した
-- 行だけを更新する。
--
-- p_bump_version は「更新できたら version を+1するか」を独立に制御する。
-- 呼び出し元ごとに既存の振る舞いが割れている（select_application は+1する、
-- complete_match/dispute_match は+1しない）ため、1つの関数で両方を賄う。
create or replace function app.set_request_status(
    p_id uuid,
    p_new_status request_status,
    p_expected_version integer default null,
    p_bump_version boolean default true
)
returns uuid language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_id uuid;
begin
    if p_expected_version is null then
        update requests set
            status = p_new_status,
            version = case when p_bump_version then version + 1 else version end
         where id = p_id
        returning id into v_id;
    else
        update requests set
            status = p_new_status,
            version = case when p_bump_version then version + 1 else version end
         where id = p_id and version = p_expected_version
        returning id into v_id;
    end if;
    return v_id;
end;
$$;

revoke all on function app.set_request_status(uuid, request_status, integer, boolean) from public;
grant execute on function app.set_request_status(uuid, request_status, integer, boolean)
    to tetote_app;

commit;
