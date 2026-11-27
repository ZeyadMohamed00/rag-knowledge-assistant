import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, type ChatRef, type Citation, type Doc, type Hit, type Msg } from "./api";
import { Badge, BarChart, Empty, Modal, Shell, Skeleton, Stat, ToastProvider, useToast } from "./ui";
import results from "./data/results.json";
import questions from "./data/questions.json";

type Page = "chat" | "docs" | "search" | "eval" | "about";
const SUGGESTIONS = ["What status code does FastAPI return when validation fails?", "Why can't Python threads speed up CPU-heavy code?", "How do I isolate project dependencies?", "What does HTTP 403 mean versus 401?"];

export function App() { return <ToastProvider><Main /></ToastProvider>; }

function Main() {
  const toast = useToast();
  const [page, setPage] = useState<Page>("chat");
  const [docs, setDocs] = useState<Doc[]>([]);
  const [chats, setChats] = useState<ChatRef[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [cite, setCite] = useState<Citation | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const guard = useCallback(async (fn: () => Promise<void>) => {
    setError(""); setBusy(true);
    try { await fn(); } catch (e) { setError((e as Error).message); toast((e as Error).message, "bad"); } finally { setBusy(false); }
  }, [toast]);
  const refresh = useCallback(async () => { setDocs(await api.docs()); setChats(await api.chats()); setLoaded(true); }, []);
  useEffect(() => { guard(refresh); }, [guard, refresh]);
  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: "smooth" }); }, [msgs, busy]);

  const open = (id: number) => guard(async () => { setActive(id); setMsgs((await api.chat(id)).messages); setPage("chat"); });
  const ask = (question: string) => {
    question = question.trim(); if (!question) return;
    guard(async () => {
      let id = active;
      if (id === null) { id = (await api.newChat()).id; setActive(id); }
      setMsgs((m) => [...m, { role: "user", content: question, citations: [], mode: "" }]); setQ("");
      const r = await api.ask(id, question);
      setMsgs((m) => [...m, { role: "assistant", content: r.answer, citations: r.citations, mode: r.mode }]);
      setChats(await api.chats());
    });
  };
  const submit = (e: FormEvent) => { e.preventDefault(); ask(q); };
  const upload = (f: File) => guard(async () => { await api.upload(f); await refresh(); toast(`Uploaded ${f.name}`, "ok"); });
  const seed = () => guard(async () => { await api.seed(); await refresh(); toast("Example handbook loaded", "ok"); });
  const chunks = docs.reduce((a, d) => a + d.chunks, 0);

  return (
    <Shell brand="Knowledge Assistant" tagline="RAG with citations" page={page} onNav={(p) => setPage(p as Page)}
      nav={[{ id: "chat", label: "Chat", icon: "✎" }, { id: "docs", label: "Documents", icon: "▤", badge: docs.length }, { id: "search", label: "Retrieval explorer", icon: "⌕" }, { id: "eval", label: "Evaluation", icon: "✓" }, { id: "about", label: "How it works", icon: "?" }]}
      footer={<div className="col" style={{ padding: 8 }}>
        <small style={{ padding: 0 }}>Saved chats</small>
        {chats.length === 0 && <span className="muted small">No chats yet</span>}
        {chats.slice(0, 6).map((c) => <button key={c.id} className={`nav ${c.id === active && page === "chat" ? "on" : ""}`} style={{ padding: "6px 8px", fontSize: 13 }} onClick={() => open(c.id)}><span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.title}</span></button>)}
      </div>}
      actions={page === "chat" ? <button className="btn sm" onClick={() => { setActive(null); setMsgs([]); }}>+ New chat</button> : undefined}>
      {error && <p role="alert" className="err">{error}</p>}

      {page === "chat" && (
        <>
          {!loaded ? <Skeleton /> : docs.length === 0 && (
            <div className="card row"><div><h3 style={{ margin: 0 }}>New here?</h3><p className="muted">Load the included 11-page engineering handbook (Python, Git, Docker, SQL...) or upload your own PDF, DOCX or TXT.</p></div>
              <button className="btn primary sp" onClick={seed} disabled={busy}>Load the example handbook</button></div>
          )}
          <div className="chat" aria-live="polite">
            {msgs.length === 0 && loaded && (
              <div className="card"><Empty icon="✎" title="Ask your documents anything" hint="Answers cite the document and page they came from.">
                <div className="row" style={{ justifyContent: "center", marginTop: 12 }}>{SUGGESTIONS.map((s) => <button key={s} className="chip" disabled={docs.length === 0} onClick={() => ask(s)}>{s}</button>)}</div></Empty></div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div>{m.content}</div>
                {m.citations.length > 0 && <div style={{ marginTop: 10 }}><b className="small muted">SOURCES</b>{m.citations.map((c, j) => (
                  <button key={j} className="cite" onClick={() => setCite(c)}><b>{c.document}, page {c.page}</b><div className="sn">{c.snippet}...</div></button>))}</div>}
                {m.role === "assistant" && <div className="row small muted" style={{ marginTop: 8 }}>{m.mode && <Badge>mode: {m.mode}</Badge>}<button className="btn ghost sm" onClick={() => { navigator.clipboard?.writeText(m.content); toast("Copied"); }}>Copy</button></div>}
              </div>
            ))}
            {busy && msgs.length > 0 && <div className="msg assistant dots" aria-label="Thinking"><span /><span /><span /></div>}
            <div ref={endRef} />
          </div>
          <form onSubmit={submit} className="askbar">
            <input aria-label="Question" placeholder={docs.length ? "Ask about your documents" : "Load or upload a document first"} value={q} onChange={(e) => setQ(e.target.value)} />
            <button className="btn primary" type="submit" disabled={busy || docs.length === 0 || !q.trim()}>Ask</button>
          </form>
        </>
      )}

      {page === "docs" && <DocsPage docs={docs} chunks={chunks} busy={busy} onUpload={upload} onSeed={seed} onDelete={(d) => guard(async () => { await api.remove(d.id); await refresh(); toast("Deleted"); })} />}
      {page === "search" && <SearchPage hasDocs={docs.length > 0} />}
      {page === "eval" && <EvalPage />}
      {page === "about" && <About />}
      {cite && <Modal title={`${cite.document}, page ${cite.page}`} onClose={() => setCite(null)}><p style={{ whiteSpace: "pre-wrap" }}>{cite.snippet}...</p><p className="muted small" style={{ marginTop: 10 }}>This is the retrieved passage the answer was built from.</p></Modal>}
    </Shell>
  );
}

