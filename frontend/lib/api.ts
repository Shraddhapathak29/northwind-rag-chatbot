// SSE client for the FastAPI /chat/stream endpoint.
// The endpoint is POST (so EventSource can't be used); we read the response
// body as a stream and parse "data:" lines ourselves.

export type Citation = {
  source: string;
  section: string;
  snippet: string;
  score: number;
};

export type SqlResult = {
  sql: string;
  columns: string[];
  rows: (string | number | null)[][];
  row_count: number;
  error?: string | null;
};

export type StreamEvent =
  | { type: "tools"; tools: string[] }
  | { type: "citations"; citations: Citation[] }
  | { type: "sql"; sql: SqlResult }
  | { type: "token"; text: string }
  | { type: "done" }
  | { type: "error"; text: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export async function* streamChat(
  message: string,
  signal?: AbortSignal
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line.
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const dataLine = frame
        .split("\n")
        .find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const json = dataLine.slice(5).trim();
      if (!json) continue;
      try {
        yield JSON.parse(json) as StreamEvent;
      } catch {
        // ignore malformed keep-alive lines
      }
    }
  }
}
