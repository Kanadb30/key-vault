import { STAGES, type Bundle } from "./types";

const object = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string";
const number = (v: unknown): v is number => typeof v === "number" && Number.isSafeInteger(v);
const nullableNumber = (v: unknown) => v === null || number(v);
const cells = (v: unknown): boolean => Array.isArray(v) && v.every(
  row => Array.isArray(row) && row.every(cell => text(cell) || number(cell)),
);

function safeTree(value: unknown, depth = 0): boolean {
  if (depth > 64) return false;
  if (typeof value === "number") return Number.isFinite(value) && Math.abs(value) <= Number.MAX_SAFE_INTEGER;
  if (Array.isArray(value)) return value.every(item => safeTree(item, depth + 1));
  if (object(value)) return Object.values(value).every(item => safeTree(item, depth + 1));
  return value === null || typeof value === "string" || typeof value === "boolean";
}

/** Validate saved evidence before render; never execute imported compiler data. */
export function isBundle(value: unknown): value is Bundle {
  if (!object(value) || value.run_schema_version !== 1 || !text(value.compiler_version) || !safeTree(value)) return false;
  const { inputs, stages, plans_ascii, rows, node_stats, metrics, errors, plan_diff,
    sqlite_cross_check: check, provenance } = value;
  if (!object(inputs) || !text(inputs.verbatim) || !text(inputs.normalized) || !text(inputs.frontend_id)) return false;
  if (!["sql", "builder", "nl", "elastic"].includes(inputs.frontend_id) ||
    (inputs.generated_sql !== undefined && !text(inputs.generated_sql))) return false;
  if (!Array.isArray(stages) || stages.length !== STAGES.length || !stages.every(
    (stage, i) => object(stage) && stage.name === STAGES[i] &&
      ["ok", "error", "skipped"].includes(String(stage.status)) &&
      typeof stage.timing_ms === "number" && Number.isFinite(stage.timing_ms) &&
      stage.timing_ms >= 0 && object(stage.artifact),
  )) return false;
  for (const stage of stages) {
    if (stage.name === "lex" && stage.status === "ok" &&
      (!Array.isArray(stage.artifact.tokens) || !stage.artifact.tokens.every(
        (token: unknown) => object(token) && text(token.type) && text(token.value) &&
          object(token.locator) && number(token.locator.line) && number(token.locator.col),
      ))) return false;
    if (stage.name === "bind" && stage.status === "ok" &&
      (!object(stage.artifact.bound) || !Array.isArray(stage.artifact.bound.columns) ||
        !stage.artifact.bound.columns.every((column: unknown) => object(column) &&
          text(column.table) && text(column.column) && text(column.type)))) return false;
  }
  if (plans_ascii !== null && (!object(plans_ascii) || !text(plans_ascii.pre) || !text(plans_ascii.post))) return false;
  if (rows !== null && (!object(rows) || !Array.isArray(rows.columns) ||
    !rows.columns.every(text) || !cells(rows.rows) || !number(rows.count) ||
    !Array.isArray(rows.rows) || rows.count !== rows.rows.length ||
    !rows.rows.every(row => Array.isArray(row) && row.length === (rows.columns as unknown[]).length))) return false;
  if (metrics !== null && (!object(metrics) || !Object.values(metrics).every(
    pair => object(pair) && nullableNumber(pair.pre) && nullableNumber(pair.post),
  ))) return false;
  if (node_stats !== null && (!object(node_stats) || !["pre", "post"].every(
    version => Array.isArray(node_stats[version]) && node_stats[version].every(
      (stat: unknown) => object(stat) && number(stat.node_id) && text(stat.operator) &&
        text(stat.label) && nullableNumber(stat.rows_in) && nullableNumber(stat.left_in) &&
        nullableNumber(stat.right_in) && number(stat.rows_out) && number(stat.join_pairs_tried) &&
        number(stat.join_pairs_matched) && number(stat.time_ns),
    ),
  ))) return false;
  if (!Array.isArray(plan_diff) || !plan_diff.every(
    diff => object(diff) && text(diff.term_id) && text(diff.term) &&
      ["left", "right", "kept"].includes(String(diff.target)) &&
      number(diff.from_node_id) && number(diff.to_node_id),
  )) return false;
  if (!Array.isArray(errors) || !errors.every(
    error => object(error) && text(error.stage) &&
      [...STAGES, "console", "storage", "bridge"].includes(error.stage) &&
      text(error.code) && text(error.message) &&
      text(error.origin) && (error.locator === null || (
         object(error.locator) && text(error.locator.kind) &&
         ["pointer", "node_id", "template_id", "slot"].every(key =>
           object(error.locator) && (error.locator[key] === undefined || text(error.locator[key]))) &&
        ["line", "col", "char_start", "char_end"].every(
          key => error.locator !== null && object(error.locator) &&
            (error.locator[key] === undefined || number(error.locator[key])),
        )
      )),
  )) return false;
  if (check !== null && (!object(check) || typeof check.passed !== "boolean" ||
    !text(check.sql_sent) || !cells(check.sqlite_rows) || !object(check.compared) ||
    typeof check.compared.pre !== "boolean" || typeof check.compared.post !== "boolean")) return false;
  return object(provenance) && text(provenance.backend) &&
    (provenance.fixture_set === null || text(provenance.fixture_set)) &&
    nullableNumber(provenance.protocol);
}

export function downloadBundle(bundle: Bundle) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = "queryrun-sql.json";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
