# HEANA Enhancement Pack

Bộ mã nguồn bổ sung để nâng cấp dự án **HCMUS Ăn Gì** thành đúng đặc tả **HEANA** (Hidden Eatery & Alley Navigation Assistant).

## Đã triển khai theo Spec

| Phần Spec | File | Mô tả |
|-----------|------|--------|
| 1.1 Onboarding Survey | `frontend/src/components/OnboardingSurvey.tsx` + API `/onboarding` | 4 câu hỏi → trọng số + allergies |
| 1.3 Input / Schema | `sql/heana_schema.sql`, `models/schemas.py` | places, dishes (ingredients), user_preferences, alley_nodes/edges |
| 1.4 Hard Filter | `services/ranking.py` → `hard_filter()` | Allergy ∩, Opening Hours, Dish + Price |
| 1.4 Soft Ranking | `services/ranking.py` → `compute_soft_scores()` | \(S = w_1 S_f + w_2 S_p + w_3 S_d + w_4 S_{fr}\) |
| 1.5 Directions 2 chặng | `services/alley_routing.py` + `AlleyDirections.tsx` | GPS → Entrance + Landmark Dijkstra |
| PAT-03 Fallback | `suggest_relaxation()` | Gợi ý nới lỏng khi 0 kết quả |
| Frontend ranking fallback | `frontend/src/lib/heana-ranking.ts` | Chạy offline / demo không cần backend |

## Cấu trúc

```
hcmus-heana/
├── sql/
│   └── heana_schema.sql          # Schema đầy đủ + seed mẫu
├── backend-python/
│   ├── models/schemas.py
│   ├── services/
│   │   ├── ranking.py            # Hard filter + Soft ranking
│   │   ├── alley_routing.py      # Graph + Dijkstra
│   │   └── search_service.py     # Orchestrator
│   └── routers/heana.py          # FastAPI router sẵn sàng include
└── frontend/src/
    ├── lib/
    │   ├── heana-types.ts
    │   └── heana-ranking.ts
    └── components/
        ├── OnboardingSurvey.tsx
        └── AlleyDirections.tsx
```

## Cách tích hợp vào project hiện tại

### 1. Database

```bash
mysql -u root -p hcmus_an_gi < sql/heana_schema.sql
```

Hoặc chạy từng lệnh trong file schema (có `CREATE TABLE IF NOT EXISTS` an toàn).

### 2. Backend

Copy các thư mục:

```bash
cp -r backend-python/models backend-python/services backend-python/routers \
  /path/to/hcmus-an-gi/backend-python/
```

Trong `app.py` hiện tại:

```python
from routers.heana import router as heana_router
app.include_router(heana_router, prefix="/api/heana")
```

Cài thêm nếu thiếu:

```bash
pip install python-jose[cryptography]  # đã có trong requirements gốc
```

### 3. Frontend

Copy:

```bash
cp frontend/src/lib/heana-*.ts src/lib/
cp frontend/src/components/OnboardingSurvey.tsx src/components/
cp frontend/src/components/AlleyDirections.tsx src/components/
```

**Gợi ý tích hợp nhanh:**

```tsx
// Sau khi signUp thành công
import { OnboardingSurvey } from "./components/OnboardingSurvey";
import { preferenceFromSurvey } from "./lib/heana-ranking";
import { DEFAULT_PREFERENCE } from "./lib/heana-types";

// State
const [pref, setPref] = useState(DEFAULT_PREFERENCE);
const [showSurvey, setShowSurvey] = useState(false);

// Khi user mới đăng ký
setShowSurvey(true);

// Render
{showSurvey && (
  <OnboardingSurvey
    onComplete={(p) => {
      setPref(p);
      localStorage.setItem("heana_pref", JSON.stringify(p));
      setShowSurvey(false);
      // Nếu có backend: POST /api/heana/onboarding
    }}
    onSkip={() => setShowSurvey(false)}
  />
)}
```

**Search với ranking mới (client-side):**

```ts
import { hardFilterAndRank } from "./lib/heana-ranking";

const results = hardFilterAndRank(rawPlacesWithDishes, pref, userLat, userLng, {
  requiredDish: "phở",
  maxPrice: 35000,
  maxRadiusM: 800,
  topK: 15,
});
```

**Directions:**

```tsx
import { AlleyDirections } from "./components/AlleyDirections";

// Sau khi gọi POST /api/heana/directions
{directions && <AlleyDirections data={directions} onClose={...} />}
```

## API Endpoints mới

| Method | Path | Mô tả |
|--------|------|--------|
| POST | `/api/heana/onboarding` | Gửi kết quả 4 câu survey |
| GET  | `/api/heana/preferences` | Lấy preference hiện tại |
| PUT  | `/api/heana/preferences` | Cập nhật trọng số / allergies |
| POST | `/api/heana/search` | Hard filter + Soft rank → Top 15 |
| POST | `/api/heana/directions` | 2-stage route (OSRM + Alley graph) |

## Lưu ý quan trọng

1. **Allergy là Hard Constraint tuyệt đối** – không bao giờ đề xuất món chứa thành phần dị ứng.
2. **Alley data** hiện chỉ seed mẫu cho 1 quán (Cơm tấm Mười). Cần bổ sung node/edge cho các quán khác.
3. Frontend ranking (`heana-ranking.ts`) dùng được ngay với localStorage, không bắt buộc backend.
4. Khi có backend thật, nên ưu tiên gọi API `/search` và `/directions` thay vì tính client-side.

## Tiếp theo (nên làm)

- [ ] Bổ sung dữ liệu alley_nodes / alley_edges cho nhiều quán hơn
- [ ] Kết nối Gemini extractor với field `required_dish` + `mentioned_allergies`
- [ ] Thêm Safety Guardrails (chặn prompt injection) ở endpoint chat
- [ ] UI hiển thị breakdown điểm số (S_feedback, S_price...) để giải thích ranking
- [ ] Constraint Relaxation UI khi search trả về 0 kết quả

---

Team HADAS · HEANA Enhancement Pack  
Tương thích với codebase HCMUS Ăn Gì hiện tại.