/**
 * HEANA 2-Stage Directions UI
 * Stage 1: GPS route to alley entrance
 * Stage 2: Landmark step-by-step inside the alley
 */

import type { DirectionsResult, RouteStep } from "../lib/heana-types";

interface Props {
  data: DirectionsResult;
  onClose?: () => void;
}

function StageBadge({ n, label }: { n: number; label: string }) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-orange-500 text-xs font-bold text-white">
        {n}
      </span>
      <span className="text-sm font-semibold text-gray-800">{label}</span>
    </div>
  );
}

function StepCard({ step, index }: { step: RouteStep; index: number }) {
  return (
    <div className="flex gap-3 rounded-xl border border-gray-100 bg-white p-3 shadow-sm">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-bold text-gray-600">
        {index}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-gray-900">{step.node_name}</p>
          {step.distance_m > 0 && (
            <span className="shrink-0 text-xs text-gray-400">{Math.round(step.distance_m)}m</span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-gray-600">{step.instruction}</p>
        {step.image_url && (
          <img
            src={step.image_url}
            alt={step.node_name}
            className="mt-2 h-24 w-full rounded-lg object-cover"
          />
        )}
        <span className="mt-1 inline-block rounded bg-gray-50 px-1.5 py-0.5 text-[10px] uppercase text-gray-400">
          {step.node_type}
        </span>
      </div>
    </div>
  );
}

export function AlleyDirections({ data, onClose }: Props) {
  const walkMin1 = Math.max(1, Math.round(data.stage1_duration_sec / 60));
  const walkMin2 = Math.max(1, Math.round(data.stage2_total_m / 75));

  return (
    <div className="flex h-full flex-col bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between border-b bg-white px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Chỉ đường</h2>
          <p className="text-xs text-gray-500">{data.place_name}</p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100"
          >
            Đóng
          </button>
        )}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        {/* Stage 1 */}
        <section>
          <StageBadge n={1} label="Đường chính → Cổng hẻm" />
          <div className="rounded-xl border border-orange-100 bg-orange-50/50 p-3">
            <p className="text-sm text-gray-700">
              Đi bộ khoảng <strong>{Math.round(data.stage1_distance_m)}m</strong> (
              ~{walkMin1} phút) đến cổng hẻm.
            </p>
            {data.stage1_polyline.length === 0 && (
              <p className="mt-1 text-xs text-amber-600">
                Không lấy được polyline GPS. Hãy dùng bản đồ để đi đến vị trí cổng hẻm.
              </p>
            )}
          </div>
        </section>

        {/* Stage 2 */}
        <section>
          <StageBadge n={2} label="Trong hẻm – Từng bước theo điểm mốc" />
          {data.has_alley_data && data.stage2.length > 0 ? (
            <>
              <p className="mb-3 text-xs text-gray-500">
                Tổng đoạn trong hẻm: ~{Math.round(data.stage2_total_m)}m ({walkMin2} phút)
              </p>
              <div className="space-y-2">
                {data.stage2.map((step, i) => (
                  <StepCard key={step.node_id} step={step} index={i} />
                ))}
              </div>
            </>
          ) : (
            <div className="rounded-xl border border-dashed border-gray-200 bg-white p-4 text-center text-sm text-gray-500">
              {data.message || "Quán chưa có dữ liệu dẫn đường chi tiết trong hẻm."}
            </div>
          )}
        </section>

        {data.message && data.has_alley_data && (
          <p className="text-center text-xs text-gray-400">{data.message}</p>
        )}
      </div>
    </div>
  );
}