function DocsPage({ docs, chunks, busy, onUpload, onSeed, onDelete }: { docs: Doc[]; chunks: number; busy: boolean; onUpload: (f: File) => void; onSeed: () => void; onDelete: (d: Doc) => void }) {
  const [over, setOver] = useState(false); const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <div className="page-h"><div><h1>Documents</h1><p>Your private library. Visitors see only their own files (10 documents, 4 MB each).</p></div></div>
      <div className="grid g3"><Stat label="Documents" value={docs.length} /><Stat label="Pages" value={docs.reduce((a, d) => a + d.pages, 0)} /><Stat label="Searchable chunks" value={chunks} /></div>
      <div className={`drop ${over ? "over" : ""}`} onClick={() => input.current?.click()} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) onUpload(f); }}>
        <b>Drop a PDF, DOCX or TXT here, or click to upload</b>
        <input ref={input} type="file" aria-label="Upload document" hidden accept=".pdf,.docx,.txt,.md" onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
      </div>
      <div className="card tw">
        {docs.length === 0 ? <Empty icon="▤" title="No documents yet" hint="Upload a file or load the example handbook."><button className="btn primary" style={{ marginTop: 10 }} onClick={onSeed} disabled={busy}>Load the example handbook</button></Empty> : (
          <table className="t"><thead><tr><th>File</th><th>Pages</th><th>Chunks</th><th /></tr></thead><tbody>
            {docs.map((d) => <tr key={d.id}><td><b>{d.filename}</b></td><td>{d.pages}</td><td>{d.chunks}</td><td><button className="btn sm danger" onClick={() => onDelete(d)}>Delete</button></td></tr>)}</tbody></table>
        )}
      </div>
    </>
  );
}

