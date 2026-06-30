const BASE_URL = "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
  const result = await chrome.storage.local.get("recallai_token");
  const token = result["recallai_token"] as string | undefined;
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

export async function fetchApi<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...init?.headers,
    },
    credentials: authHeaders["Authorization"] ? "omit" : "include",
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}
