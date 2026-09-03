import { apiClient, type ApiClient } from "../../api/client";
import { ApiError } from "../../api/errors";

/**
 * 公開依頼の一覧・詳細をAPIから取得する層。
 * 画面が使うカード表示用の形（RequestCard）への変換もここで行い、
 * 画面側はAPIのレスポンス形式を知らなくて済むようにする。
 */

export type PublicRequest = {
  id: string;
  title: string;
  description: string;
  category: string;
  areaLabel: string;
  distanceKm: number | null;
  scheduledAt: string;
  estimatedMinutes: number;
  requiredHelpers: number;
  acceptedHelpers: number;
  status: string;
  warnings: string[];
};

export type RequestListPage = {
  items: PublicRequest[];
  nextCursor: string | null;
};

/** 一覧カードが表示に使う形。 */
export type RequestCard = {
  id: string;
  title: string;
  description: string;
  location: string;
  distance: string;
  deadline: string;
  meta: string;
  tags: string[];
};

const listErrorMessages: Record<string, string> = {
  AUTHENTICATION_REQUIRED: "セッションの有効期限が切れました。もう一度ログインしてください。",
  VALIDATION_ERROR: "検索条件を確認してください。",
};

export function requestListErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return listErrorMessages[error.code] ?? error.message;
  }
  return "依頼を読み込めませんでした。通信環境を確認して、もう一度お試しください。";
}

// バックエンドのカテゴリ識別子を、一覧のタグ表示へ寄せる。
// 未知のカテゴリは「#その他」として表示だけ行い、絞り込み対象にはならない。
const categoryTags: Record<string, string[]> = {
  pet_support: ["#動物", "#散歩"],
  snow_removal: ["#力仕事"],
  shopping: ["#買い物"],
  cleaning: ["#日常生活"],
  digital_support: ["#デジタル", "#パソコン"],
  escort: ["#付き添い", "#外出"],
  exercise: ["#運動"],
  walking: ["#散歩"],
};

export function tagsForCategory(category: string): string[] {
  return categoryTags[category] ?? ["#その他"];
}

function formatMonthDay(isoDate: string): string {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

/**
 * APIの依頼をカード表示用の形へ変換する。
 * 年齢・性別はAPIが返さない（公開一覧に個人情報を出さない設計）ため、
 * 代わりに所要時間と募集人数を表示する。
 */
export function toRequestCard(item: PublicRequest): RequestCard {
  return {
    id: item.id,
    title: item.title,
    description: item.description,
    location: item.areaLabel,
    distance: item.distanceKm === null ? "" : `${item.distanceKm}km`,
    deadline: formatMonthDay(item.scheduledAt),
    meta: `約${item.estimatedMinutes}分・${item.requiredHelpers}人募集`,
    tags: tagsForCategory(item.category),
  };
}

export type ListRequestsParams = {
  areaCode?: string;
  category?: string;
  cursor?: string;
};

export async function listPublicRequests(
  params: ListRequestsParams = {},
  client: ApiClient = apiClient,
): Promise<RequestListPage> {
  const query = new URLSearchParams();
  if (params.areaCode) query.set("areaCode", params.areaCode);
  if (params.category) query.set("category", params.category);
  if (params.cursor) query.set("cursor", params.cursor);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";

  const page = await client.get<RequestListPage>(`/requests${suffix}`);
  return { items: page.items, nextCursor: page.nextCursor };
}

export async function getRequest(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<PublicRequest> {
  return client.get<PublicRequest>(`/requests/${encodeURIComponent(requestId)}`);
}
