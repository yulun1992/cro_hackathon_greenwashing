import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  FileCheck2,
  FileText,
  FlaskConical,
  Layers3,
  Leaf,
  LoaderCircle,
  Search,
  ShieldCheck,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import type {
  Case,
  Config,
  Finding,
  Passage,
  Reference,
  Result,
  Status,
} from "./types";
import VerificationDetails from "./VerificationDetails";

const labels: Record<Status, string> = {
  contradicted: "Contradicted",
  insufficient_evidence: "Evidence gap",
  not_comparable: "Not comparable",
  supported: "Supported",
};
const order: Status[] = [
  "contradicted",
  "insufficient_evidence",
  "not_comparable",
  "supported",
];
const pretty = (s: string) => s.replaceAll("_", " ");

async function responseJSON(response: Response) {
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Try again.`,
    );
  if (!data) throw new Error("The server returned an unreadable response.");
  return data;
}

export default function App() {
  const [cases, setCases] = useState<Case[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [caseId, setCaseId] = useState("A");
  const [claims, setClaims] = useState("");
  const [disclosure, setDisclosure] = useState("");
  const [mode, setMode] = useState("Offline demo");
  const [verification, setVerification] = useState("facts");
  const [source, setSource] = useState("demo");
  const [version, setVersion] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState("");
  const [stale, setStale] = useState(false);
  const [filter, setFilter] = useState<Status | "all">("all");
  const [selected, setSelected] = useState<{
    passage: Passage;
    ref: Reference;
    kind: string;
  } | null>(null);
  const [retry, setRetry] = useState(0);
  const [helpOpen, setHelpOpen] = useState(false);
  const revision = useRef(0);
  const request = useRef<AbortController | null>(null);
  const uploadInput = useRef<HTMLInputElement>(null);
  const sourceDialog = useRef<HTMLDialogElement>(null);
  const helpDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let active = true;
    setInitializing(true);
    Promise.all([
      fetch("/api/cases").then(responseJSON),
      fetch("/api/config").then(responseJSON),
    ])
      .then(([items, settings]) => {
        if (!active) return;
        setCases(items);
        setConfig(settings);
        setCaseId(items[0].id);
        setClaims(items[0].claims.join("\n"));
        setDisclosure(items[0].disclosure);
        setError("");
      })
      .catch((e) => {
        if (active)
          setError(`Could not connect to the review server. ${e.message}`);
      })
      .finally(() => {
        if (active) setInitializing(false);
      });
    return () => {
      active = false;
      request.current?.abort();
    };
  }, [retry]);

  useEffect(() => {
    if (selected) sourceDialog.current?.showModal();
    else sourceDialog.current?.close();
  }, [selected]);
  useEffect(() => {
    if (helpOpen) helpDialog.current?.showModal();
    else helpDialog.current?.close();
  }, [helpOpen]);

  function invalidate() {
    revision.current += 1;
    request.current?.abort();
    setBusy(false);
    setError("");
    if (result || busy) setStale(true);
    setResult(null);
    setSelected(null);
    setFilter("all");
  }
  function selectCase(id: string) {
    invalidate();
    setCaseId(id);
    const item = cases.find((c) => c.id === id);
    setClaims(item?.claims.join("\n") || "");
    setDisclosure(item?.disclosure || "");
  }
  function chooseFile(next: File | null) {
    invalidate();
    if (next && next.size > (config?.max_file_bytes || 10485760)) {
      setError("Regulation must be at most 10 MB.");
      setFile(null);
      if (uploadInput.current) uploadInput.current.value = "";
      return;
    }
    setFile(next);
  }
  async function compare(event: React.FormEvent) {
    event.preventDefault();
    if (!claims.trim() || !disclosure.trim()) {
      setError("Add at least one claim and supporting disclosure.");
      return;
    }
    if (source === "upload" && !file) {
      setError("Choose a regulation file first.");
      return;
    }
    const current = ++revision.current;
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    setBusy(true);
    setError("");
    setResult(null);
    setFilter("all");
    setSelected(null);
    const body = new FormData();
    body.set("claims", claims);
    body.set("disclosure", disclosure);
    body.set("mode", mode);
    body.set("verification", mode === "Live AI" ? verification : "none");
    body.set("regulation_source", source);
    body.set("version", version || "Not specified");
    if (source === "upload" && file) body.set("regulation_file", file);
    try {
      const data = await fetch("/api/reviews", {
        method: "POST",
        body,
        signal: controller.signal,
      }).then(responseJSON);
      if (current !== revision.current) return;
      setResult(data);
      setStale(false);
    } catch (e) {
      if (
        current !== revision.current ||
        (e instanceof DOMException && e.name === "AbortError")
      )
        return;
      setError(
        e instanceof Error
          ? e.message
          : "Analysis did not complete. Please try again.",
      );
    } finally {
      if (current === revision.current) setBusy(false);
    }
  }
  function inspect(ref: Reference, kind: "disclosure" | "regulation") {
    const passage = result?.sources[kind].find((p) => p.id === ref.id);
    if (passage) setSelected({ passage, ref, kind });
  }
  function download() {
    if (!result) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result.report, null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "green_claims_review.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const claimCount = claims.split("\n").filter((c) => c.trim()).length;
  const findings =
    result?.report.findings.filter(
      (f) => filter === "all" || f.status === filter,
    ) || [];

  function citation(
    ref: Reference,
    kind: "disclosure" | "regulation",
    index: number,
  ) {
    return (
      <button
        className="citation"
        key={`${ref.id}-${index}`}
        type="button"
        onClick={() => inspect(ref, kind)}
      >
        <span className="citation-top">
          <span>
            <FileText size={13} /> {ref.id}{" "}
            <span className="citation-locator">· {ref.location}</span>
          </span>
          <ArrowUpRight size={14} />
        </span>
        <q>{ref.quote}</q>
        <span className="citation-footer">
          <Check size={12} /> Quote matched to source{" "}
          <span>Inspect passage</span>
        </span>
      </button>
    );
  }
  function findingCard(f: Finding, i: number) {
    return (
      <article className={`finding ${f.status}`} key={f.claim_id}>
        <div className="finding-heading">
          <span className="finding-number">
            {String(i + 1).padStart(2, "0")}
          </span>
          <span className={`badge ${f.status}`}>{labels[f.status]}</span>
          <span className="claim-id">{f.claim_id}</span>
        </div>
        <h3>{f.claim}</h3>
        <div className="tags">
          {f.test_types.map((t) => (
            <span key={t}>{pretty(t)}</span>
          ))}
        </div>
        <p className="reasoning">{f.explanation}</p>
        <div className="evidence-label">
          <BookOpen size={14} /> DISCLOSURE EVIDENCE
        </div>
        {f.evidence.length ? (
          f.evidence.map((ref, n) => citation(ref, "disclosure", n))
        ) : (
          <p className="small muted">No validated disclosure citation.</p>
        )}
        <details className="reg-assessment">
          <summary>
            <span>
              <ShieldCheck size={15} /> Regulatory assessment
            </span>
            <span className="reg-status">
              {pretty(f.regulation_status)} <ChevronDown size={14} />
            </span>
          </summary>
          <p className="small muted">{f.regulation_explanation}</p>
          {f.regulation_references.map((ref, n) =>
            citation(ref, "regulation", n),
          )}
          {!!f.candidate_regulation_passages?.length && (
            <p className="candidate-note">
              Candidate passages only. No regulatory assessment was performed.
            </p>
          )}
          {f.candidate_regulation_passages?.map((ref, n) =>
            citation(ref, "regulation", n),
          )}
        </details>
        {f.verification && <VerificationDetails value={f.verification} inspect={inspect} />}
        <div className="follow-up">
          <CircleHelp size={15} />
          <div>
            <span>FOLLOW-UP QUESTION</span>
            <p>{f.follow_up_question}</p>
          </div>
        </div>
      </article>
    );
  }

  return (
    <>
      <header className="topbar">
        <a className="brand" href="/" aria-label="Green Claims home">
          <span className="brand-mark">
            <Leaf size={21} />
          </span>
          green<span>claims</span>
          <span className="brand-divider" />
          <span className="workspace-label">Review workspace</span>
        </a>
        <div className="top-actions">
          <span className="private-label">
            <ShieldCheck size={14} /> Evidence-led review
          </span>
          <button className="help-button" onClick={() => setHelpOpen(true)}>
            <CircleHelp size={16} /> How it works
          </button>
        </div>
      </header>
      <main>
        <section className="page-heading">
          <div>
            <div className="eyebrow">
              <span /> CLAIMS, CHECKED AGAINST EVIDENCE
            </div>
            <h1>A clearer view of green claims.</h1>
            <p>
              Compare statements. Examine the evidence. Know what to ask next.
            </p>
          </div>
          <div className="method-label">
            <Layers3 size={19} />
            <div>
              Traceable by design
              <span>Source quotations with every finding</span>
            </div>
          </div>
        </section>
        <div className="workspace">
          <form className="setup-panel" onSubmit={compare}>
            <div className="panel-title">
              <div>
                <span className="step">01</span>
                <h2>Prepare your review</h2>
              </div>
              <FileText size={18} />
            </div>
            <div className="setup-body">
              <label className="label" htmlFor="case">
                Start with a case <span>Synthetic examples</span>
              </label>
              <div className="select-wrap">
                <select
                  id="case"
                  value={caseId}
                  onChange={(e) => selectCase(e.target.value)}
                  disabled={initializing || !cases.length}
                >
                  {cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                  <option value="custom">Custom material</option>
                </select>
                <ChevronDown size={15} />
              </div>
              <div
                className="mode-switch"
                role="group"
                aria-label="Analysis mode"
              >
                <button
                  type="button"
                  aria-pressed={mode === "Offline demo"}
                  className={mode === "Offline demo" ? "active" : ""}
                  onClick={() => {
                    invalidate();
                    setMode("Offline demo");
                  }}
                >
                  <FlaskConical size={14} /> Offline demo
                </button>
                <button
                  type="button"
                  aria-pressed={mode === "Live AI"}
                  className={mode === "Live AI" ? "active" : ""}
                  disabled={!config?.live_available}
                  onClick={() => {
                    invalidate();
                    setMode("Live AI");
                  }}
                >
                  <Sparkles size={14} /> Live AI{" "}
                  {!config?.live_available && <span className="config-dot" />}
                </button>
              </div>
              <p className="mode-hint">
                {mode === "Offline demo"
                  ? "Replays the three unchanged examples. No model call."
                  : "Analyzes your inputs with the server’s configured model."}
              </p>
              {mode === "Live AI" && (
                <>
                  <label className="label" htmlFor="verification">Evidence cross-check</label>
                  <div className="select-wrap">
                    <select id="verification" value={verification} onChange={(e) => {
                      invalidate();
                      setVerification(e.target.value);
                    }}>
                      <option value="none">Original analysis · 1 model call</option>
                      <option value="facts">Facts & arithmetic · 2 model calls</option>
                      <option value="facts_and_judge">Facts & LLM judge · 3 model calls</option>
                    </select>
                    <ChevronDown size={15} />
                  </div>
                  <p className="mode-hint">Quoted facts are aligned and calculated when possible. The judge gives a separate review opinion.</p>
                </>
              )}
              {!config?.live_available && !initializing && (
                <p className="connection-note">
                  Live AI needs endpoint and credentials configured on the
                  server.
                </p>
              )}
              <div className="field-heading">
                <label htmlFor="claims">Environmental claims</label>
                <span>{claimCount} / 15 claims</span>
              </div>
              <textarea
                id="claims"
                className="claims-input"
                value={claims}
                disabled={initializing}
                onChange={(e) => {
                  invalidate();
                  setClaims(e.target.value);
                }}
                placeholder="One claim per line…"
                maxLength={30015}
              />
              <div className="field-heading">
                <label htmlFor="disclosure">Supporting disclosure</label>
                <span>{disclosure.length.toLocaleString()} / 35,000</span>
              </div>
              <textarea
                id="disclosure"
                className="disclosure-input"
                value={disclosure}
                disabled={initializing}
                onChange={(e) => {
                  invalidate();
                  setDisclosure(e.target.value);
                }}
                placeholder="Paste the evidence behind the claims…"
                maxLength={35000}
              />
              <div className="section-divider" />
              <div className="field-heading">
                <label htmlFor="regulation">Regulatory reference</label>
                <span>Optional</span>
              </div>
              <div className="select-wrap">
                <select
                  id="regulation"
                  value={source}
                  onChange={(e) => {
                    invalidate();
                    setSource(e.target.value);
                  }}
                >
                  <option value="demo">Fictional demo standard</option>
                  <option value="upload">Upload regulation</option>
                  <option value="none">No regulation</option>
                </select>
                <ChevronDown size={15} />
              </div>
              {source === "demo" && (
                <div className="source-note">
                  <BookOpen size={15} />
                  <div>
                    Demo review standard{" "}
                    <span>Fictional · for demonstration only</span>
                  </div>
                  <span className="source-chip">MD</span>
                </div>
              )}
              {source === "upload" && (
                <div className="upload-section">
                  <label
                    className={`upload-box ${file ? "has-file" : ""}`}
                    htmlFor="upload"
                  >
                    <UploadCloud size={24} />
                    <strong>
                      {file ? file.name : "Choose a regulation file"}
                    </strong>
                    <span>
                      {file
                        ? `${(file.size / 1024).toFixed(1)} KB · click to replace`
                        : "PDF, TXT or Markdown · up to 10 MB"}
                    </span>
                    <input
                      ref={uploadInput}
                      id="upload"
                      type="file"
                      accept=".pdf,.txt,.md"
                      onChange={(e) => chooseFile(e.target.files?.[0] || null)}
                    />
                  </label>
                  <label className="label version-label" htmlFor="version">
                    Version label
                  </label>
                  <input
                    id="version"
                    type="text"
                    value={version}
                    maxLength={200}
                    placeholder="e.g. Policy v2.1 · September 2026"
                    onChange={(e) => {
                      invalidate();
                      setVersion(e.target.value);
                    }}
                  />
                  <p className="small muted">
                    The uploaded file replaces the demo standard. Currency and
                    applicability are not independently verified.
                  </p>
                </div>
              )}
              {source === "none" && (
                <p className="small muted">
                  Compare claims with disclosure only.
                </p>
              )}
              {!!error && (
                <div className="error-message" role="alert">
                  <CircleHelp size={17} />
                  <div>
                    {error}
                    {!config && (
                      <button
                        type="button"
                        onClick={() => setRetry((v) => v + 1)}
                      >
                        Reconnect
                      </button>
                    )}
                  </div>
                </div>
              )}
              <button
                className="compare-button"
                disabled={busy || initializing || !config}
                type="submit"
              >
                {busy ? (
                  <>
                    <LoaderCircle className="spin" size={17} /> Reviewing
                    evidence…
                  </>
                ) : (
                  <>
                    <Search size={17} /> Compare & screen{" "}
                    <ArrowRight size={17} />
                  </>
                )}
              </button>
              <p className="submit-note">
                {mode === "Offline demo"
                  ? "Synthetic findings. No regulatory determination."
                  : "Your material is sent to the configured model when you compare."}
              </p>
            </div>
          </form>
          <section
            className="results-panel"
            aria-label="Review results"
            aria-busy={busy}
          >
            <div className="panel-title results-title">
              <div>
                <span className="step">02</span>
                <h2>Evidence & findings</h2>
              </div>
              {result ? (
                <button className="export-button" onClick={download}>
                  <ArrowDownToLine size={15} /> Export JSON
                </button>
              ) : (
                <span className="awaiting">
                  {busy ? "Review in progress" : "Ready when you are"}
                </span>
              )}
            </div>
            <div aria-live="polite" className="sr-only">
              {busy
                ? "Analyzing your material."
                : result
                  ? `Review complete. ${result.report.findings.length} findings.`
                  : stale
                    ? "Inputs changed. Run the review again."
                    : ""}
            </div>
            {!result && (
              <div className="empty-results">
                <div className={`empty-symbol ${busy ? "working" : ""}`}>
                  {busy ? (
                    <LoaderCircle className="spin" size={31} />
                  ) : (
                    <FileCheck2 size={33} />
                  )}
                  <span>
                    <Check size={12} />
                  </span>
                </div>
                <span className="eyebrow">
                  {busy
                    ? "REVIEW IN PROGRESS"
                    : stale
                      ? "MATERIALS UPDATED"
                      : "FROM STATEMENT TO SOURCE"}
                </span>
                <h2>
                  {busy
                    ? "Following the evidence."
                    : stale
                      ? "A fresh look at your changes."
                      : "Every claim deserves\nan evidence trail."}
                </h2>
                <p>
                  {busy
                    ? "Preparing passages, comparing claims and checking source quotations. Each live model stage can take up to two minutes."
                    : stale
                      ? "Your previous results have been cleared. Compare again to review the updated material."
                      : "Start with a synthetic case or add your own material. Your findings and verifiable source excerpts will appear here."}
                </p>
                <div className="journey">
                  <div>
                    <span>
                      <FileText size={17} />
                    </span>
                    <strong>Compare</strong>
                    <small>Claims vs. disclosure</small>
                  </div>
                  <ArrowRight size={15} />
                  <div>
                    <span>
                      <Search size={17} />
                    </span>
                    <strong>Check</strong>
                    <small>Numbers, scope & time</small>
                  </div>
                  <ArrowRight size={15} />
                  <div>
                    <span>
                      <BookOpen size={17} />
                    </span>
                    <strong>Trace</strong>
                    <small>Back to the source</small>
                  </div>
                </div>
                <div className="empty-footnote">
                  <ShieldCheck size={15} />
                  <span>
                    Built to support a reviewer’s judgment.
                    <br />
                    Never a substitute for it.
                  </span>
                </div>
              </div>
            )}
            {result && (
              <div className="results-body">
                <div
                  className={`run-banner ${result.report.mode === "Live AI" ? "live" : ""}`}
                >
                  <span>
                    {result.report.mode === "Live AI" ? (
                      <Sparkles size={16} />
                    ) : (
                      <FlaskConical size={16} />
                    )}
                    <strong>
                      {result.report.mode === "Live AI"
                        ? "Live AI analysis"
                        : "Offline demonstration"}
                    </strong>
                  </span>
                  <p>
                    {result.report.mode === "Live AI"
                      ? "Quotations checked against supplied text. Reasoning and applicability need review."
                      : "Authored example findings. No AI call or regulatory assessment was performed."}
                  </p>
                </div>
                <div className="metrics">
                  {order.map((status) => (
                    <button
                      key={status}
                      type="button"
                      aria-pressed={filter === status}
                      className={`metric ${status} ${filter === status ? "selected" : ""}`}
                      onClick={() =>
                        setFilter(filter === status ? "all" : status)
                      }
                    >
                      <span className="metric-dot" />
                      <strong>{result.report.summary[status]}</strong>
                      <span>{labels[status]}</span>
                    </button>
                  ))}
                </div>
                <div className="findings-toolbar">
                  <span>
                    {filter === "all"
                      ? `${result.report.findings.length} claims reviewed`
                      : `${findings.length} ${labels[filter].toLowerCase()} findings`}
                  </span>
                  {filter !== "all" ? (
                    <button onClick={() => setFilter("all")}>
                      Show all <X size={12} />
                    </button>
                  ) : (
                    <span>
                      <CheckCircle2 size={13} /> Source-linked findings
                    </span>
                  )}
                </div>
                {result.report.warnings.map((w, i) => (
                  <div className="warning" key={i}>
                    <CircleHelp size={15} />
                    {w}
                  </div>
                ))}
                {findings.length ? (
                  findings.map(findingCard)
                ) : (
                  <div className="no-findings">
                    No claims in this category.
                    <button onClick={() => setFilter("all")}>
                      View all findings
                    </button>
                  </div>
                )}
                {result.report.regulation && (
                  <div className="provenance">
                    <div>
                      <BookOpen size={16} />
                      <strong>{result.report.regulation.filename}</strong>
                      <span>
                        {result.report.regulation_passages_sent}/
                        {result.report.regulation_total_passages} passages used
                      </span>
                    </div>
                    <p>
                      {result.report.regulation.version} · Version not
                      independently verified
                    </p>
                    <details>
                      <summary>Source fingerprint & review details</summary>
                      <dl>
                        <dt>Regulation SHA-256</dt>
                        <dd>{result.report.regulation.sha256}</dd>
                        <dt>Input fingerprint</dt>
                        <dd>{result.report.input_fingerprint}</dd>
                        <dt>Generated</dt>
                        <dd>{result.report.generated_at_utc}</dd>
                      </dl>
                    </details>
                  </div>
                )}
                <details className="limits">
                  <summary>
                    Review limitations <ChevronDown size={14} />
                  </summary>
                  {result.report.limitations.map((l) => (
                    <p key={l}>{l}</p>
                  ))}
                </details>
              </div>
            )}
          </section>
        </div>
        <footer>
          <span>
            <Leaf size={13} /> GREEN CLAIMS
          </span>
          <p>Comparison, testing & greenwashing screening</p>
          <span className="footer-status">
            <span />{" "}
            {config
              ? "Review server connected"
              : initializing
                ? "Connecting to review server"
                : "Review server unavailable"}
          </span>
        </footer>
      </main>
      <dialog
        aria-labelledby="source-title"
        className="source-dialog"
        ref={sourceDialog}
        onClose={() => setSelected(null)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setSelected(null);
        }}
      >
        {selected && (
          <>
            <div className="dialog-top">
              <span className="eyebrow">SOURCE INSPECTOR</span>
              <button
                className="icon-button"
                aria-label="Close source inspector"
                onClick={() => setSelected(null)}
              >
                <X size={20} />
              </button>
            </div>
            <h2 id="source-title">
              {selected.kind === "regulation"
                ? result?.report.regulation?.filename
                : "Supporting disclosure"}
            </h2>
            <p className="small muted">
              {selected.passage.id} · {selected.passage.location}
            </p>
            {selected.kind === "regulation" && (
              <p className="source-version">
                {result?.report.regulation?.version} · Version not independently
                verified
              </p>
            )}
            <h3>Quoted evidence</h3>
            <blockquote>{selected.ref.quote}</blockquote>
            <div className="quote-check">
              <CheckCircle2 size={14} /> Quotation matched to extracted source
              text
            </div>
            <h3>Full source passage</h3>
            <div className="passage-text">{selected.passage.text}</div>
            <p className="small muted">
              Quote verification checks the text exists. It does not
              independently validate the conclusion.
            </p>
          </>
        )}
      </dialog>
      <dialog
        aria-labelledby="help-title"
        className="help-dialog"
        ref={helpDialog}
        onClose={() => setHelpOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setHelpOpen(false);
        }}
      >
        <div className="dialog-top">
          <span className="eyebrow">BEHIND THE REVIEW</span>
          <button
            className="icon-button"
            aria-label="Close explanation"
            onClick={() => setHelpOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <h2 id="help-title">Small steps. Traceable evidence.</h2>
        <div className="help-steps">
          <div>
            <span>01</span>
            <div>
              <h3>Prepare the material</h3>
              <p>
                Claims are separated by line. Disclosure and regulation are
                split at paragraphs, with long passages capped at roughly 1,800
                characters. PDFs keep page locations.
              </p>
            </div>
          </div>
          <div>
            <span>02</span>
            <div>
              <h3>Select the context</h3>
              <p>
                All disclosure is included within the input limit. Short
                regulations are included in full; longer ones use keyword
                overlap within a 30,000-character budget. No vector search is
                used.
              </p>
            </div>
          </div>
          <div>
            <span>03</span>
            <div>
              <h3>Analyze and verify</h3>
              <p>
                Live AI compares the supplied material. The server checks
                finding structure and exact quotations before displaying
                results. Offline demo replays authored fixtures.
              </p>
            </div>
          </div>
        </div>
        <div className="help-limit">
          One regulation per review. Multiple regulations and effective-date
          verification are planned, not implemented.
        </div>
      </dialog>
    </>
  );
}
