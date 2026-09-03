import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import {
  applyBlockResult,
  canBlock,
  emptyBlockedUsers,
  excludeBlocked,
  type BlockedUsers,
} from "../features/safety/blocking";
import { setUserBlocked } from "../features/safety/client";

type SafetyContextValue = {
  blockedUsers: BlockedUsers;
  isBlocked: (userId: string) => boolean;
  /** 自分自身や空の対象は false。画面のボタン表示にも使う。 */
  canBlockUser: (userId: string) => boolean;
  blockUser: (userId: string) => Promise<void>;
  unblockUser: (userId: string) => Promise<void>;
  /** ブロックした相手の依頼・応募・メッセージを一覧から除く。 */
  withoutBlocked: <T>(items: readonly T[], ownerOf: (item: T) => string | null | undefined) => T[];
};

const SafetyContext = createContext<SafetyContextValue | null>(null);

export function SafetyProvider({ children }: { children: ReactNode }) {
  const { profile } = useAuth();
  const selfId = profile?.id ?? null;
  const [blockedUsers, setBlockedUsers] = useState<BlockedUsers>(emptyBlockedUsers);

  const blockUser = useCallback(
    async (userId: string) => {
      // API結果を正として反映する。楽観更新はしない（失敗時に画面と実態がずれるため）。
      const result = await setUserBlocked(userId, true);
      setBlockedUsers((current) => applyBlockResult(current, result));
    },
    [],
  );

  const unblockUser = useCallback(async (userId: string) => {
    const result = await setUserBlocked(userId, false);
    setBlockedUsers((current) => applyBlockResult(current, result));
  }, []);

  const value = useMemo<SafetyContextValue>(
    () => ({
      blockedUsers,
      isBlocked: (userId) => blockedUsers.has(userId),
      canBlockUser: (userId) => canBlock(userId, selfId),
      blockUser,
      unblockUser,
      withoutBlocked: (items, ownerOf) => excludeBlocked(items, blockedUsers, ownerOf),
    }),
    [blockedUsers, selfId, blockUser, unblockUser],
  );

  return <SafetyContext.Provider value={value}>{children}</SafetyContext.Provider>;
}

export function useSafety(): SafetyContextValue {
  const context = useContext(SafetyContext);
  if (!context) {
    throw new Error("useSafety must be used inside SafetyProvider");
  }
  return context;
}
