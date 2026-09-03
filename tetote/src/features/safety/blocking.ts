import type { BlockResult } from "./client";

/**
 * ブロック関係の画面側の状態。純粋な関数として持ち、Reactなしで検証する。
 *
 * サーバーがブロック一覧を返すAPIをまだ持たないため、この状態はセッション内で
 * 積み上げる。画面の再読み込みで消えるが、サーバー側の関係は残っているので
 * 一覧・応募・メッセージの非表示はサーバーが引き続き保証する。
 */

export type BlockedUsers = ReadonlySet<string>;

export const emptyBlockedUsers: BlockedUsers = new Set();

/** 自分自身はブロックさせない。サーバーも422で拒否するが、画面でも先に止める。 */
export function canBlock(targetUserId: string, selfUserId: string | null): boolean {
  return targetUserId.length > 0 && targetUserId !== selfUserId;
}

/** APIの結果を正として状態へ反映する。同じ操作を繰り返しても同じ状態になる。 */
export function applyBlockResult(
  current: BlockedUsers,
  result: Pick<BlockResult, "userId" | "blocked">,
): BlockedUsers {
  const next = new Set(current);
  if (result.blocked) {
    next.add(result.userId);
  } else {
    next.delete(result.userId);
  }
  return next;
}

/** ブロックした相手が所有する項目を、画面の一覧から取り除く。 */
export function excludeBlocked<T>(
  items: readonly T[],
  blocked: BlockedUsers,
  ownerOf: (item: T) => string | null | undefined,
): T[] {
  if (blocked.size === 0) return [...items];
  return items.filter((item) => {
    const owner = ownerOf(item);
    return !owner || !blocked.has(owner);
  });
}
