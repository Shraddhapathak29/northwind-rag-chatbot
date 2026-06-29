"use client";

import { useRef, useState } from "react";
import {
  streamChat,
  type Citation,
  type SqlResult,
  type StreamEvent,
} from "@/lib/api";

type Msg = {
  role: "user" | "assistant";
  text: string;
  tools?: string[];
  citations?: Citation[];
  sql?: SqlResult;
  streaming?: boolean;
};

const TOOL_LABELS: Record<string, string> = {
  search_documents: "📄 Document RAG",
  query_orders: "🗄️ Text-to-SQL",
};

const SAMPLES = [
  "What is the refund window?",
  "How many orders are pending?",
  "What was total revenue last month?",
  "Our policy allows 30-day returns; did order ORD-1207 qualify?",
  "What's the capital of France?",
];

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollDown = () =>
    requestAnimationFrame(() =>
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
    );

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [
      ...m,
      { role: "user", text: q },
      { role: "assistant", text: "", streaming: true },
    ]);
    scrollDown();

    const patchLast = (patch: Partial<Msg>) =>
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = { ...last, ...patch };
        return copy;
      });

    try {
      for await (const ev of streamChat(q) as AsyncGenerator<StreamEvent>) {
        if (ev.type === "tools") patchLast({ tools: ev.tools });
        else if (ev.type === "citations") patchLast({ citations: ev.citations });
        else if (ev.type === "sql") patchLast({ sql: ev.sql });
        else if (ev.type === "token")
          setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, text: last.text + ev.text };
            return copy;
          });
        else if (ev.type === "error") patchLast({ text: `⚠️ ${ev.text}` });
        scrollDown();
      }
    } catch (e: any) {
      patchLast({ text: `⚠️ ${e?.message ?? "stream error"}` });
    } finally {
      patchLast({ streaming: false });
      setBusy(false);
    }
  }

  return (
    <div className="flex h-[100dvh] flex-col">
      <header className="border-b bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">Northwind Gadgets — Support Assistant</h1>
        <p className="text-sm text-slate-500">
          Agentic RAG · vector retrieval + text-to-SQL · routed automatically
        </p>
      </header>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-6 md:px-6">
        {messages.length === 0 && (
          <div className="mx-auto max-w-2xl">
            <p className="mb-3 text-sm text-slate-500">Try one of these:</p>
            <div className="flex flex-wrap gap-2">
              {SAMPLES.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border bg-white px-3 py-1.5 text-sm hover:bg-slate-100"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <Bubble key={i} m={m} />
        ))}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="border-t bg-white p-4"
      >
        <div className="mx-auto flex max-w-3xl gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about policies or orders…"
            className="flex-1 rounded-xl border px-4 py-2.5 outline-none focus:ring-2 focus:ring-slate-400"
          />
          <button
            disabled={busy}
            className="rounded-xl bg-slate-900 px-5 py-2.5 font-medium text-white disabled:opacity-50"
          >
            {busy ? "…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Bubble({ m }: { m: Msg }) {
  const isUser = m.role === "user";
  return (
    <div className={`mx-auto flex max-w-3xl ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser ? "bg-slate-900 text-white" : "border bg-white"
        }`}
      >
        {!isUser && (m.tools?.length ?? 0) > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {m.tools!.map((t) => (
              <span
                key={t}
                className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700"
              >
                {TOOL_LABELS[t] ?? t}
              </span>
            ))}
          </div>
        )}

        <div className="whitespace-pre-wrap text-[15px] leading-relaxed">
          {m.text}
          {m.streaming && <span className="ml-0.5 animate-pulse">▋</span>}
        </div>

        {!isUser && m.sql && <SqlBlock sql={m.sql} />}
        {!isUser && (m.citations?.length ?? 0) > 0 && <Citations cites={m.citations!} />}
      </div>
    </div>
  );
}

function SqlBlock({ sql }: { sql: SqlResult }) {
  return (
    <details className="mt-3 rounded-lg bg-slate-900 text-slate-100" open>
      <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-slate-300">
        Generated SQL {sql.error ? "(failed)" : `· ${sql.row_count} row(s)`}
      </summary>
      <pre className="overflow-x-auto px-3 pb-3 text-xs">
        <code>{sql.sql || "—"}</code>
      </pre>
      {sql.error ? (
        <p className="px-3 pb-3 text-xs text-rose-300">{sql.error}</p>
      ) : (
        sql.rows.length > 0 && (
          <div className="overflow-x-auto px-3 pb-3">
            <table className="text-xs">
              <thead>
                <tr>
                  {sql.columns.map((c) => (
                    <th key={c} className="px-2 py-1 text-left text-slate-400">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sql.rows.slice(0, 10).map((r, i) => (
                  <tr key={i} className="border-t border-slate-700">
                    {r.map((v, j) => (
                      <td key={j} className="px-2 py-1">
                        {String(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </details>
  );
}

function Citations({ cites }: { cites: Citation[] }) {
  return (
    <div className="mt-3 border-t pt-2">
      <p className="mb-1 text-xs font-medium text-slate-500">Citations</p>
      <ul className="space-y-1">
        {cites.map((c, i) => (
          <li key={i} className="text-xs text-slate-600">
            <span className="font-medium text-slate-800">{c.source}</span>
            <span className="text-slate-400"> · {c.section} · score {c.score}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
