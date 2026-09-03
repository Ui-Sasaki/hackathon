/**
 * ブラウザの Web Speech API を扱う層。
 * 画面はこのアダプタ越しにだけ音声認識へ触れるため、テストでは差し替えられる。
 *
 * 音声データの扱い：録音した音声はブラウザとOSの音声認識が処理し、
 * このアプリは音声そのものを保存も送信もしない。保持するのは文字起こし結果だけで、
 * 取消・画面離脱・確認後の送信完了で破棄する。詳細は docs/voice-input.md を参照。
 */

import { VoiceErrorReason } from "./session";

export type RecognitionHandlers = {
  onTranscript: (text: string) => void;
  onError: (reason: VoiceErrorReason) => void;
};

export type RecognitionController = {
  /** 録音を止めて、そこまでの結果を文字起こしする。 */
  stop: () => void;
  /** 録音を破棄する。結果は通知しない。 */
  abort: () => void;
};

export type RecognitionAdapter = {
  isSupported: () => boolean;
  start: (handlers: RecognitionHandlers) => RecognitionController;
};

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
};

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  }
}

function constructorOf(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/** ブラウザごとに異なるエラーコードを、画面が扱う4種類の理由へ寄せる。 */
export function toErrorReason(code: unknown): VoiceErrorReason {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "permission-denied";
    case "audio-capture":
      return "recording-failed";
    case "no-speech":
      return "empty-transcript";
    default:
      return "transcription-failed";
  }
}

export const webSpeechAdapter: RecognitionAdapter = {
  isSupported: () => constructorOf() !== null,

  start: (handlers) => {
    const Recognition = constructorOf();

    if (!Recognition) {
      handlers.onError("unsupported");
      return { stop: () => {}, abort: () => {} };
    }

    const recognition = new Recognition();
    recognition.lang = "ja-JP";
    recognition.interimResults = false;
    recognition.continuous = false;

    // 取消後に onend や onerror が届いても画面へ通知しないための番人。
    let discarded = false;
    let transcript = "";

    recognition.onresult = (event: any) => {
      const results = event?.results;

      if (!results || results.length === 0) {
        return;
      }

      transcript = Array.from({ length: results.length }, (_, index) => {
        return results[index]?.[0]?.transcript ?? "";
      }).join("");
    };

    recognition.onerror = (event: any) => {
      if (discarded) {
        return;
      }

      // 取消時の aborted は失敗ではないため無視する。
      if (event?.error === "aborted") {
        return;
      }

      discarded = true;
      handlers.onError(toErrorReason(event?.error));
    };

    recognition.onend = () => {
      if (discarded) {
        return;
      }

      discarded = true;
      handlers.onTranscript(transcript);
    };

    try {
      recognition.start();
    } catch {
      discarded = true;
      handlers.onError("recording-failed");
    }

    return {
      stop: () => recognition.stop(),
      abort: () => {
        discarded = true;
        recognition.abort();
      },
    };
  },
};
