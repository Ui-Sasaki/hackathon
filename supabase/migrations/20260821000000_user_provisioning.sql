-- #4 の依頼永続化に必要な、最小限の利用者プロビジョニング。
--
-- users テーブルには INSERT ポリシーを意図的に置いていない（baseline の設計どおり、
-- 通常の DML では作成できない）。SuperTokens で認証は既に済んでいる利用者に対して、
-- 対応する内部 UUID が無ければ作る、という一点だけを行う SECURITY DEFINER 関数を用意する。
--
-- 本関数が行うのは auth_subject への行の存在保証だけであり、role や status を
-- 特権操作で書き換える経路ではない。既存行がある場合は display_name だけを更新する。

begin;

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
    on conflict (auth_subject) do update set
        display_name = excluded.display_name,
        updated_at = now()
    returning id into v_id;
    return v_id;
end;
$$;

revoke all on function app.ensure_user(text, text, account_role) from public;
grant execute on function app.ensure_user(text, text, account_role) to tetote_app;

-- `users` の SELECT ポリシーは自分自身の行しか許さない（baseline の設計どおり）。
-- 一方、公開中の依頼一覧には依頼者の識別子を含める必要がある（従来のインメモリ実装が
-- 一貫してそうしてきた）。行ではなく auth_subject 1列だけを返す narrow な関数を
-- 経由させることで、users テーブルの可視範囲は広げずにこの必要を満たす。
create or replace function app.auth_subject_of(p_user_id uuid)
returns text language sql stable security definer
set search_path = public, pg_temp as $$
    select auth_subject from users where id = p_user_id;
$$;

revoke all on function app.auth_subject_of(uuid) from public;
grant execute on function app.auth_subject_of(uuid) to tetote_app;

-- ---------------------------------------------------------------------------
-- テスト・開発専用のリセット補助（#4）。
--
-- tetote_app には requests への UPDATE/DELETE を意図的に付与していない（状態遷移は
-- 専用関数へ寄せる設計のため）。POST /_mock/reset はこの制約の例外を必要とする唯一の
-- 経路なので、narrow な SECURITY DEFINER 関数として切り出す。汎用の DELETE/TRUNCATE
-- 権限を tetote_app へ与えることはしない。
--
-- この関数はアプリケーションの `MOCK_RESET_ENABLED` ゲート（既定 false、#12）の
-- 内側からのみ呼ばれる想定。ゲートの実体はアプリケーション側にあり、この関数自体は
-- 環境を判定しない。
-- ---------------------------------------------------------------------------

create or replace function app.mock_reset_requests()
returns void language plpgsql security definer
set search_path = public, pg_temp as $$
declare
    v_owner_1024 uuid;
    v_owner_1025 uuid;
begin
    delete from requests;

    v_owner_1024 := app.ensure_user('usr_101', '山田 花子', 'member');
    v_owner_1025 := app.ensure_user('usr_301', '地域住民', 'member');

    insert into requests (
        id, requester_id, title, original_text, category_id, risk_level,
        area_code, scheduled_at, estimated_minutes, required_helpers,
        status, version, created_at
    ) values
    (
        '5fcfec7f-a8b0-58d4-931e-593d60355ee3', v_owner_1024,
        '犬の散歩をお願いしたい', '体調不良のため、小型犬の散歩を30分お願いしたいです。',
        'pet_support', 'medium', 'AREA-001',
        timestamptz '2026-08-19T17:00:00+09:00', 30, 1,
        'published', 3, timestamptz '2026-08-18T10:00:00+09:00'
    ),
    (
        '39521aee-fc9b-5be6-9652-b3cf45d9107f', v_owner_1025,
        '玄関前の雪かきを手伝ってほしい', '玄関から歩道までの雪かきをお願いします。',
        'snow_removal', 'medium', 'AREA-001',
        timestamptz '2026-08-20T09:00:00+09:00', 45, 2,
        'published', 1, timestamptz '2026-08-18T11:00:00+09:00'
    );
end;
$$;

revoke all on function app.mock_reset_requests() from public;
grant execute on function app.mock_reset_requests() to tetote_app;

commit;
