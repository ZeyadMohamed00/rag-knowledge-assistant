import { authHeaders, getToken, logout } from "./auth";
export const API_BASE: string = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "/api" : "");

export function clientId(): string {
  let id = localStorage.getItem("rag_client_id");
  if (!id) {
    id = (crypto.randomUUID?.() ?? String(Date.now()) + Math.random().toString(16).slice(2)).replace(/[^a-zA-Z0-9-]/g, "");
    localStorage.setItem("rag_client_id", id);
  }
  return id;
}

async function req<T>(path: string, method = "GET", body?: unknown, form?: FormData): Promise<T> {
  const headers: Record<string, string> = { "X-Client-Id": clientId() };
  if (body) headers["Content-Type"] = "application/json";
  Object.assign(headers, authHeaders());
  const res = await fetch(API_BASE + path, { method, headers, body: form ?? (body ? JSON.stringify(body) : undefined) });
  if (!res.ok) {
    if (res.status === 401 && getToken()) logout();
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* keep */ }
    throw new Error(msg);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export type Doc = { id: number; filename: string; pages: number; chunks: number };
export type Citation = { document: string; page: number; snippet: string };
export type Msg = { role: "user" | "assistant"; content: string; citations: Citation[]; mode: string };
export type Hit = { chunk_id: number; document: string; page: number; text: string; score: number };
export type ChatRef = { id: number; title: string };

export const api = {
  docs: () => req<Doc[]>("/documents"),
  upload: (f: File) => { const fd = new FormData(); fd.append("file", f); return req<Doc>("/documents", "POST", undefined, fd); },
  remove: (id: number) => req<void>(`/documents/${id}`, "DELETE"),
  search: (question: string, k = 6) => req<Hit[]>("/search", "POST", { question, k }),
  seed: () => req<{ seeded: boolean }>("/examples/handbook", "POST", {}),
  chats: () => req<ChatRef[]>("/chats"),
  newChat: () => req<ChatRef>("/chats", "POST", {}),
  chat: (id: number) => req<{ id: number; title: string; messages: Msg[] }>(`/chats/${id}`),
  ask: (id: number, question: string) => req<{ answer: string; citations: Citation[]; mode: string }>(`/chats/${id}/ask`, "POST", { question }),
};
