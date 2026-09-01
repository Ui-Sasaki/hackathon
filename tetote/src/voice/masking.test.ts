import { describe, expect, it } from "vitest";

import { describeMasked, maskPersonalInfo } from "./masking";

describe("LLM送信前の個人情報マスク", () => {
  it("メールアドレスと電話番号を伏せる", () => {
    const result = maskPersonalInfo(
      "連絡先は taro.yamada@example.com か 090-1234-5678 です",
    );

    expect(result.text).toBe("連絡先は [メールアドレス] か [電話番号] です");
    expect(result.masked).toEqual(["email", "phone"]);
  });

  it("ハイフンなしの電話番号も伏せる", () => {
    expect(maskPersonalInfo("09012345678へ電話して").text).toBe(
      "[電話番号]へ電話して",
    );
  });

  it("全角数字の電話番号を半角へ揃えてから伏せる", () => {
    expect(maskPersonalInfo("０９０－１２３４－５６７８").text).toBe(
      "[電話番号]",
    );
  });

  it("丁目・番地の詳細住所を伏せる", () => {
    const result = maskPersonalInfo("金沢市扇が丘7丁目1番地まで来てほしい");

    expect(result.text).toBe("金沢市扇が丘[住所]まで来てほしい");
    expect(result.masked).toEqual(["address"]);
  });

  it("郵便番号とハイフン区切りの番地を伏せる", () => {
    expect(maskPersonalInfo("921-8501 の 3-1-2").text).toBe("[住所] の [住所]");
  });

  it("学籍番号などの証明書番号を伏せる", () => {
    const result = maskPersonalInfo("学籍番号は A1234567 です");

    expect(result.text).toBe("[証明書番号] です");
    expect(result.masked).toEqual(["certificate"]);
  });

  it("個人情報を含まない依頼文は変えない", () => {
    const result = maskPersonalInfo("庭の草むしりを30分ほど手伝ってほしい");

    expect(result.text).toBe("庭の草むしりを30分ほど手伝ってほしい");
    expect(result.masked).toEqual([]);
  });

  it("同じ入力へは同じ結果を返す", () => {
    const text = "090-1234-5678 と 3-1-2";

    expect(maskPersonalInfo(text)).toEqual(maskPersonalInfo(text));
  });

  it("伏せた種別を利用者向けの一文へ変換する", () => {
    expect(describeMasked(["email", "phone"])).toBe(
      "メールアドレス・電話番号を伏せてから送信します",
    );
    expect(describeMasked([])).toBeNull();
  });
});
