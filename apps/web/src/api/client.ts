function getBaseUrl(): string {
  return "";
}

export async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    credentials: "same-origin",
  });

  if (!response.ok) {
    if (response.status === 401) {
      window.location.href = "/auth/login";
      throw new Error("Not authenticated");
    }
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}

