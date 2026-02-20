import { getToken } from "./auth";

const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface RequestOptions extends Omit<RequestInit, "headers"> {
  headers?: Record<string, string>;
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

/**
 * Make an authenticated API request.
 * Automatically adds the Bearer token from secure storage.
 */
export async function apiFetch(
  path: string,
  options: RequestOptions = {}
): Promise<Response> {
  const token = await getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const url = `${API_BASE}${path}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    throw new AuthError("Session expired. Please log in again.");
  }

  return response;
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

  const headers: Record<string, string> = {};
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
