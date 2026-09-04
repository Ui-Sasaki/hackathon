import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  ScrollView,
  Modal,
} from "react-native";
import {
  useLocalSearchParams,
  useRouter,
} from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useFontSize } from "../../context/FontSizeContext";
import { ApiAuthenticationError, ApiError } from "../../api/errors";
import {
  canProceedAfterMasking,
  confirmMaskingPreview,
  previewRequestMasking,
  type MaskingPreviewState,
} from "../../api/request-masking";
import {
  structureConfirmedRequest,
  updateStructuredDraft,
  type RequestStructuringState,
} from "../../api/request-structuring";
import {
  beginRequestCreation,
  submitRequestCreation,
  type CreatedRequest,
} from "../../api/request-creation";

function maskingErrorMessage(error: unknown): string {
  if (error instanceof ApiAuthenticationError) {
    return "セッションの有効期限が切れました。もう一度ログインしてください。";
  }

  if (error instanceof ApiError && error.status === 422) {
    return "依頼内容を確認して、もう一度お試しください。";
  }

  return "マスキング結果を取得できませんでした。通信環境を確認してください。";
}

function structuringErrorMessage(error: unknown): string {
  if (error instanceof ApiAuthenticationError) {
    return "セッションの有効期限が切れました。もう一度ログインしてください。";
  }

  if (error instanceof ApiError && error.status === 422) {
    return "依頼内容を確認して、もう一度お試しください。";
  }

  return "依頼内容を構造化できませんでした。";
}

function publishErrorMessage(error: unknown): string {
  if (error instanceof ApiAuthenticationError) {
    return "セッションの有効期限が切れました。もう一度ログインしてください。";
  }

  if (error instanceof ApiError && error.status === 422) {
    return "依頼内容を確認して、もう一度お試しください。";
  }

  return "依頼を公開できませんでした。通信環境を確認してください。";
}

const TIME_SLOTS = Array.from({ length: 15 }, (_, index) => {
  const hour = index + 8;

  return {
    label: `${hour}:00〜${hour + 1}:00`,
    hour,
  };
});

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

function padNumber(value: number) {
  return String(value).padStart(2, "0");
}

function createScheduledAt(date: Date, hour: number) {
  return `${date.getFullYear()}-${padNumber(
    date.getMonth() + 1
  )}-${padNumber(date.getDate())}T${padNumber(
    hour
  )}:00:00+09:00`;
}

function parseScheduledAt(value: string | null | undefined) {
  if (!value) {
    return {
      date: null as Date | null,
      hour: null as number | null,
    };
  }

  const match = value.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):/
  );

  if (!match) {
    return {
      date: null as Date | null,
      hour: null as number | null,
    };
  }

  return {
    date: new Date(
      Number(match[1]),
      Number(match[2]) - 1,
      Number(match[3])
    ),
    hour: Number(match[4]),
  };
}

function formatSelectedDate(date: Date | null) {
  if (!date) return "日付を選択";

  return `${date.getFullYear()}年${
    date.getMonth() + 1
  }月${date.getDate()}日`;
}

