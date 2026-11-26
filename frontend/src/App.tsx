import { useEffect, useState, type FormEvent } from "react";
import { api, type ChatRef, type Doc, type Msg } from "./api";

export function App() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [chats, setChats] = useState<ChatRef[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const guard = async (fn: () => Promise<void>) => {
    setError(""); setBusy(true);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const refresh = async () => { setDocs(await api.docs()); setChats(await api.chats()); };
  useEffect(() => { guard(refresh); }, []);

  const open = (id: number) => guard(async () => { setActive(id); setMsgs((await api.chat(id)).messages); });

  const ask = (e: FormEvent) => {
    e.preventDefault();
    const question = q.trim();
    if (!question) return;
    guard(async () => {
      let id = active;
      if (id === null) { id = (await api.newChat()).id; setActive(id); }
      setMsgs((m) => [...m, { role: "user", content: question, citations: [], mode: "" }]);
      setQ("");
      const r = await api.ask(id, question);
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, citations: r.citations, mode: r.mode }]);
      setChats(await api.chats());
    });
  };

  return (
    <div className="layout">
      <aside>
        <h1>Knowledge Assistant</h1>
        <p className="muted">Ask questions about your documents. Answers cite the document and page.</p>
        {docs.length === 0 && (
          <div className="banner">
            <strong>New here?</strong>
            <button onClick={() => guard(async () => { await api.seed(); await refresh(); })}>Load sample documents (demo)</button>
            <p className="muted">Loads a synthetic 11-page handbook (Python, Git, Docker, SQL...). Not real data.</p>
          </div>
        )}
        <h3>Documents</h3>
        <label className="upload">Upload PDF / DOCX / TXT
          <input type="file" aria-label="Upload document" accept=".pdf,.docx,.txt,.md"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) guard(async () => { await api.upload(f); await refresh(); }); e.target.value = ""; }} />
        </label>
        <ul>
          {docs.map((d) => (
            <li key={d.id}>{d.filename} <span className="muted">({d.pages}p, {d.chunks} chunks)</span>
              <button className="link" onClick={() => guard(async () => { await api.remove(d.id); await refresh(); })}>delete</button></li>
          ))}
        </ul>
        <h3>Saved chats</h3>
        <button onClick={() => { setActive(null); setMsgs([]); }}>+ New chat</button>
        <ul>
          {chats.map((c) => (
            <li key={c.id}><button className={"link" + (c.id === active ? " on" : "")} onClick={() => open(c.id)}>{c.title}</button></li>
          ))}
        </ul>
      </aside>
      <main>
        {error && <p role="alert" className="err">{error}</p>}
        <div className="thread">
          {msgs.length === 0 && <p className="muted">Ask something, for example: "What status code does FastAPI return when validation fails?"</p>}
          {msgs.map((m, i) => (
            <div key={i} className={"msg " + m.role}>
              <p>{m.content}</p>
              {m.citations.length > 0 && (
                <ol className="cites">
                  {m.citations.map((c, j) => <li key={j}><strong>{c.document}, page {c.page}</strong><div className="muted">{c.snippet}...</div></li>)}
                </ol>
              )}
              {m.mode && <div className="muted">answer mode: {m.mode}</div>}
            </div>
          ))}
          {busy && <p className="muted">working...</p>}
        </div>
        <form onSubmit={ask} className="askbar">
          <input aria-label="Question" placeholder="Ask about your documents" value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="submit" disabled={busy || docs.length === 0}>Ask</button>
        </form>
        {docs.length === 0 && <p className="muted">Upload a document or load the sample first.</p>}
      </main>
    </div>
  );
}
