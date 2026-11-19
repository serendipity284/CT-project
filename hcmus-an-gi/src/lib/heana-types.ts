/** HEANA Frontend Types - đồng bộ với backend schemas */

export type CampusId = "q5" | "lang";

export interface UserPreference {
  w_price: number;
  w_distance: number;
  w_quality: number;
  w_freshness: number;
  allergies: string[];
  survey_done?: boolean;
}

export interface Dish {
  dish_id: number;
  dish_name: string;
  price: number;
  ingredients: string[];
}

export interface PlaceResult {
  place_id: number;
  name: string;
  campus: CampusId;
  address: string;
  lat: number;
  lng: number;
  alley_entrance_lat?: number | null;
  alley_entrance_lng?: number | null;
  hours_text: string;
  price_min: number;
  price_max: number;
  cuisine: string;
  rating_avg: number;
  rating_count: number;
  distance_m: number;
  score: number;
  matched_dishes: Dish[];
  image_url?: string | null;
  s_feedback: number;
  s_price: number;
  s_distance: number;
  s_freshness: number;
}

export interface RouteStep {
  node_id: number;
  node_name: string;
  instruction: string;
  distance_m: number;
  lat: number;
  lng: number;
  image_url?: string | null;
  node_type: "entrance" | "landmark" | "eatery";
}

export interface DirectionsResult {
  place_id: number;
  place_name: string;
  stage1_distance_m: number;
  stage1_duration_sec: number;
  stage1_polyline: [number, number][]; // [lng, lat]
  stage2: RouteStep[];
  stage2_total_m: number;
  has_alley_data: boolean;
  message: string;
}

export interface OnboardingAnswers {
  price_importance: number; // 1-5
  distance_importance: number;
  quality_importance: number;
  allergies_text: string;
}

export const DEFAULT_PREFERENCE: UserPreference = {
  w_price: 0.3,
  w_distance: 0.3,
  w_quality: 0.3,
  w_freshness: 0.1,
  allergies: [],
  survey_done: false,
};
export interface DishPreview {
  name: string;
  price: number;
}

// Bổ sung các trường tùy chọn (nếu chưa có) vào type Place / Eatery hiện tại của bạn:
export interface Place {
  id: number | string;
  name: string;
  address?: string;
  price_min?: number;
  price_max?: number;
  distance_m?: number;
  // Các trường sẽ bổ sung dữ liệu sau (dùng dấu ? để không lỗi khi DB thiếu)
  rating?: number | null;
  image_url?: string | null;
  dishes?: DishPreview[];
}
export type SurveyFactor = "price" | "distance" | "quality";
export type SurveyChoice = SurveyFactor | "any";
export interface SurveyAnswers {
  q1: SurveyChoice;
  q2?: SurveyChoice | null;
  allergies_text: string;
}