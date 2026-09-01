/**
 * LLMへ送信する前に、文字起こしテキストから個人情報をマスクする。
 * 要件定義書 11.3「LLM送信前に電話番号、メール、詳細住所、証明書番号をマスクする」に対応する。
 */

export type MaskKind = "email" | "phone" | "address" | "certificate";

export type MaskResult = {
  /** マスク適用後のテキスト。LLMへはこの値だけを送る。 */
  text: string;
  /** 実際にマスクした種別。利用者へ「何を伏せたか」を提示するために使う。 */
  masked: MaskKind[];
};

export const MASK_LABELS: Record<MaskKind, string> = {
  email: "メールアドレス",
  phone: "電話番号",
  address: "住所",
  certificate: "証明書番号",
};

const PLACEHOLDER: Record<MaskKind, string> = {
  email: "[メールアドレス]",
  phone: "[電話番号]",
  address: "[住所]",
  certificate: "[証明書番号]",
};

/**
 * 音声認識結果には全角数字が混ざることがあるため、検出前に半角へ揃える。
 * 表示テキストにも同じ正規化を適用し、マスク位置と表示位置をずらさない。
 */
function normalizeDigits(text: string): string {
  return text
    .replace(/[０-９]/g, (char) =>
      String.fromCharCode(char.charCodeAt(0) - 0xfee0),
    )
    .replace(/[‐‑‒–—―ー－]/g, "-");
}

/**
 * 適用順に意味がある。メールは数字と記号を含むため最初に取り除き、
 * 電話番号を住所や証明書番号より先に判定して数字列の取り合いを防ぐ。
 */
const RULES: { kind: MaskKind; pattern: RegExp }[] = [
  {
    kind: "email",
    pattern: /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g,
  },
  {
    kind: "phone",
    pattern: /0\d{1,4}-\d{1,4}-\d{3,4}|\b0\d{9,10}\b/g,
  },
  {
    kind: "address",
    // 「3丁目4番5号」のような番地表現と、郵便番号・ハイフン区切りの番地。
    pattern:
      /\d{1,4}\s*(?:丁目|番地|番|号)(?:\s*の?\s*\d{1,4}\s*(?:丁目|番地|番|号)?)*|\b\d{3}-\d{4}\b|\b\d{1,4}-\d{1,4}-\d{1,4}\b/g,
  },
  {
    kind: "certificate",
    // 「学籍番号は A1234567」のようなラベル付きと、桁数の多い単独の英数字列。
    pattern:
      /(?:学籍番号|会員番号|証明書番号|保険証番号|免許証番号|マイナンバー)\s*(?:は|:|：)?\s*[A-Za-z0-9-]{4,}|\b[A-Za-z]{1,3}\d{6,}\b|\b\d{8,}\b/g,
  },
];

/**
 * テキストへマスクを適用する。副作用はなく、同じ入力へは常に同じ結果を返す。
 */
export function maskPersonalInfo(text: string): MaskResult {
  let masked = normalizeDigits(text);
  const kinds: MaskKind[] = [];

  for (const rule of RULES) {
    let hit = false;
    masked = masked.replace(rule.pattern, () => {
      hit = true;
      return PLACEHOLDER[rule.kind];
    });

    if (hit) {
      kinds.push(rule.kind);
    }
  }

  return { text: masked, masked: kinds };
}

/**
 * マスクした種別を利用者向けの一文へ変換する。何も伏せていなければ null を返す。
 */
export function describeMasked(kinds: MaskKind[]): string | null {
  if (kinds.length === 0) {
    return null;
  }

  const labels = kinds.map((kind) => MASK_LABELS[kind]).join("・");

  return `${labels}を伏せてから送信します`;
}
