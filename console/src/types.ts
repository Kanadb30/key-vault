export const STAGES = ["lex", "parse", "bind", "plan", "optimize", "execute", "verify"] as const;
export type StageName = typeof STAGES[number];
export type Cell = string | number;
export type Pair = { pre: number | null; post: number | null };
export type Locator = {
  kind: string; line?: number; col?: number; char_start?: number; char_end?: number;
  pointer?: string; node_id?: string; template_id?: string; slot?: string;
};
export type Envelope = {
  stage: string; code: string; message: string; origin: string; locator: Locator | null;
};
export type Stage = {
  name: StageName; status: "ok" | "error" | "skipped"; timing_ms: number;
  artifact: Record<string, unknown>;
};
export type NodeStat = {
  node_id: number; operator: string; label: string; rows_in: number | null;
  left_in: number | null; right_in: number | null; rows_out: number;
  join_pairs_tried: number; join_pairs_matched: number; time_ns: number;
};
export type Diff = {
  term_id: string; term: string; target: "left" | "right" | "kept";
  from_node_id: number; to_node_id: number;
};
export type Check = {
  passed: boolean; sql_sent: string; sqlite_rows: Cell[][]; counter_diff: unknown;
  compared: { pre: boolean; post: boolean };
};
export type Bundle = {
  run_schema_version: 1; compiler_version: string;
  inputs: { frontend_id: string; verbatim: string; normalized: string; generated_sql?: string };
  stages: Stage[]; plans_ascii: { pre: string; post: string } | null;
  plan_diff: Diff[]; node_stats: { pre: NodeStat[]; post: NodeStat[] } | null;
  rows: { columns: string[]; rows: Cell[][]; count: number } | null;
  metrics: Record<string, Pair> | null; errors: Envelope[];
  sqlite_cross_check: Check | null;
  provenance: { backend: string; fixture_set: string | null; protocol: number | null };
};
export type Preset = { id: string; label: string; description: string; source: string };
export type CatalogTable = { name: string; columns: { name: string; type: string }[]; row_count: number };
export type Dataset = { id: string; label: string; description: string };
export type Workspace = {
  v: 1; catalog: CatalogTable[]; presets: Preset[]; initial_bundle: Bundle;
  backend: { backend: string; available: boolean };
  engine: { available: boolean; reason: string };
  dataset: string;
  datasets: Dataset[];
  frontends: { id: string; label: string; available: boolean }[];
  examples: Record<string, string>;
  supported: { types: Record<string, string[]>; unsupported: string[]; dsl_rejected: string[] };
  nl_language?: { version: number; parser: string };
};
