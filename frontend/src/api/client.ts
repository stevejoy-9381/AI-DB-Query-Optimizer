/**
 * frontend/src/api/client.ts
 * Typed Axios client wrapping all FastAPI REST endpoints.
 */

import axios, { AxiosError } from "axios";
import type {
  AnalyzeResponse,
  ExecutionPlanResponse,
  HealthResponse,
  OptimizeResponse,
  RecommendationsResponse,
  RewriteResponse,
  SampleQueryItem,
  ScoreResponse,
  SimulateIndexResponse,
} from "./types";

// Default API URL from environment with localStorage persistence for QA switcher
const DEFAULT_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const STORAGE_KEY = "ai_db_api_base_url";

export function getBaseUrl(): string {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_URL;
}

export function setBaseUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY, url);
  apiClient.defaults.baseURL = url;
}

export const apiClient = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15000,
});

/**
 * Format any Axios error into a clear human-readable string.
 */
export function extractErrorMessage(err: unknown): { message: string; status?: number; detail?: any } {
  if (axios.isAxiosError(err)) {
    const axiosErr = err as AxiosError<{ error?: string; detail?: any }>;
    const status = axiosErr.response?.status;
    const data = axiosErr.response?.data;

    if (data?.error) {
      return { message: data.error, status, detail: data.detail };
    }
    if (typeof data?.detail === "string") {
      return { message: data.detail, status };
    }
    if (Array.isArray(data?.detail)) {
      const messages = data.detail.map((d: any) => `${d.loc?.join(".") || "field"}: ${d.msg}`).join("; ");
      return { message: messages || "Validation error", status, detail: data.detail };
    }
    if (axiosErr.message === "Network Error") {
      return {
        message: `Network Error: Unable to reach backend at ${apiClient.defaults.baseURL}. Is FastAPI running?`,
        status: 0,
      };
    }
    return { message: axiosErr.message || "Request failed", status };
  }
  return { message: (err as Error).message || "An unexpected error occurred" };
}

// ---------------------------------------------------------------------------
// Typed Endpoint Callers
// ---------------------------------------------------------------------------

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await apiClient.get<HealthResponse>("/api/health");
  return res.data;
}

export async function fetchSampleQueries(): Promise<SampleQueryItem[]> {
  const res = await apiClient.get<SampleQueryItem[]>("/api/sample-queries");
  return res.data;
}

export async function analyzeQuery(query: string): Promise<AnalyzeResponse> {
  const res = await apiClient.post<AnalyzeResponse>("/api/analyze", { query });
  return res.data;
}

export async function scoreQuery(query: string): Promise<ScoreResponse> {
  const res = await apiClient.post<ScoreResponse>("/api/score", { query });
  return res.data;
}

export async function optimizeQuery(query: string): Promise<OptimizeResponse> {
  const res = await apiClient.post<OptimizeResponse>("/api/optimize", { query });
  return res.data;
}

export async function getRecommendations(query: string): Promise<RecommendationsResponse> {
  const res = await apiClient.post<RecommendationsResponse>("/api/recommendations", { query });
  return res.data;
}

export async function rewriteQuery(query: string): Promise<RewriteResponse> {
  const res = await apiClient.post<RewriteResponse>("/api/rewrite", { query });
  return res.data;
}

export async function getExecutionPlan(query: string): Promise<ExecutionPlanResponse> {
  const res = await apiClient.post<ExecutionPlanResponse>("/api/execution-plan", { query });
  return res.data;
}

export async function simulateIndex(query: string, index: string): Promise<SimulateIndexResponse> {
  const res = await apiClient.post<SimulateIndexResponse>("/api/simulate-index", { query, index });
  return res.data;
}
