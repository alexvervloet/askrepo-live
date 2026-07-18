// Client for the SSE wire protocol documented in the README. Uses fetch +
// ReadableStream because EventSource cannot POST a body.

export interface Source {
  path: string;
  start_line: number;
  end_line: number;
}

export interface Repo {
  name: string;
  github: string;
  branch: string;
}

export type AskEvent =
  | { type: "meta"; provider: string; repo: string }
  | { type: "sources"; sources: Source[] }
  | { type: "token"; text: string }
  | { type: "done"; elapsed_ms: number }
  | { type: "error"; message: string };

export async function fetchRepos(): Promise<Repo[]> {
  const res = await fetch("/api/repos");
  if (!res.ok) throw new Error(`GET /api/repos: ${res.status}`);
  return res.json();
}

export async function askStream(
  question: string,
  repo: string,
  onEvent: (e: AskEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, repo }),
    signal,
  });
  if (!res.ok || !res.body) {
    const raw = await res.text().catch(() => "");
    let detail = raw;
    try {
      detail = JSON.parse(raw).detail ?? raw;
    } catch {
      // not JSON; show the raw body
    }
    throw new Error(detail || `request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buf.indexOf("\n\n")) !== -1) {
      const frame = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      const event = parseFrame(frame);
      if (event) onEvent(event);
    }
  }
}

function parseFrame(frame: string): AskEvent | null {
  let type = "";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!type || dataLines.length === 0) return null;
  const data = JSON.parse(dataLines.join("\n"));
  // "sources" sends a bare array; wrap it so every event is an object
  if (type === "sources") return { type, sources: data };
  return { type, ...data } as AskEvent;
}
