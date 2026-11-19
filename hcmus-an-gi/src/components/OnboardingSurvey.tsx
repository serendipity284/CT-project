import { useState } from "react";
import type { SurveyAnswers, SurveyChoice, SurveyFactor } from "../lib/heana-types";
import { FACTOR_LABEL } from "../lib/heana-ranking";

type Props = {
  onComplete: (a: SurveyAnswers) => Promise<void> | void;
  onClose?: () => void;
};

type Step = "q1" | "q2" | "q3" | "done";
const ALL: SurveyFactor[] = ["price", "distance", "quality"];

export function OnboardingSurvey({ onComplete, onClose }: Props) {
  const [step, setStep] = useState<Step>("q1");
  const [q1, setQ1] = useState<SurveyChoice>("any");
  const [q2, setQ2] = useState<SurveyChoice | null>(null);
  const [allergies, setAllergies] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const others = ALL.filter((f) => f !== q1);

  function pickQ1(c: SurveyChoice) {
    setQ1(c);
    setQ2(null);
    setStep(c === "any" ? "q3" : "q2"); // D -> bỏ qua Q2
  }

  async function finish() {
    setBusy(true);
    setError("");
    try {
      await onComplete({ q1, q2: q1 === "any" ? null : q2 ?? "any", allergies_text: allergies });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không lưu được khảo sát");
      setBusy(false);
    }
  }

  return (
    <div className="sv-overlay" role="dialog" aria-modal="true">
      <div className="sv-card">
        {step === "q1" && (
          <>
            <p className="sv-intro">
              Chào bạn mới! Trước khi chúng ta bắt đầu việc lựa chọn quán, bạn hãy thực hiện bài
              khảo sát này để giúp mình tìm quán phù hợp với bạn nhất! (Bạn có thể thực hiện lại
              bất kỳ lúc nào bạn muốn)
            </p>
            <h3>Câu 1: Bạn muốn kết quả tìm kiếm ưu tiên yếu tố nào nhất?</h3>
            {ALL.map((f) => (
              <button key={f} type="button" className="sv-opt" onClick={() => pickQ1(f)}>
                {FACTOR_LABEL[f]}
              </button>
            ))}
            <button type="button" className="sv-opt" onClick={() => pickQ1("any")}>
              Sao cũng được
            </button>
          </>
        )}

        {step === "q2" && (
          <>
            <h3>Câu 2: Hãy chọn yếu tố phụ để mình đưa ra lựa chọn tốt hơn cho bạn</h3>
            {others.map((f) => (
              <button key={f} type="button" className="sv-opt"
                onClick={() => { setQ2(f); setStep("q3"); }}>
                {FACTOR_LABEL[f]}
              </button>
            ))}
            <button type="button" className="sv-opt" onClick={() => { setQ2("any"); setStep("q3"); }}>
              Sao cũng được
            </button>
            <button type="button" className="sv-link" onClick={() => setStep("q1")}>← Quay lại</button>
          </>
        )}

        {step === "q3" && (
          <>
            <h3>
              Câu 3: Cảm ơn bạn! Bạn có thành phần nào khiến bạn dị ứng hoặc khó chịu khi ăn không?
            </h3>
            <textarea className="field" rows={3} value={allergies}
              placeholder="Ví dụ: lạc, hải sản, hành (cách nhau bằng dấu phẩy, để trống nếu không có)"
              onChange={(e) => setAllergies(e.target.value)} />
            <div className="row">
              <button type="button" className="chip"
                onClick={() => setStep(q1 === "any" ? "q1" : "q2")}>← Quay lại</button>
              <button type="button" className="btn-primary grow" onClick={() => setStep("done")}>
                Tiếp tục
              </button>
            </div>
          </>
        )}

        {step === "done" && (
          <>
            <h3>Vậy là chúng ta đã sẵn sàng bắt đầu rồi!</h3>
            <p className="muted">
              Bạn có thể làm lại bài khảo sát để thay đổi cách mình tìm kiếm, hoặc nói thẳng với
              mình trong đoạn chat nhé.
            </p>
            {error && <p className="error">{error}</p>}
            <button type="button" className="btn-primary" disabled={busy} onClick={() => void finish()}>
              {busy ? "Đang lưu…" : "Bắt đầu"}
            </button>
          </>
        )}

        {onClose && step !== "done" && (
          <button type="button" className="sv-link" onClick={onClose}>Bỏ qua lúc này</button>
        )}
      </div>
    </div>
  );
}