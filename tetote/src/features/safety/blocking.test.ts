import { describe, expect, it } from "vitest";

import { applyBlockResult, canBlock, emptyBlockedUsers, excludeBlocked } from "./blocking";

describe("ブロック状態", () => {
  it("ブロック結果を状態へ反映する", () => {
    const next = applyBlockResult(emptyBlockedUsers, { userId: "usr_301", blocked: true });
    expect(next.has("usr_301")).toBe(true);
  });

  it("解除結果で状態から外す", () => {
    const blocked = applyBlockResult(emptyBlockedUsers, { userId: "usr_301", blocked: true });
    const next = applyBlockResult(blocked, { userId: "usr_301", blocked: false });
    expect(next.has("usr_301")).toBe(false);
  });

  it("同じ操作を繰り返しても状態は変わらない", () => {
    const once = applyBlockResult(emptyBlockedUsers, { userId: "usr_301", blocked: true });
    const twice = applyBlockResult(once, { userId: "usr_301", blocked: true });
    expect([...twice]).toEqual(["usr_301"]);
  });

  it("元の状態を書き換えない", () => {
    const original = new Set(["usr_207"]);
    applyBlockResult(original, { userId: "usr_301", blocked: true });
    expect([...original]).toEqual(["usr_207"]);
  });
});

describe("自己ブロックの防止", () => {
  it("自分自身はブロックできない", () => {
    expect(canBlock("usr_101", "usr_101")).toBe(false);
  });

  it("他人はブロックできる", () => {
    expect(canBlock("usr_301", "usr_101")).toBe(true);
  });

  it("対象が空なら操作させない", () => {
    expect(canBlock("", "usr_101")).toBe(false);
  });
});

describe("ブロックした相手の除外", () => {
  const items = [
    { id: "a", owner: "usr_301" },
    { id: "b", owner: "usr_207" },
    { id: "c", owner: null },
  ];

  it("ブロックした相手の項目を一覧から取り除く", () => {
    const blocked = new Set(["usr_301"]);
    expect(excludeBlocked(items, blocked, (item) => item.owner).map((i) => i.id)).toEqual([
      "b",
      "c",
    ]);
  });

  it("ブロックが無ければそのまま返す", () => {
    expect(excludeBlocked(items, emptyBlockedUsers, (item) => item.owner)).toEqual(items);
  });
});
