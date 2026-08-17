import type {
  ApiError,
  LlmStatusResponse,
  TextVerifyRequest,
  VerifyResponse,
} from "@/types/verify";
import type { CommunityReport } from "@/types/admin";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "https://verifin.pempekasliwongkito.my.id";

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

export async function verifyUrl(url: string): Promise<VerifyResponse> {
  const res = await fetch(`${API_BASE}/api/v1/verify/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  return res.json() as Promise<VerifyResponse>;
}

// ── SSE Streaming untuk real-time progress ──────────────────────────────
// Event types yang dikirim backend:
//   "start"  → { request_id, message }
//   "stage"  → { stage: "fetch"|"ocr"|"ner"|"osint"|"graph"|"ai", status: "processing"|"done", message }
//   "done"   → { case_id, verdict, risk_score, response: VerifyResponse }
//   "error"  → { message }

export type SSEEvent =
  | { event: "start"; data: { request_id: string; message: string } }
  | { event: "stage"; data: { stage: string; status: "processing" | "done"; message: string; entities?: Record<string, unknown> } }
  | { event: "done"; data: { message: string; case_id: string; verdict: string; risk_score: number; response: VerifyResponse } }
  | { event: "error"; data: { message: string } };

/**
 * Verify URL dengan SSE streaming.
 * Memakai fetch + ReadableStream (bukan EventSource) karena endpoint butuh POST body.
 *
 * @param url URL lowongan kerja
 * @param onEvent Callback dipanggil untuk setiap SSE event
 * @param signal AbortSignal untuk cancel
 */
export async function verifyUrlStream(
  url: string,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/verify/url/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ url }),
    signal,
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("Browser tidak mendukung streaming response.");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events dari buffer (dipisah oleh \n\n)
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || ""; // sisain bagian yang belum complete

      for (const part of parts) {
        const lines = part.trim().split("\n");
        let event = "message";
        let data = "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            event = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            data = line.slice(6);
          }
        }

        if (!data) continue;

        try {
          const parsed = JSON.parse(data);
          onEvent({ event, data: parsed } as SSEEvent);
        } catch {
          // skip invalid JSON
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function getCaseById(caseId: string): Promise<VerifyResponse> {
  const res = await fetch(`${API_BASE}/api/v1/cases/${encodeURIComponent(caseId)}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseError(res));
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

export async function submitCommunityReport(payload: {
  company_name?: string;
  phone?: string;
  email?: string;
  url?: string;
  report_type: string;
  description?: string;
  reporter_contact?: string;
  case_id?: string;
  evidence_file?: File | null;
}): Promise<{ status: string; message: string; id: string }> {
  const form = new FormData();
  if (payload.company_name) form.append("company_name", payload.company_name);
  if (payload.phone) form.append("phone", payload.phone);
  if (payload.email) form.append("email", payload.email);
  if (payload.url) form.append("url", payload.url);
  form.append("report_type", payload.report_type);
  if (payload.description) form.append("description", payload.description);
  if (payload.reporter_contact) form.append("reporter_contact", payload.reporter_contact);
  if (payload.case_id) form.append("case_id", payload.case_id);
  if (payload.evidence_file) form.append("evidence_file", payload.evidence_file);

  const res = await fetch(`${API_BASE}/api/v1/community/report`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchCommunityReports(
  status?: "pending" | "approved" | "rejected",
  limit = 50,
): Promise<CommunityReport[]> {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (status) qs.set("status", status);
  const res = await fetch(`${API_BASE}/api/v1/community/reports?${qs}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as { reports?: CommunityReport[] };
  return data.reports ?? [];
}

export async function reviewCommunityReport(
  id: string,
  status: "pending" | "approved" | "rejected",
  reviewer_note?: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/community/reports/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, reviewer_note: reviewer_note ?? null }),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export { API_BASE };
