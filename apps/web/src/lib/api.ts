import type { components } from "./generated";
export type Garment = components["schemas"]["GarmentOut"];
export type Category = Garment["category"];
export type GarmentStatus = Garment["status"];
export type Season = Garment["season"];
export type Session = components["schemas"]["SessionOut"];
export type Job = components["schemas"]["JobOut"];
export type CutoutModel = "birefnet-general-lite";
export const cutoutModel: CutoutModel = "birefnet-general-lite";
export const cutoutModelName = "BiRefNet Lite";

export function formatDuration(milliseconds: number) {
  return milliseconds < 1000
    ? `${milliseconds} 毫秒`
    : `${(milliseconds / 1000).toFixed(1)} 秒`;
}

let csrfToken = "";
export function setCsrf(token: string) {
  csrfToken = token;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (init.method && init.method !== "GET")
    headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail =
      typeof payload.detail === "string"
        ? payload.detail
        : "输入内容不符合要求，请检查后重试";
    if (
      response.status === 401 &&
      path !== "/auth/login" &&
      path !== "/auth/me"
    )
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(detail, response.status);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export const categories: Record<Category, string> = {
  top: "上装",
  bottom: "下装",
  outerwear: "外套",
  dress: "连衣裙",
  shoes: "鞋履",
  accessory: "配饰",
};
export const seasons: Record<Season, string> = {
  all: "四季",
  spring: "春季",
  summer: "夏季",
  autumn: "秋季",
  winter: "冬季",
};
export const statuses: Record<GarmentStatus, string> = {
  available: "可穿着",
  laundry: "待洗涤",
  archived: "已收纳",
};
export function updatePayload(item: Garment, changes: Partial<Garment> = {}) {
  const {
    name,
    category,
    color,
    season,
    material,
    care,
    notes,
    status,
    favorite,
  } = { ...item, ...changes };
  return {
    name,
    category,
    color,
    season,
    material,
    care,
    notes,
    status,
    favorite,
    expected_version: item.version,
  };
}
