import { authStore } from "../lib/auth";
import type { Capture, Profile, RadarPoint, User } from "../types/api";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = authStore.getToken();
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init?.body && !(init.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  async login(email: string, password: string): Promise<string> {
    const body = JSON.stringify({ email, password });
    const res = await request<{ access_token: string }>("/v1/auth/login", {
      method: "POST",
      body,
    });
    return res.access_token;
  },

  async me(): Promise<User> {
    return request<User>("/v1/auth/me");
  },

  async listCaptures(userId: string, limit = 50): Promise<Capture[]> {
    return request<Capture[]>(`/v1/users/${userId}/captures?limit=${limit}`);
  },

  async getCapture(captureId: string): Promise<Capture> {
    return request<Capture>(`/v1/captures/${captureId}`);
  },

  async getProfile(userId: string): Promise<Profile> {
    return request<Profile>(`/v1/users/${userId}/profile`);
  },

  async getRadarHistory(userId: string, days = 30): Promise<RadarPoint[]> {
    return request<RadarPoint[]>(`/v1/users/${userId}/radar/history?days=${days}`);
  },

  mediaUrl(path: string): string {
    const token = authStore.getToken();
    const encoded = encodeURIComponent(path);
    return `${API_BASE}/v1/media?path=${encoded}${token ? `&token=${encodeURIComponent(token)}` : ""}`;
  },
};