function SearchPage({ hasDocs }: { hasDocs: boolean }) {
  const [q, setQ] = useState(""); const [hits, setHits] = useState<Hit[] | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const run = async (e: FormEvent) => { e.preventDefault(); if (!q.trim()) return; setBusy(true); setErr(""); try { setHits(await api.search(q.trim())); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); } };
  const terms = q.toLowerCase().split(/\W+/).filter((w) => w.length > 3);
  const mark = (t: string) => t.split(new RegExp(`(${terms.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") || "$^"})`, "gi")).map((p, i) => (terms.includes(p.toLowerCase()) ? <mark key={i}>{p}</mark> : p));
  return (
    <>
      <div className="page-h"><div><h1>Retrieval explorer</h1><p>See exactly which chunks the vector search returns, with cosine similarity scores, before any answer is written.</p></div></div>
      <form className="row" onSubmit={run}><input style={{ flex: 1 }} aria-label="Search query" placeholder="Try: how do I isolate dependencies" value={q} onChange={(e) => setQ(e.target.value)} /><button className="btn primary" disabled={busy || !hasDocs}>Search</button></form>
      {!hasDocs && <p className="muted">Load a document first.</p>}{err && <p className="err" role="alert">{err}</p>}
      {hits && <div className="col">{hits.length === 0 && <Empty title="No chunks returned" />}{hits.map((h, i) => (
        <div key={h.chunk_id} className="hit"><div className="row"><Badge kind="acc">#{i + 1}</Badge><b>{h.document}, page {h.page}</b><span className="sp"><Badge kind={h.score > 0.5 ? "ok" : h.score > 0.25 ? "warn" : ""}>score {h.score.toFixed(3)}</Badge></span></div><p style={{ marginTop: 8 }}>{mark(h.text)}</p></div>))}</div>}
    </>
  );
}

function EvalPage() {
  const r = results as { questions: number; "recall@1": number; "recall@3": number; "recall@5": number; mrr: number; faithfulness_proxy: number; embedder: string; answerer: string; missed_at_5: string[] };
  const pct = (v: number) => `${Math.round(v * 1000) / 10}%`;
  return (
    <>
      <div className="page-h"><div><h1>Evaluation</h1><p>{r.questions} reference questions, run offline against the included handbook ({r.embedder}, {r.answerer} answerer).</p></div></div>
      <div className="grid g4"><Stat label="Recall@1" value={pct(r["recall@1"])} /><Stat label="Recall@3" value={pct(r["recall@3"])} /><Stat label="Recall@5" value={pct(r["recall@5"])} /><Stat label="MRR" value={r.mrr.toFixed(3)} /></div>
      <div className="grid g2">
        <div className="card"><h3>Retrieval recall by k</h3><BarChart max={1} data={[{ label: "@1", value: r["recall@1"] }, { label: "@3", value: r["recall@3"] }, { label: "@5", value: r["recall@5"] }]} /><div className="row small muted" style={{ justifyContent: "space-around" }}><span>k=1</span><span>k=3</span><span>k=5</span></div></div>
        <div className="card col"><h3>Honest caveats</h3><p className="small">The questions were written by the project author from the same documents, so this is not an independent benchmark.</p><p className="small">Faithfulness ({pct(r.faithfulness_proxy)}) is a lexical proxy, not an LLM judge. An extractive answerer scores high on it by construction.</p>{r.missed_at_5.length > 0 && <p className="small">Missed at k=5: <i>{r.missed_at_5.join("; ")}</i> (a paraphrase, the expected weakness of lexical embeddings).</p>}</div>
      </div>
      <div className="card tw"><h3>The {questions.length} reference questions</h3><table className="t"><thead><tr><th>Question</th><th>Expected source</th></tr></thead><tbody>{(questions as { q: string; doc: string }[]).map((x) => <tr key={x.q}><td>{x.q}</td><td><Badge>{x.doc}</Badge></td></tr>)}</tbody></table></div>
    </>
  );
}

function About() {
  const steps = [["1. Ingest", "Extract text per page (PDF, DOCX, TXT), then split into overlapping chunks."], ["2. Embed", "Turn each chunk into a vector. Default is a lexical hashing embedder; set an API key for semantic embeddings."], ["3. Retrieve", "pgvector finds the nearest chunks to the question by cosine distance."], ["4. Answer", "Extractive by default (picks the best sentences). With an LLM key, it writes an answer using only the retrieved text."], ["5. Cite", "Every answer lists the document and page it was built from. If nothing relevant is found, it says so."]];
  return (
    <>
      <div className="page-h"><div><h1>How it works</h1><p>A retrieval-augmented generation pipeline, built from scratch on FastAPI, PostgreSQL and pgvector.</p></div></div>
      <div className="grid g3">{steps.map(([t, d]) => <div key={t} className="card"><h3>{t}</h3><p className="muted">{d}</p></div>)}</div>
      <div className="card"><h3>Good to know</h3><p className="muted">Free-tier hosting: the first request can be slow. Without an LLM key configured, answers are extractive: the best matching sentences from your documents, quoted with their source.</p></div>
    </>
  );
}
