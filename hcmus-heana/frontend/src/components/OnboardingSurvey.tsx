/**
 * HEANA Onboarding Survey (Spec 1.1)
 * Hiển thị ngay sau lần đăng ký đầu tiên hoặc khi user chưa làm survey.
 */

import { useState } from "react";
import type { OnboardingAnswers, UserPreference } from "../lib/heana-types";
import { preferenceFromSurvey } from "../lib/heana-ranking";

interface Props {
  onComplete: (pref: UserPreference) => void;
  onSkip?: () => void;
}

const IMPORTANCE_LABELS = ["", "Không quan tâm", "Ít", "Trung bình", "Quan tâm", "Rất quan tâm"];

export function OnboardingSurvey({ onComplete, onSkip }: Props) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<OnboardingAnswers>({
    price_importance: 3,
    distance_importance: 3,
    quality_importance: 3,
    allergies_text: "",
  });

  const questions = [
    {
      key: "price_importance" as const,
      title: "Bạn quan tâm đến giá cả ở mức nào?",
      subtitle: "Ngân sách sinh viên thường < 35.000đ/bữa",
    },
    {
      key: "distance_importance" as const,
      title: "Bạn quan tâm đến khoảng cách ở mức nào?",
      subtitle: "Đi bộ gần hay chấp nhận đi xa hơn một chút?",
    },
    {
      key: "quality_importance" as const,
      title: "Bạn quan tâm đến chất lượng / rating ở mức nào?",
      subtitle: "Điểm đánh giá và review từ người khác",
    },
    {
      key: "allergies_text" as const,
      title: "Bạn có dị ứng thành phần nào không?",
      subtitle: 'Ví dụ: lạc, hải sản, hành tây, sữa... (để trống nếu không có)',
      isText: true,
    },
  ];

  const current = questions[step];
  const isLast = step === questions.length - 1;

  function handleNext() {
    if (isLast) {
      const pref = preferenceFromSurvey(answers);
      onComplete(pref);
    } else {
      setStep((s) => s + 1);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Thiết lập sở thích</h2>
          <span className="text-sm text-gray-500">
            {step + 1}/{questions.length}
          </span>
        </div>

        {/* Progress */}
        <div className="mb-6 h-1.5 overflow-hidden rounded-full bg-gray-100">
          <div
            className="h-full rounded-full bg-orange-500 transition-all"
            style={{ width: `${((step + 1) / questions.length) * 100}%` }}
          />
        </div>

        <h3 className="mb-1 text-base font-medium text-gray-800">{current.title}</h3>
        <p className="mb-5 text-sm text-gray-500">{current.subtitle}</p>

        {current.isText ? (
          <textarea
            className="mb-6 w-full rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:border-orange-400"
            rows={3}
            placeholder="lạc, hải sản, hành tây..."
            value={answers.allergies_text}
            onChange={(e) =>
              setAnswers((a) => ({ ...a, allergies_text: e.target.value }))
            }
          />
        ) : (
          <div className="mb-6 flex justify-between gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() =>
                  setAnswers((a) => ({ ...a, [current.key]: n }))
                }
                className={`flex h-12 w-12 flex-col items-center justify-center rounded-xl border text-sm font-medium transition ${
                  (answers as any)[current.key] === n
                    ? "border-orange-500 bg-orange-50 text-orange-600"
                    : "border-gray-200 text-gray-600 hover:border-gray-300"
                }`}
              >
                {n}
              </button>
            ))}
          </div>
        )}

        {!current.isText && (
          <p className="mb-4 text-center text-xs text-gray-400">
            {IMPORTANCE_LABELS[(answers as any)[current.key]]}
          </p>
        )}

        <div className="flex gap-3">
          {onSkip && step === 0 && (
            <button
              type="button"
              onClick={onSkip}
              className="flex-1 rounded-xl border border-gray-200 py-2.5 text-sm font-medium text-gray-600"
            >
              Bỏ qua
            </button>
          )}
          {step > 0 && (
            <button
              type="button"
              onClick={() => setStep((s) => s - 1)}
              className="flex-1 rounded-xl border border-gray-200 py-2.5 text-sm font-medium text-gray-600"
            >
              Quay lại
            </button>
          )}
          <button
            type="button"
            onClick={handleNext}
            className="flex-1 rounded-xl bg-orange-500 py-2.5 text-sm font-medium text-white hover:bg-orange-600"
          >
            {isLast ? "Hoàn tất" : "Tiếp tục"}
          </button>
        </div>
      </div>
    </div>
  );
}