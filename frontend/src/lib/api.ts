import type {
  ApiError,
  LlmStatusResponse,
  TextVerifyRequest,
  VerifyResponse,
} from "@/types/verify";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as ApiError | { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: string }).msg);
          }
          return JSON.stringify(item);
        })
        .join("; ");
    }
    return `Request gagal (${res.status})`;
  } catch {
    return `Request gagal (${res.status})`;
  }
}

export async function verifyText(
  payload: TextVerifyRequest,
): Promise<VerifyResponse> {
  const res = await fetch(`${API_BASE}/api/v1/verify/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: payload.text,
      include_raw_text: payload.include_raw_text ?? true,
    }),
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  return res.json() as Promise<VerifyResponse>;
}

export async function verifyImage(file: File): Promise<VerifyResponse> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/api/v1/verify/image`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  return res.json() as Promise<VerifyResponse>;
}

export async function getAiStatus(): Promise<LlmStatusResponse> {
  const res = await fetch(`${API_BASE}/api/v1/verify/status`, {
    method: "GET",
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  return res.json() as Promise<LlmStatusResponse>;
}

export { API_BASE };
