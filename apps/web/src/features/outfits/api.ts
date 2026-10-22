import type { components } from "../../lib/generated";

export type Location = components["schemas"]["Location"];
export type Preferences = components["schemas"]["RecommendationPreferences"];
export type Feedback = components["schemas"]["OutfitFeedback"];
export type Outfit = components["schemas"]["OutfitOut"];
export type Run = components["schemas"]["RecommendationRunOut"];

export const occasions = { casual: "休闲", work: "通勤", sport: "运动" };
export const exposures = {
  commute: "短时通勤",
  outdoor: "主要在户外",
  indoor: "主要在室内",
};
export const thermalPreferences = {
  cold: "比较怕冷",
  neutral: "适中",
  warm: "比较怕热",
};
export const weatherSources = {
  live: "实时预报",
  cache: "缓存预报",
  stale: "过期预报",
  manual: "手动天气",
};

export function localDate(timezone?: string) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone || "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