export default function RequestConfirmScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const [calendarOpen, setCalendarOpen] = useState(false);
  const [timeOpen, setTimeOpen] = useState(false);

  const [calendarMonth, setCalendarMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const [maskingState, setMaskingState] =
    useState<MaskingPreviewState | null>(null);

  const [maskingLoading, setMaskingLoading] =
    useState(true);

  const [structuringState, setStructuringState] =
    useState<RequestStructuringState | null>(null);

  const [structuringLoading, setStructuringLoading] =
    useState(false);

  const [publishing, setPublishing] =
    useState(false);

  const [publishMessage, setPublishMessage] =
    useState("");

  const [createdRequest, setCreatedRequest] =
    useState<CreatedRequest | null>(null);

  const {
    content,
    location,
    areaCode,
    time,
    deadline,
  } = useLocalSearchParams<{
    content?: string;
    location?: string;
    areaCode?: string;
    time?: string;
    deadline?: string;
  }>();

  const retryMaskingPreview = async () => {
    setMaskingLoading(true);
    setMaskingState(null);

    const state = await previewRequestMasking(
      content ?? ""
    );

    setMaskingState(state);
    setMaskingLoading(false);
  };

  useEffect(() => {
    let active = true;

    void previewRequestMasking(
      content ?? ""
    ).then((state) => {
      if (!active) return;

      setMaskingState(state);
      setMaskingLoading(false);
    });

    return () => {
      active = false;
    };
  }, [content]);

  const handleSubmit = async () => {
    if (
      !canProceedAfterMasking(maskingState) ||
      structuringLoading
    ) {
      return;
    }

    setPublishMessage("");
    setStructuringLoading(true);

    const state =
      await structureConfirmedRequest(
        maskingState
      );

    setStructuringState(state);
    setStructuringLoading(false);
  };

  const validatePublishInput = () => {
const draft =
  structuringState?.status === "draft" ||
  structuringState?.status === "manual"
    ? structuringState.draft
    : null;

    if (!draft) {
      return "AI整理後の下書きを確認してください。";
    }

    if (
      !draft.title.trim() ||
      !draft.description.trim() ||
      !draft.category.trim()
    ) {
      return "タイトル、依頼内容、カテゴリを入力してください。";
    }

    if (!draft.scheduledAt) {
      return "希望日と希望時間を選択してください。";
    }

    if (
      !draft.estimatedMinutes ||
      draft.estimatedMinutes < 10 ||
      draft.estimatedMinutes > 240
    ) {
      return "所要時間は10分から240分の範囲で入力してください。";
    }

    if (
      !draft.requiredHelpers ||
      draft.requiredHelpers < 1 ||
      draft.requiredHelpers > 5
    ) {
      return "必要人数は1人から5人の範囲で入力してください。";
    }

    if (
      draft.riskLevel === "high" ||
      draft.riskLevel === "prohibited"
    ) {
      return "危険度が高い依頼は公開できません。内容を修正してください。";
    }

    return null;
  };

  const handlePublish = async () => {
const draft =
  structuringState?.status === "draft" ||
  structuringState?.status === "manual"
    ? structuringState.draft
    : null;    const validationMessage =
      validatePublishInput();

    if (!draft || validationMessage) {
      setPublishMessage(
        validationMessage ??
          "依頼内容を確認してください。"
      );
      return;
    }

    setPublishing(true);
    setPublishMessage("");

    const result =
      await submitRequestCreation(
        beginRequestCreation({
          title: draft.title.trim(),
          description:
            draft.description.trim(),
          category: draft.category.trim(),
          scheduledAt:
            draft.scheduledAt as string,
          estimatedMinutes:
            draft.estimatedMinutes as number,
          requiredHelpers:
            draft.requiredHelpers as number,
          areaCode: areaCode || undefined,
          riskLevel:
            draft.riskLevel as
              | "low"
              | "medium",
          confirmed: true,
        })
      );

    if (result.status === "created") {
      setCreatedRequest(result.request);
      setPublishMessage(
        "依頼を公開しました。"
      );
    } else if (
      result.status === "conflict"
    ) {
      setPublishMessage(
        "同じ依頼はすでに作成されています。"
      );
    } else {
      setPublishMessage(
        publishErrorMessage(result.error)
      );
    }

    setPublishing(false);
  };

const scheduledSelection = parseScheduledAt(
  structuringState?.status === "draft" ||
  structuringState?.status === "manual"
    ? structuringState.draft.scheduledAt
    : null
);
  const selectedDate =
    scheduledSelection.date;

  const selectedHour =
    scheduledSelection.hour;

  const selectedTimeLabel =
    selectedHour !== null
      ? `${selectedHour}:00〜${
          selectedHour + 1
        }:00`
      : "時間を選択";

  const calendarYear =
    calendarMonth.getFullYear();

  const calendarMonthIndex =
    calendarMonth.getMonth();

  const firstDayOfMonth = new Date(
    calendarYear,
    calendarMonthIndex,
    1
  ).getDay();

  const daysInMonth = new Date(
    calendarYear,
    calendarMonthIndex + 1,
    0
  ).getDate();

  const calendarDays = [
    ...Array(firstDayOfMonth).fill(null),
    ...Array.from(
      { length: daysInMonth },
      (_, index) => index + 1
    ),
  ];

  const updateScheduledAt = (
    date: Date | null,
    hour: number | null
  ) => {
    if (!date || hour === null) return;

    const scheduledAt =
      createScheduledAt(date, hour);

    setStructuringState((state) =>
      state
        ? updateStructuredDraft(state, {
            scheduledAt,
          })
        : state
    );
  };

  const selectDate = (day: number) => {
    const date = new Date(
      calendarYear,
      calendarMonthIndex,
      day
    );

    if (selectedHour !== null) {
      updateScheduledAt(
        date,
        selectedHour
      );
    } else {
      setStructuringState((state) =>
        state
          ? updateStructuredDraft(state, {
              scheduledAt:
                createScheduledAt(
                  date,
                  9
                ),
            })
          : state
      );
    }

    setCalendarOpen(false);
    setTimeOpen(true);
  };

  const selectTime = (hour: number) => {
    if (!selectedDate) return;

    updateScheduledAt(
      selectedDate,
      hour
    );

    setTimeOpen(false);
  };

  const previousMonth = () => {
    setCalendarMonth(
      new Date(
        calendarYear,
        calendarMonthIndex - 1,
        1
      )
    );
  };

  const nextMonth = () => {
    setCalendarMonth(
      new Date(
        calendarYear,
        calendarMonthIndex + 1,
        1
      )
    );
  };

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={
          styles.scrollContent
        }
        showsVerticalScrollIndicator={
          false
        }
      >
        <View style={styles.container}>
          <View style={styles.header}>
            <Pressable
              onPress={() =>
                router.back()
              }
              style={({ pressed }) => [
                styles.backButton,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons
                name="arrow-back"
                size={21}
                color="#111111"
              />

              <Text
                style={styles.backText}
              >
                戻る
              </Text>
            </Pressable>

            <Text style={styles.title}>
              依頼確認
            </Text>

            <Ionicons
              name="hand-left"
              size={42}
              color="#191600"
            />
          </View>

          <View
            style={styles.confirmCard}
          >
            <Text
              style={styles.sectionTitle}
            >
              依頼内容
            </Text>

            <View style={styles.infoBox}>
              <Text
                style={styles.infoText}
              >
                {maskingState?.preview
                  ?.maskedText ??
                  content ??
                  "未入力"}
              </Text>
            </View>

            {structuringState?.status ===
              "error" && (
              <View
                style={
                  styles.structuringBox
                }
              >
                <Text
                  style={styles.errorText}
                >
                  {structuringErrorMessage(
                    structuringState.error
                  )}
                </Text>
              </View>
            )}

            {(structuringState?.status ===
              "draft" ||
              structuringState?.status ===
                "manual") && (
              <View
                style={
                  styles.structuringBox
                }
              >
                <Text
                  style={
                    styles.maskingTitle
                  }
                >
                  {structuringState.status ===
                  "manual"
                    ? "手入力で下書きを仕上げる"
                    : "AIが整理した下書き（未公開）"}
                </Text>

                {structuringState.status ===
                  "manual" && (
                  <Text
                    style={
                      styles.errorText
                    }
                  >
                    AIを利用できないため、入力内容を保持して手入力へ切り替えました。
                  </Text>
                )}

                {structuringState.additionalQuestion && (
                  <Text
                    style={
                      styles.questionText
                    }
                  >
                    {
                      structuringState.additionalQuestion
                    }
                  </Text>
                )}

                <Text
                  style={
                    styles.draftLabel
                  }
                >
                  タイトル
                </Text>

                <TextInput
                  accessibilityLabel="依頼タイトル"
                  onChangeText={(title) =>
                    setStructuringState(
                      (state) =>
                        state
                          ? updateStructuredDraft(
                              state,
                              {
                                title,
                              }
                            )
                          : state
                    )
                  }
                  style={
                    styles.draftInput
                  }
                  value={
                    structuringState
                      .draft.title
                  }
                />

                <Text
                  style={
                    styles.draftLabel
                  }
                >
                  依頼内容
                </Text>

                <TextInput
                  accessibilityLabel="構造化した依頼内容"
                  multiline
                  onChangeText={(
                    description
                  ) =>
                    setStructuringState(
                      (state) =>
                        state
                          ? updateStructuredDraft(
                              state,
                              {
                                description,
                              }
                            )
                          : state
                    )
                  }
                  style={[
                    styles.draftInput,
                    styles.draftDescription,
                  ]}
                  value={
                    structuringState
                      .draft.description
                  }
                />

                <Text
                  style={
                    styles.draftLabel
                  }
                >
                  カテゴリ
                </Text>

                <TextInput
                  accessibilityLabel="依頼カテゴリ"
                  onChangeText={(
                    category
                  ) =>
                    setStructuringState(
                      (state) =>
                        state
                          ? updateStructuredDraft(
                              state,
                              {
                                category,
                              }
                            )
                          : state
                    )
                  }
                  style={
                    styles.draftInput
                  }
                  value={
                    structuringState
                      .draft.category
                  }
                />

                <Text
                  style={
                    styles.draftLabel
                  }
                >
                  希望日
                </Text>

                <Pressable
                  onPress={() => {
                    if (selectedDate) {
                      setCalendarMonth(
                        new Date(
                          selectedDate.getFullYear(),
                          selectedDate.getMonth(),
                          1
                        )
                      );
                    }

                    setCalendarOpen(true);
                  }}
                  style={({ pressed }) => [
                    styles.dateTimeSelector,
                    pressed &&
                      styles.pressed,
                  ]}
                >
                  <Text
                    style={[
                      styles.dateTimeSelectorText,
                      !selectedDate &&
                        styles.dateTimePlaceholder,
                    ]}
                  >
                    {formatSelectedDate(
                      selectedDate
                    )}
                  </Text>

                  <Ionicons
                    name="calendar-outline"
                    size={21}
                    color="#D89B31"
                  />
                </Pressable>

                <Text
                  style={
                    styles.draftLabel
                  }
                >
                  希望時間
                </Text>

                <Pressable
                  disabled={!selectedDate}
                  onPress={() =>
                    setTimeOpen(true)
                  }
                  style={({ pressed }) => [
                    styles.dateTimeSelector,
                    !selectedDate &&
                      styles.dateTimeSelectorDisabled,
                    pressed &&
                      selectedDate &&
                      styles.pressed,
                  ]}
                >
                  <Text
                    style={[
                      styles.dateTimeSelectorText,
                      selectedHour ===
                        null &&
                        styles.dateTimePlaceholder,
                    ]}
                  >
                    {selectedTimeLabel}
                  </Text>

                  <Ionicons
                    name="chevron-down"
                    size={20}
                    color={
                      selectedDate
                        ? "#D89B31"
                        : "#AAAAAA"
                    }
                  />
                </Pressable>

                <Text
                  style={
                    styles.draftLabel
                  }
                >
                  所要時間（分）
                </Text>

                <TextInput
                  accessibilityLabel="所要時間"
                  keyboardType="number-pad"
                  onChangeText={(value) =>
                    setStructuringState(
                      (state) =>
                        state
                          ? updateStructuredDraft(
                              state,
                              {
                                estimatedMinutes:
                                  Number(
                                    value
                                  ) ||
                                  null,
                              }
                            )
                          : state
                    )
                  }
                  style={
                    styles.draftInput
                  }
                  value={
                    structuringState.draft.estimatedMinutes?.toString() ??
                    ""
                  }
                />

                <Text
                  style={
                    styles.draftLabel
                  }
                >
                  必要人数
                </Text>

                <TextInput
                  accessibilityLabel="必要人数"
                  keyboardType="number-pad"
                  onChangeText={(value) =>
                    setStructuringState(
                      (state) =>
                        state
                          ? updateStructuredDraft(
                              state,
                              {
                                requiredHelpers:
                                  Number(
                                    value
                                  ) ||
                                  null,
                              }
                            )
                          : state
                    )
                  }
                  style={
                    styles.draftInput
                  }
                  value={
                    structuringState.draft.requiredHelpers?.toString() ??
                    ""
                  }
                />

                <Text
                  style={
                    styles.unpublishedText
                  }
                >
                  この下書きはまだ公開されていません。
                </Text>
              </View>
            )}

            <View
              style={styles.maskingBox}
            >
              <Text
                style={styles.maskingTitle}
              >
                個人情報のマスキング確認
              </Text>

              {maskingLoading && (
                <ActivityIndicator
                  color="#D89B31"
                />
              )}

              {maskingState?.status ===
                "error" && (
                <>
                  <Text
                    style={
                      styles.errorText
                    }
                  >
                    {maskingErrorMessage(
                      maskingState.error
                    )}
                  </Text>

                  <Pressable
                    onPress={() =>
                      void retryMaskingPreview()
                    }
                    style={
                      styles.retryButton
                    }
                  >
                    <Text
                      style={
                        styles.retryButtonText
                      }
                    >
                      再試行する
                    </Text>
                  </Pressable>
                </>
              )}

              {maskingState?.preview && (
                <>
                  <Text
                    style={
                      styles.maskingMeta
                    }
                  >
                    検出種別:{" "}
                    {maskingState.preview.detections
                      .map(
                        (item) =>
                          item.type
                      )
                      .join("、") ||
                      "なし"}
                  </Text>

                  <Text
                    style={
                      styles.maskingMeta
                    }
                  >
                    ルール版:{" "}
                    {
                      maskingState.preview
                        .ruleVersion
                    }
                  </Text>

                  <Pressable
                    disabled={
                      maskingState.status ===
                      "confirmed"
                    }
                    onPress={() =>
                      setMaskingState(
                        confirmMaskingPreview(
                          maskingState
                        )
                      )
                    }
                    style={[
                      styles.maskingConfirmButton,
                      maskingState.status ===
                        "confirmed" &&
                        styles.confirmedButton,
                    ]}
                  >
                    <Text
                      style={
                        styles.maskingConfirmText
                      }
                    >
                      {maskingState.status ===
                      "confirmed"
                        ? "マスキング結果を確認済み"
                        : "マスキング結果を確認しました"}
                    </Text>
                  </Pressable>
                </>
              )}
            </View>

            <Text
              style={styles.sectionTitle}
            >
              場所
            </Text>

            <View style={styles.infoBox}>
              <Text
                style={styles.infoText}
              >
                {location || "未入力"}
              </Text>
            </View>

            <Text
              style={styles.sectionTitle}
            >
              必要な時間
            </Text>

            <View
              style={styles.smallInfoBox}
            >
              <Text
                style={styles.infoText}
              >
                {time || "未選択"}
              </Text>
            </View>

            <Text
              style={styles.sectionTitle}
            >
              依頼期限
            </Text>

            <View
              style={styles.smallInfoBox}
            >
              <Text
                style={styles.infoText}
              >
                {deadline || "未選択"}
              </Text>
            </View>

            <View
              style={styles.noticeBox}
            >
              <Ionicons
                name="information-circle-outline"
                size={22}
                color="#D89B31"
              />

              <Text
                style={styles.noticeText}
              >
                内容を確認して、問題がなければ依頼してください
              </Text>
            </View>

            {createdRequest ? (
              <View
                style={
                  styles.publishSuccessBox
                }
              >
                <Ionicons
                  name="checkmark-circle"
                  size={22}
                  color="#245C2D"
                />

                <View
                  style={
                    styles.publishSuccessTextBox
                  }
                >
                  <Text
                    style={
                      styles.publishSuccessTitle
                    }
                  >
                    依頼を公開しました
                  </Text>

                  <Text
                    style={
                      styles.publishSuccessText
                    }
                  >
                    応募者の確認へ進めます。
                  </Text>
                </View>
              </View>
            ) : null}

            <Pressable
              disabled={
                !canProceedAfterMasking(
                  maskingState
                ) ||
                structuringLoading ||
                publishing
              }
              onPress={() => {
                if (createdRequest) {
                  router.replace({
                    pathname:
                      "/help/requests",
                    params: {
                      requestId:
                        createdRequest.id,
                    },
                  });

                  return;
                }

                void (
  structuringState?.status === "draft" ||
  structuringState?.status === "manual"
    ? handlePublish()
    : handleSubmit()
);
              }}
              style={({ pressed }) => [
                styles.submitButton,
                (!canProceedAfterMasking(
                  maskingState
                ) ||
                  structuringLoading ||
                  publishing) &&
                  styles.disabledButton,
                pressed &&
                  styles.pressed,
              ]}
            >
              {structuringLoading ||
              publishing ? (
                <ActivityIndicator
                  color="#FFFFFF"
                />
              ) : (
                <Text
                  style={
                    styles.submitButtonText
                  }
                >
                  {createdRequest
                    ? "応募者確認へ進む"
                    : structuringState?.status ===
                          "draft" ||
                        structuringState?.status ===
                          "manual"
                      ? "内容を確認して公開する"
                      : "AIで内容を整理する"}
                </Text>
              )}
            </Pressable>

            {publishMessage ? (
              <Text
                style={
                  createdRequest
                    ? styles.successText
                    : styles.errorText
                }
              >
                {publishMessage}
              </Text>
            ) : null}

            <Pressable
              onPress={() =>
                router.back()
              }
              style={({ pressed }) => [
                styles.editButton,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={
                  styles.editButtonText
                }
              >
                内容を修正する
              </Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>

      <Modal
        visible={calendarOpen}
        transparent
        animationType="fade"
        onRequestClose={() =>
          setCalendarOpen(false)
        }
      >
        <View
          style={styles.modalOverlay}
        >
          <View
            style={styles.calendarModal}
          >
            <View
              style={
                styles.calendarHeader
              }
            >
              <Pressable
                onPress={previousMonth}
                style={
                  styles.calendarArrow
                }
              >
                <Ionicons
                  name="chevron-back"
                  size={24}
                  color="#245C2D"
                />
              </Pressable>

              <Text
                style={
                  styles.calendarTitle
                }
              >
                {calendarYear}年
                {calendarMonthIndex + 1}
                月
              </Text>

              <Pressable
                onPress={nextMonth}
                style={
                  styles.calendarArrow
                }
              >
                <Ionicons
                  name="chevron-forward"
                  size={24}
                  color="#245C2D"
                />
              </Pressable>
            </View>

            <View
              style={styles.weekRow}
            >
              {WEEKDAYS.map(
                (weekday) => (
                  <Text
                    key={weekday}
                    style={
                      styles.weekText
                    }
                  >
                    {weekday}
                  </Text>
                )
              )}
            </View>

            <View
              style={styles.calendarGrid}
            >
              {calendarDays.map(
                (day, index) => {
                  if (day === null) {
                    return (
                      <View
                        key={`empty-${index}`}
                        style={
                          styles.calendarDay
                        }
                      />
                    );
                  }

                  const active =
                    selectedDate?.getFullYear() ===
                      calendarYear &&
                    selectedDate?.getMonth() ===
                      calendarMonthIndex &&
                    selectedDate?.getDate() ===
                      day;

                  return (
                    <Pressable
                      key={day}
                      onPress={() =>
                        selectDate(day)
                      }
                      style={[
                        styles.calendarDay,
                        active &&
                          styles.calendarDaySelected,
                      ]}
                    >
                      <Text
                        style={[
                          styles.calendarDayText,
                          active &&
                            styles.calendarDayTextSelected,
                        ]}
                      >
                        {day}
                      </Text>
                    </Pressable>
                  );
                }
              )}
            </View>

            <Pressable
              onPress={() =>
                setCalendarOpen(false)
              }
              style={
                styles.modalCancel
              }
            >
              <Text
                style={
                  styles.modalCancelText
                }
              >
                キャンセル
              </Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      <Modal
        visible={timeOpen}
        transparent
        animationType="fade"
        onRequestClose={() =>
          setTimeOpen(false)
        }
      >
        <View
          style={styles.modalOverlay}
        >
          <View
            style={styles.timeModal}
          >
            <Text
              style={
                styles.timeModalTitle
              }
            >
              希望時間を選択
            </Text>

            <Text
              style={
                styles.timeModalDate
              }
            >
              {formatSelectedDate(
                selectedDate
              )}
            </Text>

            <ScrollView
              style={styles.timeList}
              showsVerticalScrollIndicator={
                false
              }
            >
              {TIME_SLOTS.map(
                (slot) => {
                  const active =
                    selectedHour ===
                    slot.hour;

                  return (
                    <Pressable
                      key={slot.hour}
                      onPress={() =>
                        selectTime(
                          slot.hour
                        )
                      }
                      style={[
                        styles.timeOption,
                        active &&
                          styles.timeOptionSelected,
                      ]}
                    >
                      <Text
                        style={[
                          styles.timeOptionText,
                          active &&
                            styles.timeOptionTextSelected,
                        ]}
                      >
                        {slot.label}
                      </Text>

                      {active && (
                        <Ionicons
                          name="checkmark"
                          size={20}
                          color="#FFFFFF"
                        />
                      )}
                    </Pressable>
                  );
                }
              )}
            </ScrollView>

            <Pressable
              onPress={() =>
                setTimeOpen(false)
              }
              style={
                styles.modalCancel
              }
            >
              <Text
                style={
                  styles.modalCancelText
                }
              >
                キャンセル
              </Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const createStyles = (scale: number) =>
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: "#FFF5E9",
    },

    scrollContent: {
      flexGrow: 1,
      alignItems: "center",
      paddingBottom: 30,
    },

    container: {
      width: "100%",
      maxWidth: 520,
      paddingHorizontal: 28,
      paddingTop: 38,
    },

    header: {
      width: "100%",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 18,
    },

    backButton: {
      minHeight: 38,
      paddingHorizontal: 12,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      flexDirection: "row",
      alignItems: "center",
      gap: 3,
    },

    backText: {
      color: "#111111",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    title: {
      color: "#111111",
      fontSize: 20 * scale,
      fontWeight: "900",
    },

    confirmCard: {
      width: "100%",
      borderWidth: 2,
      borderColor: "#F2A329",
      borderRadius: 28,
      paddingHorizontal: 22,
      paddingTop: 24,
      paddingBottom: 24,
    },

    sectionTitle: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "900",
      marginBottom: 8,
    },

    maskingBox: {
      width: "100%",
      backgroundColor: "#FFF0D6",
      borderRadius: 16,
      padding: 14,
      marginBottom: 20,
      gap: 8,
    },

    maskingTitle: {
      color: "#8B651F",
      fontSize: 14 * scale,
      fontWeight: "900",
    },

    maskingMeta: {
      color: "#6F531E",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "700",
    },

    errorText: {
      color: "#A52A2A",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "700",
    },

    successText: {
      color: "#245C2D",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "800",
      textAlign: "center",
    },

    retryButton: {
      alignSelf: "flex-start",
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      paddingHorizontal: 14,
      paddingVertical: 8,
    },

    retryButtonText: {
      color: "#333333",
      fontSize: 12 * scale,
      fontWeight: "800",
    },

    maskingConfirmButton: {
      minHeight: 42,
      borderRadius: 999,
      backgroundColor: "#D89B31",
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 12,
    },

    confirmedButton: {
      backgroundColor: "#6E8B3D",
    },

    maskingConfirmText: {
      color: "#FFFFFF",
      fontSize: 13 * scale,
      fontWeight: "800",
    },

    structuringBox: {
      width: "100%",
      backgroundColor: "#FFF0D6",
      borderRadius: 16,
      padding: 14,
      marginBottom: 20,
      gap: 8,
    },

    questionText: {
      color: "#6F531E",
      fontSize: 13 * scale,
      lineHeight: 19 * scale,
      fontWeight: "800",
    },

    draftLabel: {
      color: "#333333",
      fontSize: 12 * scale,
      fontWeight: "800",
    },

    draftInput: {
      width: "100%",
      minHeight: 44,
      borderWidth: 1,
      borderColor: "#E1C58F",
      borderRadius: 12,
      backgroundColor: "#FFFFFF",
      color: "#333333",
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 14 * scale,
    },

    draftDescription: {
      minHeight: 90,
      textAlignVertical: "top",
    },

    dateTimeSelector: {
      width: "100%",
      minHeight: 48,
      borderWidth: 1,
      borderColor: "#E1C58F",
      borderRadius: 12,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 14,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 6,
    },

    dateTimeSelectorDisabled: {
      opacity: 0.5,
    },

    dateTimeSelectorText: {
      color: "#333333",
      fontSize: 14 * scale,
      fontWeight: "700",
    },

    dateTimePlaceholder: {
      color: "#999999",
    },

    unpublishedText: {
      color: "#8B651F",
      fontSize: 12 * scale,
      fontWeight: "700",
    },

    infoBox: {
      width: "100%",
      minHeight: 74,
      borderRadius: 18,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 16,
      paddingVertical: 14,
      justifyContent: "center",
      marginBottom: 20,
    },

    smallInfoBox: {
      width: "100%",
      minHeight: 48,
      borderRadius: 999,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 16,
      justifyContent: "center",
      marginBottom: 20,
    },

    infoText: {
      color: "#333333",
      fontSize: 14 * scale,
      lineHeight: 21 * scale,
      fontWeight: "700",
    },

    noticeBox: {
      width: "100%",
      backgroundColor: "#FFF0D6",
      borderRadius: 16,
      paddingHorizontal: 14,
      paddingVertical: 12,
      flexDirection: "row",
      alignItems: "center",
      gap: 9,
      marginTop: 4,
    },

    noticeText: {
      flex: 1,
      color: "#8B651F",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "700",
    },

    publishSuccessBox: {
      width: "100%",
      backgroundColor: "#E8F3E5",
      borderRadius: 16,
      paddingHorizontal: 14,
      paddingVertical: 12,
      flexDirection: "row",
      alignItems: "center",
      gap: 9,
      marginTop: 14,
    },

    publishSuccessTextBox: {
      flex: 1,
      gap: 2,
    },

    publishSuccessTitle: {
      color: "#245C2D",
      fontSize: 13 * scale,
      fontWeight: "900",
    },

    publishSuccessText: {
      color: "#245C2D",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "700",
    },

    submitButton: {
      width: "76%",
      height: 52,
      borderRadius: 999,
      backgroundColor: "#D89B31",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      marginTop: 24,
    },

    submitButtonText: {
      color: "#FFFFFF",
      fontSize: 20 * scale,
      fontWeight: "600",
    },

    disabledButton: {
      opacity: 0.45,
    },

    editButton: {
      width: "76%",
      height: 48,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      marginTop: 10,
    },

    editButtonText: {
      color: "#333333",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    modalOverlay: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.35)",
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 24,
    },

    calendarModal: {
      width: "100%",
      maxWidth: 420,
      backgroundColor: "#FFF5E9",
      borderRadius: 24,
      padding: 20,
    },

    calendarHeader: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 18,
    },

    calendarArrow: {
      width: 40,
      height: 40,
      borderRadius: 20,
      backgroundColor: "#FFFFFF",
      alignItems: "center",
      justifyContent: "center",
    },

    calendarTitle: {
      color: "#245C2D",
      fontSize: 18 * scale,
      fontWeight: "900",
    },

    weekRow: {
      flexDirection: "row",
      marginBottom: 8,
    },

    weekText: {
      width: "14.2857%",
      textAlign: "center",
      color: "#777777",
      fontSize: 12 * scale,
      fontWeight: "800",
    },

    calendarGrid: {
      flexDirection: "row",
      flexWrap: "wrap",
    },

    calendarDay: {
      width: "14.2857%",
      aspectRatio: 1,
      alignItems: "center",
      justifyContent: "center",
      borderRadius: 999,
    },

    calendarDaySelected: {
      backgroundColor: "#D89B31",
    },

    calendarDayText: {
      color: "#333333",
      fontSize: 14 * scale,
      fontWeight: "700",
    },

    calendarDayTextSelected: {
      color: "#FFFFFF",
      fontWeight: "900",
    },

    timeModal: {
      width: "100%",
      maxWidth: 400,
      maxHeight: "75%",
      backgroundColor: "#FFF5E9",
      borderRadius: 24,
      padding: 20,
    },

    timeModalTitle: {
      color: "#245C2D",
      fontSize: 19 * scale,
      fontWeight: "900",
      textAlign: "center",
    },

    timeModalDate: {
      color: "#777777",
      fontSize: 13 * scale,
      fontWeight: "700",
      textAlign: "center",
      marginTop: 4,
      marginBottom: 16,
    },

    timeList: {
      maxHeight: 420,
    },

    timeOption: {
      minHeight: 50,
      borderRadius: 14,
      backgroundColor: "#FFFFFF",
      marginBottom: 8,
      paddingHorizontal: 16,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },

    timeOptionSelected: {
      backgroundColor: "#D89B31",
    },

    timeOptionText: {
      color: "#333333",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    timeOptionTextSelected: {
      color: "#FFFFFF",
    },

    modalCancel: {
      height: 46,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
      marginTop: 12,
    },

    modalCancelText: {
      color: "#333333",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    pressed: {
      opacity: 0.72,
      transform: [{ scale: 0.98 }],
    },
  });