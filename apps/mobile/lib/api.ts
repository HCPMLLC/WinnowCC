import { Platform } from "react-native";
import { getToken, removeToken } from "./auth";

export const API_BASE =
  Platform.OS === "web"
    ? (process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000")
    : process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1000;
const REQUEST_TIMEOUT_MS = 30000;

interface RequestOptions extends Omit<RequestInit, "headers"> {
  headers?: Record<string, string>;
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

export class FeatureGateError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FeatureGateError";
  }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Make an authenticated API request.
 * Automatically adds the Bearer token from secure storage.
 * Retries on network failures. Clears token on 401.
 */
export async function apiFetch(
  path: string,
  options: RequestOptions = {}
): Promise<Response> {
  const token = await getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Client-Platform": "mobile",
    ...options.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = `${API_BASE}${path}`;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.status === 401) {
        await removeToken();
        throw new AuthError("Session expired. Please log in again.");
      }

      return response;
    } catch (err: any) {
      clearTimeout(timeoutId);
      if (err instanceof AuthError) throw err;
      lastError = err;
      if (attempt < MAX_RETRIES) {
        await delay(RETRY_DELAY_MS * (attempt + 1));
      }
    }
  }

  throw lastError || new Error("Request failed after retries.");
}

/**
 * Upload a file via multipart/form-data (e.g. resume upload).
 * Do NOT set Content-Type — let the runtime set the multipart boundary.
 */
export async function uploadFile(
  path: string,
  fileUri: string,
  fileName: string,
  mimeType: string,
): Promise<Response> {
  const token = await getToken();

  const formData = new FormData();
  formData.append("file", {
    uri: fileUri,
    name: fileName,
    type: mimeType,
  } as any);

  const headers: Record<string, string> = {
    "X-Client-Platform": "mobile",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
  });

  if (response.status === 401) {
    await removeToken();
    throw new AuthError("Session expired. Please log in again.");
  }

  return response;
}

export const api = {
  get: (path: string) => apiFetch(path, { method: "GET" }),

  post: (path: string, body?: unknown) =>
    apiFetch(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: (path: string, body: unknown) =>
    apiFetch(path, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  patch: (path: string, body: unknown) =>
    apiFetch(path, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  delete: (path: string) => apiFetch(path, { method: "DELETE" }),
};
