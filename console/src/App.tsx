import { useEffect, useRef, useState } from "react";

import { downloadBundle, isBundle } from "./bundle";
import AddRow from "./DataPanel";
import Icon from "./Icon";
import Builder from "./Builder";
import { Diagnostic, LABELS, Rows, StageContent, TITLES, Verification } from "./Panels";
import { STAGES, type Bundle, type Cell, type StageName, type Workspace } from "./types";

const STATUS = { ok: "Complete", error: "Failed", skipped: "Not run" };
const SOURCE_TITLES: Record<string, string> = { sql: "SQL source", builder: "Visual query builder", nl: "Natural language", elastic: "Elastic JSON DSL" };
const SOURCE_LABELS: Record<string, string> = { sql: "SQL query", builder: "Builder configuration", nl: "Natural language query", elastic: "Elastic JSON query" };

async function responseJson(response: Response) {
  const data = await response.json();
  if (!response.ok) throw new Error(data.errors?.[0]?.message ?? `Request failed (${response.status}).`);
  if (data.v !== 1) throw new Error("This console does not support the server's response version.");
  return data;
}

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [source, setSource] = useState("");
  const [active, setActive] = useState<StageName>("optimize");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [networkError, setNetworkError] = useState("");
  const [fileError, setFileError] = useState("");
  const [replay, setReplay] = useState(false);
  const [frontend, setFrontend] = useState("sql");
  const [backend, setBackend] = useState("fixtures");
  const [dataBusy, setDataBusy] = useState(false);
  const [dataError, setDataError] = useState("");
  const [dataEpoch, setDataEpoch] = useState(0);
  const drafts = useRef<Record<string, string>>({});
  const editor = useRef<HTMLTextAreaElement>(null);
  const gutter = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const stageNav = useRef<HTMLElement>(null);
  const inFlight = useRef(false);
  const bundleEpoch = useRef(0);
  const dataStale = dataEpoch !== bundleEpoch.current;
  const dirty = bundle !== null && (source !== bundle.inputs.verbatim || frontend !== bundle.inputs.frontend_id ||
    (!replay && backend !== bundle.provenance.backend));

  function switchFrontend(next: string) {
    if (running) return;
    drafts.current[frontend] = source;
    setFrontend(next);
    setSource(drafts.current[next] ?? workspace?.examples[next] ?? "");
  }

  async function loadWorkspace() {
    setLoading(true);
    setNetworkError("");
    try {
      const data: Workspace = await responseJson(await fetch("/api/workspace", { signal: AbortSignal.timeout(10000) }));
      if (!isBundle(data.initial_bundle) || !Array.isArray(data.catalog) || !Array.isArray(data.presets)) {
        throw new Error("The server returned an invalid workspace. Restart the server and reload.");
      }
      setWorkspace(data);
      setBundle(data.initial_bundle);
      setSource(data.initial_bundle.inputs.verbatim);
      bundleEpoch.current = dataEpoch;
    } catch (error) {
      setNetworkError(error instanceof Error ? error.message : "Could not connect to the compiler.");
    } finally { setLoading(false); }
  }

  useEffect(() => { void loadWorkspace(); }, []);
  useEffect(() => {
    const nav = stageNav.current;
    const selected = nav?.querySelector<HTMLButtonElement>('[aria-pressed="true"]');
    if (nav && selected && nav.scrollWidth > nav.clientWidth) {
      nav.scrollLeft = selected.offsetLeft - (nav.clientWidth - selected.offsetWidth) / 2;
    }
  }, [active, bundle]);

  async function run() {
    if (!source.trim() || inFlight.current) return;
    if (frontend === "nl" && workspace?.nl_language?.version !== 1) {
      setNetworkError("Restart the compiler server to load the grammar-based NL frontend.");
      return;
    }
    inFlight.current = true;
    setRunning(true);
    setNetworkError("");
    setFileError("");
    const submitted = source;
    try {
      const data = await responseJson(await fetch("/api/query", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ v: 1, frontend_id: frontend, backend, source: submitted }),
        signal: AbortSignal.timeout(15000),
      }));
      if (!isBundle(data.bundle)) throw new Error("The compiler returned an unsupported bundle. Previous evidence is retained.");
      setBundle(data.bundle);
      bundleEpoch.current = dataEpoch;
      if (data.engine && typeof data.engine.available === "boolean" && typeof data.engine.reason === "string") {
        setWorkspace(current => current ? { ...current, engine: data.engine } : current);
      }
      setReplay(false);
      const failed = data.bundle.stages.find((stage: { status: string }) => stage.status === "error");
      if (failed) setActive(failed.name);
    } catch (error) {
      setNetworkError(error instanceof Error ? error.message : "Could not run the query. Check the server and retry.");
    } finally {
      inFlight.current = false;
      setRunning(false);
    }
  }

  async function importBundle(file: File | undefined) {
    if (!file || inFlight.current) return;
    setFileError("");
    try {
      if (file.size > 2 * 1024 * 1024) throw new Error("Choose a bundle smaller than 2 MiB.");
      const value: unknown = JSON.parse(await file.text());
      if (!isBundle(value)) throw new Error("This file is not a supported QueryRun v1 bundle.");
      setBundle(value);
      setSource(value.inputs.verbatim);
      setFrontend(value.inputs.frontend_id);
      bundleEpoch.current = dataEpoch;
      setReplay(true);
      setActive(value.stages.find(stage => stage.status === "error")?.name ?? "optimize");
    } catch (error) {
      setFileError(error instanceof Error ? error.message : "Could not read this bundle.");
    }
    if (fileInput.current) fileInput.current.value = "";
  }

  function locate(start: number, end: number) {
    const characters = Array.from(bundle?.inputs.verbatim ?? source);
    editor.current?.focus();
    editor.current?.setSelectionRange(characters.slice(0, start).join("").length, characters.slice(0, end).join("").length);
  }

  function applyData(data: { dataset?: string; catalog: Workspace["catalog"]; engine: Workspace["engine"] }) {
    setWorkspace(current => current ? {
      ...current, catalog: data.catalog, engine: data.engine, ...(data.dataset ? { dataset: data.dataset } : {}),
    } : current);
  }

  async function switchDataset(dataset: string) {
    if (!workspace || dataBusy || running) return;
    setDataBusy(true);
    setDataError("");
    try {
      const data = await responseJson(await fetch("/api/data/dataset", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ v: 1, dataset }),
        signal: AbortSignal.timeout(10000),
      }));
      applyData(data);
      setDataEpoch(epoch => epoch + 1);
    } catch (error) {
      setDataError(error instanceof Error ? error.message : "Could not switch the dataset.");
    } finally {
      setDataBusy(false);
    }
  }

  async function insertRows(table: string, rows: Cell[][]): Promise<true | string> {
    if (!workspace) return "The compiler is still connecting.";
    if (dataBusy) return "Wait for the current data request to finish.";
    setDataBusy(true);
    try {
      const data = await responseJson(await fetch("/api/data/insert", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ v: 1, table, rows }),
        signal: AbortSignal.timeout(10000),
      }));
      applyData(data);
      setDataEpoch(epoch => epoch + 1);
      return true;
    } catch (error) {
      return error instanceof Error ? error.message : "Could not insert these rows.";
    } finally {
      setDataBusy(false);
    }
  }

  return <div className="app-shell">
    <a href="#source" className="skip-link">Skip to query editor</a>
    <aside className="sidebar" aria-label="Workspace navigation">
      <div className="brand"><Icon name="layers" size={27} /><div>SQL Compiler<span>Query workbench</span></div></div>
      <nav className="frontend-nav" aria-label="Query frontends">
        {(workspace?.frontends ?? [
          { id: "sql", label: "SQL", available: true },
          { id: "builder", label: "Visual builder", available: false },
          { id: "nl", label: "Natural language", available: false },
          { id: "elastic", label: "Elastic DSL", available: false },
        ]).map(input => <button key={input.id} className={input.id === frontend ? "nav-item selected" : "nav-item"}
          disabled={!input.available || running} aria-current={input.id === frontend ? "page" : undefined}
          aria-label={input.available ? input.label : `${input.label} (planned)`}
          onClick={() => switchFrontend(input.id)}>
          <Icon name={input.id === "sql" ? "code" : input.id === "builder" ? "table" : "layers"} />
          <span>{input.label}</span>
        </button>)}
      </nav>
      <section className="catalog" aria-labelledby="catalog-heading">
        <div className="sidebar-heading"><h2 id="catalog-heading">Data</h2>
          <span>{workspace ? `${workspace.catalog.reduce((total, table) => total + table.row_count, 0)} rows` : "—"}</span></div>
        <div className="dataset-row">
          <label className="dataset-label" htmlFor="dataset-select">Dataset</label>
          <button className="text-button" disabled={!workspace || running || dataBusy}
            title="Restore the selected dataset to its original rows"
            onClick={() => workspace && void switchDataset(workspace.dataset)}>Reset</button>
        </div>
        <select id="dataset-select" className="dataset-select" aria-label="Preloaded dataset"
          value={workspace?.dataset ?? "default-v1"} disabled={!workspace || running || dataBusy}
          title={workspace?.datasets.find(item => item.id === workspace.dataset)?.description}
          onChange={event => void switchDataset(event.target.value)}>
          {workspace?.datasets.map(item => <option value={item.id} key={item.id}>{item.label}</option>)}
        </select>
        {dataError && <p className="data-error" role="alert">{dataError}</p>}
        <p className="dataset-note">Inserts apply to the session data behind all three backends. Restarting the server restores the preloaded dataset.</p>
        {workspace?.catalog.map(table => <details key={table.name} open>
          <summary><Icon name="table" size={16} /><span>{table.name}</span><small>{table.row_count} rows</small></summary>
          <dl>{table.columns.map(column => <div key={column.name}><dt>{column.name}</dt><dd>{column.type}</dd></div>)}</dl>
          {workspace && <AddRow key={`${table.name}:${table.row_count}`} table={table}
            busy={running || dataBusy} onInsert={insertRows} />}
        </details>)}
      </section>
      <div className="runtime">
        <p><span className="connection-dot" />Fixture backend{workspace ? " connected" : " connecting"}</p>
        <div className="engine-state" title={workspace?.engine.reason}><Icon name="layers" size={16} /><span>{workspace?.engine.available ? "Rust engine ready · protocol 1" : "Rust engine not connected"}</span></div>
        <small>All query execution runs in Python.<br />No silent backend fallback.</small>
      </div>
    </aside>

    <main className="workspace" aria-busy={loading}>
      <header className="workspace-header">
        <div><h1>Query workbench</h1><p>Follow a query from source to verified rows.</p></div>
        <div className="header-actions">
          <input ref={fileInput} type="file" accept=".json,application/json" hidden
            aria-label="Import a QueryRun bundle" onChange={event => void importBundle(event.target.files?.[0])} />
          <button className="button secondary compact" disabled={running} onClick={() => fileInput.current?.click()}><Icon name="upload" />Load bundle</button>
          <button className="button secondary compact" disabled={!bundle} onClick={() => bundle && downloadBundle(bundle)}><Icon name="download" />Export JSON</button>
        </div>
      </header>

      {networkError && <div className="transport-error" role="alert">
        <Icon name="alert" /><div><strong>Compiler connection problem</strong><p>{networkError}</p>
          <p>Start the backend with <code>bash demo/run_demo.sh</code>, then retry.</p></div>
        <button className="button secondary" onClick={() => workspace ? void run() : void loadWorkspace()}>Retry</button>
      </div>}
      {fileError && <div className="transport-error" role="alert"><Icon name="alert" /><p>{fileError}</p></div>}

      <section className="source-panel" aria-labelledby="source-heading" onKeyDown={event => {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
          event.preventDefault(); void run();
        }
      }}>
        <div className="source-toolbar">
          <h2 id="source-heading"><Icon name="code" />{SOURCE_TITLES[frontend]}</h2>
          <label className="backend-picker">Storage<select aria-label="Storage backend" value={backend} disabled={running}
            onChange={e => setBackend(e.target.value)}>
            <option value="fixtures">Python fixtures</option><option value="sqlite">SQLite storage</option>
            <option value="kb_db" disabled={!workspace?.engine.available}>Rust kb_db{!workspace?.engine.available ? " (unavailable)" : ""}</option>
          </select></label>
          {frontend === "sql" ? <label className="preset-picker">Example
            <select aria-label="Load an example query" value="" disabled={!workspace || running} onChange={event => {
              const preset = workspace?.presets.find(item => item.id === event.target.value);
              if (preset) { setSource(preset.source); editor.current?.focus(); }
            }}>
              <option value="" disabled>Choose a query</option>
              {workspace?.presets.map(preset => <option value={preset.id} key={preset.id}>{preset.label}</option>)}
            </select>
          </label> : <button className="button secondary compact" disabled={!workspace || running}
            onClick={() => setSource(workspace?.examples[frontend] ?? "")}>Load example</button>}
        </div>
        {frontend === "builder" && workspace ? <Builder source={source} catalog={workspace.catalog}
          operators={workspace.supported.types} onChange={setSource} /> : <div className="editor">
          <div ref={gutter} className="line-numbers" aria-hidden="true">{(source || " ").split("\n").map((_, i) => <span key={i}>{i + 1}</span>)}</div>
          <textarea id="source" ref={editor} value={source} spellCheck={false} autoCapitalize="off"
            autoComplete="off" autoCorrect="off" aria-label={SOURCE_LABELS[frontend]} aria-describedby="query-help"
            maxLength={16384} disabled={loading} placeholder="SELECT name FROM student WHERE marks > 80;"
            style={{ whiteSpace: frontend === "nl" ? "pre-wrap" : "pre" }}
            onScroll={event => { if (gutter.current) gutter.current.scrollTop = event.currentTarget.scrollTop; }}
            onChange={event => setSource(event.target.value)} />
        </div>}
        {frontend === "nl" && <p className="frontend-help">
          {workspace?.nl_language?.version !== 1 ? "Restart the compiler server to enable the NL grammar." :
            "Grammar-based NL compiler, not a template matcher or LLM. Combine fields with commas or “and”; use comparisons such as “above 80”, “at least 80”, or “between 80 and 90”. Tables and joins are resolved from the catalog."}
        </p>}
        {frontend === "elastic" && <p className="frontend-help">Version 1: _source, term, range, bool.filter (AND), and one local join extension. No OR, nested bool, wildcards, or aggregates.</p>}
        <div className="source-footer">
          <p id="query-help">SELECT · one equijoin · AND comparisons <span className="keyboard-hint">Ctrl / ⌘ + Enter to run</span></p>
          <button className="button primary" onClick={() => void run()} disabled={loading || running || !source.trim() || (frontend === "nl" && workspace?.nl_language?.version !== 1)}>
            <Icon name="play" size={16} />{running ? "Running compiler…" : "Run query"}
          </button>
        </div>
      </section>

      <div className="evidence-bar" aria-live="polite">
        <span className={dirty || networkError || dataStale ? "evidence-status stale" : "evidence-status"}>
          <Icon name={dirty || networkError || dataStale ? "clock" : replay ? "upload" : "check"} size={15} />
          {running ? "Compiling submitted source…" : networkError && bundle ? "Request failed · showing previous run" :
            dirty ? "Source changed · showing previous run" :
            dataStale ? "Data changed since this run · run again for current rows" :
            replay ? "Replay · recorded bundle" : bundle?.errors.length ? "Run completed with an error" :
              bundle ? `Live run · ${bundle.provenance.backend === "fixtures" ? "fixture data" : bundle.provenance.backend + " storage"}` : "Loading workspace…"}
        </span>
        <span>Bundle v{bundle?.run_schema_version ?? 1}{bundle && ` · compiler ${bundle.compiler_version}`}</span>
      </div>

      {bundle?.inputs.generated_sql && !dirty && <details className="generated-sql" open>
        <summary>Generated SQL · {bundle.inputs.frontend_id} frontend</summary>
        <pre className="code-block">{bundle.inputs.generated_sql}</pre>
        {bundle.stages[1].artifact.nl_lowering !== undefined && <details className="artifact-details">
          <summary>NL field resolution and join inference</summary>
          <pre className="code-block">{JSON.stringify(bundle.stages[1].artifact.nl_lowering, null, 2)}</pre>
        </details>}
        {bundle.stages[1].artifact.template_trace !== undefined && <details className="artifact-details">
          <summary>Legacy template trace (recorded bundle)</summary>
          <pre className="code-block">{JSON.stringify(bundle.stages[1].artifact.template_trace, null, 2)}</pre>
        </details>}
      </details>}

      {bundle?.errors.map((error, index) => <Diagnostic key={index} error={error} source={bundle.inputs.verbatim}
        locate={!dirty && error.locator?.char_start !== undefined ? () => locate(
          error.locator!.char_start!, error.locator!.char_end ?? error.locator!.char_start! + 1,
        ) : undefined} />)}

      {loading ? <section className="loading-panel" aria-label="Loading compiler workspace">
        <div /><div /><div /><p>Loading compiler artifacts…</p>
      </section> : bundle && <>
        <nav ref={stageNav} className="stage-strip" aria-label="Compiler stages">
          {bundle.stages.map((stage, index) => <button key={stage.name} className={`stage-button ${active === stage.name ? "active" : ""}`}
            aria-pressed={active === stage.name} aria-controls="stage-content"
            onClick={() => setActive(stage.name)}>
            <span className={`stage-number ${stage.status}`}>
              {stage.status === "error" ? <Icon name="alert" size={15} /> : String(index + 1).padStart(2, "0")}
            </span>
            <span className="stage-label">{LABELS[stage.name]}<small>{STATUS[stage.status]} · {stage.timing_ms.toFixed(2)} ms</small></span>
          </button>)}
        </nav>

        <section className="inspector" id="stage-content" aria-label={`${LABELS[active]} stage artifacts`}>
          <div className="inspector-heading"><h2>{TITLES[active]}</h2>
            <span>{bundle.stages.find(stage => stage.name === active)?.status === "ok" ?
              "Recorded by the compiler" : "Inspect stage status"}</span></div>
          <StageContent bundle={bundle} active={active} />
        </section>

        {bundle.metrics && <section className="metrics-band" aria-label="Measured execution work">
          <h2>Measured work</h2>
          {[
            ["Candidate pairs", "join_pairs_tried"],
            ["Left rows into join", "left_in"],
            ["Result rows", "rows_out"],
          ].map(([label, key]) => <div className="measurement" key={key}>
            <span>{label}</span><strong>{bundle.metrics![key]?.pre ?? "—"}<Icon name="arrow" size={17} />{bundle.metrics![key]?.post ?? "—"}</strong>
          </div>)}
          <span className="measurement-key">Original <Icon name="arrow" size={13} /> optimized</span>
        </section>}

        <div className="results-grid"><Rows bundle={bundle} /><Verification bundle={bundle} /></div>
        <footer className="workspace-footer"><span>One compiler pipeline. Every number comes from this bundle.</span>
          <span>{replay ? `Recorded backend: ${bundle.provenance.backend}` : `Backend: ${bundle.provenance.backend}`}
            {bundle.provenance.fixture_set && ` · ${bundle.provenance.fixture_set}`}</span></footer>
      </>}
    </main>
  </div>;
}
