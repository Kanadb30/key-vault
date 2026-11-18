import { type ReactNode } from "react";
import Icon from "./Icon";
import type { Bundle, Envelope, NodeStat, StageName } from "./types";

export const LABELS: Record<StageName, string> = {
  lex: "Tokens", parse: "AST", bind: "Bind", plan: "Plan",
  optimize: "Pushdown", execute: "Execute", verify: "Verify",
};

export const TITLES: Record<StageName, string> = {
  lex: "The token stream", parse: "Abstract syntax tree", bind: "Resolved references",
  plan: "The logical plan", optimize: "Predicate pushdown",
  execute: "Execution trace", verify: "SQLite verification",
};

export function Json({ value }: { value: unknown }) {
  return <pre className="code-block">{JSON.stringify(value, null, 2)}</pre>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export function PlanPair({ bundle }: { bundle: Bundle }) {
  const plans = bundle.plans_ascii;
  if (!plans) return <Empty>The compiler has not produced a plan. Resolve the error above and run again.</Empty>;
  return <>
    <div className="plan-pair">
      {(["pre", "post"] as const).map(version => <section className="plan-pane" key={version}>
        <div className="pane-heading">
          <h3>{version === "pre" ? "Before pushdown" : "After pushdown"}</h3>
          <span className={`plan-tag ${version === "post" ? "accent" : ""}`}>
            {version === "pre" ? "Original" : "Optimized"}
          </span>
        </div>
        <pre className="plan-code" tabIndex={0} aria-label={`${version === "pre" ? "Original" : "Optimized"} plan`}>
          {plans[version].split("\n").map((line, index) => <span key={index} className={
            bundle.plan_diff.some(diff => line.includes(diff.term)) ? "plan-moved" : undefined
          }>{line}{"\n"}</span>)}
        </pre>
      </section>)}
    </div>
    <div className="rewrite-evidence">
      <Icon name="arrow" />
      <div>{bundle.plan_diff.length ? bundle.plan_diff.map(diff => <p key={diff.term_id}>
        <code>{diff.term_id}</code> <code>{diff.term}</code>
        <span>{diff.target === "kept" ? " kept above the join" : ` moved to the ${diff.target} input`}</span>
        <small> · node {diff.from_node_id} to {diff.to_node_id}</small>
      </p>) : <p>No eligible filter above a join. The original plan is unchanged.</p>}</div>
    </div>
  </>;
}

export function Rows({ bundle }: { bundle: Bundle }) {
  const rows = bundle.rows;
  return <section className="result-panel">
    <div className="panel-heading"><h2>Result rows</h2><span>{rows ? `${rows.count} ${rows.count === 1 ? "row" : "rows"}` : "Not executed"}</span></div>
    {!rows ? <Empty>Rows appear after a successful execution.</Empty> : rows.count === 0 ?
      <Empty>The query returned no rows. Try a less restrictive WHERE comparison.</Empty> :
      <div className="table-scroll" tabIndex={0} aria-label="Result rows">
        <table><thead><tr>{rows.columns.map((column, i) => <th key={i} scope="col">{column}</th>)}</tr></thead>
          <tbody>{rows.rows.map((row, i) => <tr key={i}>{row.map((cell, j) =>
            <td key={j} className={typeof cell === "number" ? "numeric" : undefined}>{cell}</td>,
          )}</tr>)}</tbody>
        </table>
      </div>}
  </section>;
}

export function Verification({ bundle, detailed = false }: { bundle: Bundle; detailed?: boolean }) {
  const check = bundle.sqlite_cross_check;
  return <section className="verification-panel">
    <div className="panel-heading">
      <h2>SQLite cross-check</h2>
      <span className={check ? (check.passed ? "status success" : "status failure") : "status"}>
        {check && <Icon name={check.passed ? "check" : "alert"} size={15} />}
        {check ? (check.passed ? "Passed" : "Mismatch") : "Not run"}
      </span>
    </div>
    {!check ? <Empty>No verification evidence. Execute a valid query with SQLite verification enabled.</Empty> : <>
      <p className="verification-copy">Both plans {check.passed ? "match" : "were compared with"} SQLite using
        {" "}<code>Counter(rows)</code>. Row order is ignored; duplicates are counted.</p>
      <pre className="sql-evidence">{check.sql_sent}</pre>
      {detailed && <>
        <dl className="comparison-list">
          <div><dt>Original plan</dt><dd>{check.compared.pre ? "Matches SQLite" : "Mismatch"}</dd></div>
          <div><dt>Optimized plan</dt><dd>{check.compared.post ? "Matches SQLite" : "Mismatch"}</dd></div>
        </dl>
        <h3 className="subheading">SQLite rows</h3><Json value={check.sqlite_rows} />
      </>}
      {check.counter_diff !== null && <><h3 className="subheading">Counter difference</h3><Json value={check.counter_diff} /></>}
    </>}
  </section>;
}

function StatTable({ stats, title }: { stats: NodeStat[]; title: string }) {
  return <section>
    <h3 className="subheading">{title}</h3>
    <div className="table-scroll" tabIndex={0} aria-label={`${title} node statistics`}>
      <table className="stat-table">
        <thead><tr><th scope="col">Node / operator</th><th scope="col">Rows in</th><th scope="col">Rows out</th>
          <th scope="col">Pairs tried</th><th scope="col">Matched</th></tr></thead>
        <tbody>{stats.map(stat => <tr key={stat.node_id}>
          <td><code>#{stat.node_id} {stat.operator}</code><small>{stat.label}</small></td>
          <td>{stat.rows_in ?? "—"}</td><td>{stat.rows_out}</td>
          <td>{stat.operator === "Join" ? stat.join_pairs_tried : "—"}</td>
          <td>{stat.operator === "Join" ? stat.join_pairs_matched : "—"}</td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>;
}

export function StageContent({ bundle, active }: { bundle: Bundle; active: StageName }) {
  const stage = bundle.stages.find(item => item.name === active)!;
  if (stage.status === "skipped" && typeof stage.artifact.reason === "string") return <Empty>{stage.artifact.reason}</Empty>;
  if (active === "optimize") return <PlanPair bundle={bundle} />;
  if (active === "verify") return <Verification bundle={bundle} detailed />;
  if (stage.status !== "ok") return <Empty>
    {stage.status === "error" ? "This stage failed. Inspect the diagnostic above." : "This stage was not run."}
    {" "}Fix the source and run the compiler to continue.
  </Empty>;
  if (active === "plan") return <pre className="code-block" tabIndex={0}>{bundle.plans_ascii?.pre}</pre>;
  if (active === "parse") return <>
    {typeof stage.artifact.nl_ast_text === "string" && <>
      <h3 className="subheading">Natural-language AST</h3>
      <pre className="code-block ast-text">{stage.artifact.nl_ast_text}</pre>
      <details className="artifact-details"><summary>Structured NL AST with source locations</summary><Json value={stage.artifact.nl_ast} /></details>
      <details className="artifact-details"><summary>NL grammar (Lark EBNF)</summary><pre className="code-block">{String(stage.artifact.nl_grammar)}</pre></details>
      <h3 className="subheading">Lowered shared query AST</h3>
    </>}
    <pre className="code-block ast-text">{String(stage.artifact.ast)}</pre>
    <details className="artifact-details"><summary>Structured AST with source locations</summary><Json value={stage.artifact.tree} /></details>
  </>;
  if (active === "lex") {
    const tokens = stage.artifact.tokens as { type: string; value: string; locator: { line: number; col: number } }[];
    if (!Array.isArray(tokens)) return <Empty>No token list was recorded in this bundle.</Empty>;
    return <>{stage.artifact.language === "nl" && <p className="frontend-help">These tokens come from your NL input, not the generated SQL.</p>}
    <div className="table-scroll token-table" tabIndex={0} aria-label="Lexer tokens">
      <table><thead><tr><th scope="col">Token</th><th scope="col">Lexeme</th><th scope="col">Line : column</th></tr></thead>
        <tbody>{tokens.map((token, index) => <tr key={index}>
          <td><code>{token.type}</code></td><td><code>{token.value}</code></td>
          <td>{token.locator.line} : {token.locator.col}</td>
        </tr>)}</tbody></table>
    </div></>;
  }
  if (active === "bind") {
    const bound = stage.artifact.bound as { columns: { table: string; column: string; type: string }[] };
    if (!bound || !Array.isArray(bound.columns)) return <Json value={stage.artifact} />;
    return <>
      <div className="table-scroll" tabIndex={0} aria-label="Bound projection columns">
        <table><thead><tr><th scope="col">Table</th><th scope="col">Column</th><th scope="col">Resolved type</th></tr></thead>
          <tbody>{bound.columns.map((column, index) => <tr key={index}>
            <td><code>{column.table}</code></td><td><code>{column.column}</code></td><td>{column.type}</td>
          </tr>)}</tbody></table>
      </div>
      <details className="artifact-details"><summary>Complete bound query</summary><Json value={bound} /></details>
    </>;
  }
  if (active === "execute" && bundle.node_stats) return <div className="trace-grid">
    <StatTable stats={bundle.node_stats.pre} title="Original plan" />
    <StatTable stats={bundle.node_stats.post} title="Optimized plan" />
  </div>;
  return <Json value={stage.artifact} />;
}

export function Diagnostic({ error, source, locate }: { error: Envelope; source: string; locate?: () => void }) {
  const start = error.locator?.char_start;
  const end = error.locator?.char_end;
  const characters = Array.from(source);
  const hasSpan = start !== undefined && end !== undefined && start >= 0 && end >= start;
  return <section className="diagnostic" role="alert">
    <Icon name="alert" size={20} />
    <div>
      <div className="diagnostic-heading"><h2>{error.stage === "bind" ? "Semantic error" : `${error.stage[0].toUpperCase()}${error.stage.slice(1)} error`}</h2>
        <code>{error.code}</code></div>
      <p>{error.message}</p>
      {hasSpan && <pre className="error-source">{characters.slice(0, start).join("")}<mark>{characters.slice(start, end).join("") || " "}</mark>{characters.slice(end).join("")}</pre>}
      {error.locator?.line && <p className="error-location">Line {error.locator.line}, column {error.locator.col}
        {locate && <button className="text-button" onClick={locate}>Locate in editor</button>}</p>}
      {error.locator?.kind === "json_pointer" && <p className="error-location">JSON path: <code>{error.locator.pointer}</code></p>}
      {error.locator?.kind === "builder_node" && <p className="error-location">Builder field: <code>{error.locator.node_id}</code></p>}
      {error.locator?.kind === "template_slot" && <p className="error-location">Template: <code>{error.locator.template_id}</code> · slot: <code>{error.locator.slot}</code></p>}
    </div>
  </section>;
}
