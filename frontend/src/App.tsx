import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { askStream, fetchRepos, type AskEvent, type Repo, type Source } from "./api";

type Status = "idle" | "streaming" | "error";

export default function App() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [repoName, setRepoName] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [provider, setProvider] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState("");
  const [lastAsked, setLastAsked] = useState<{ question: string; repo: string } | null>(null);
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchRepos()
      .then((rs) => {
        setRepos(rs);
        if (rs.length > 0) setRepoName(rs[0].name);
      })
      .catch((e) => {
        setError(`Backend unreachable. Is uvicorn running? (${e})`);
        setStatus("error");
      });
  }, []);

  const repo = repos.find((r) => r.name === repoName);

  function onEvent(e: AskEvent) {
    switch (e.type) {
      case "meta":
        setProvider(e.provider);
        break;
      case "sources":
        setSources(e.sources);
        break;
      case "token":
        setAnswer((a) => a + e.text);
        break;
      case "error":
        setError(e.message);
        setStatus("error");
        break;
      case "done":
        setElapsedMs(e.elapsed_ms);
        break;
    }
  }

  async function run(q: string, repo: string) {
    if (!q.trim() || status === "streaming") return;
    setLastAsked({ question: q, repo });
    setAnswer("");
    setSources([]);
    setProvider("");
    setError("");
    setElapsedMs(null);
    setStatus("streaming");
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      await askStream(q, repo, onEvent, ac.signal);
      setStatus("idle");
    } catch (e) {
      if (ac.signal.aborted) {
        setStatus("idle");
      } else {
        setError(String(e));
        setStatus("error");
      }
    }
  }

  function ask() {
    return run(question, repoName);
  }

  function regenerate() {
    if (lastAsked) void run(lastAsked.question, lastAsked.repo);
  }

  function stop() {
    abortRef.current?.abort();
  }

  function sourceUrl(s: Source): string {
    if (!repo) return "#";
    return `${repo.github}/blob/${repo.branch}/${s.path}#L${s.start_line}-L${s.end_line}`;
  }

  return (
    <main>
      <header>
        <h1>askrepo</h1>
        <p className="tagline">ask my code anything: retrieval-grounded, cited</p>
        {provider === "mock" && <span className="badge mock">MOCK</span>}
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
      >
        <label>
          Repo
          <select value={repoName} onChange={(e) => setRepoName(e.target.value)}>
            {repos.map((r) => (
              <option key={r.name} value={r.name}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Question
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="How does the local→foundation fallback work?"
            rows={3}
            maxLength={500}
          />
        </label>
        <div className="actions">
          {status === "streaming" ? (
            <button type="button" onClick={stop}>
              Stop
            </button>
          ) : (
            <>
              <button type="submit" disabled={!question.trim() || repos.length === 0}>
                Ask
              </button>
              {lastAsked && (
                <button type="button" className="secondary" onClick={regenerate}>
                  Regenerate
                </button>
              )}
            </>
          )}
        </div>
      </form>

      {error && (
        <div className="error" role="alert">
          <strong>Something went wrong.</strong> {error}
          {lastAsked && status !== "streaming" && " You can regenerate to try again."}
        </div>
      )}

      {(answer || status === "streaming") && (
        <section className="answer">
          <h2>Answer</h2>
          <div className="answer-body">
            <Markdown remarkPlugins={[remarkGfm]}>{answer}</Markdown>
            {status === "streaming" && <span className="cursor">▌</span>}
          </div>
          {elapsedMs !== null && (
            <p className="answer-meta">
              {provider === "mock" ? "mock provider (canned)" : "retrieval + Claude"} ·{" "}
              {(elapsedMs / 1000).toFixed(1)}s
            </p>
          )}
        </section>
      )}

      {sources.length > 0 && (
        <section className="sources">
          <h2>Sources</h2>
          <ul>
            {sources.map((s) => (
              <li key={`${s.path}:${s.start_line}`}>
                <a href={sourceUrl(s)} target="_blank" rel="noreferrer">
                  {s.path}:{s.start_line}–{s.end_line}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
