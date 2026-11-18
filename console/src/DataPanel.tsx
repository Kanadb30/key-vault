import { useState } from "react";

import type { CatalogTable, Cell } from "./types";

type Result = true | string;

/** Per-table row entry: typed fields for one row, or pasted JSON for a batch.
 * The server stays authoritative; this only prevents obvious typos. */
export default function AddRow({ table, busy, onInsert }:
{ table: CatalogTable; busy: boolean; onInsert: (table: string, rows: Cell[][]) => Promise<Result> }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"form" | "json">("form");
  const [fields, setFields] = useState(table.columns.map(() => ""));
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  function rowFromFields(): Cell[][] | string {
    const row: Cell[] = [];
    for (let index = 0; index < table.columns.length; index++) {
      const column = table.columns[index];
      const raw = fields[index].trim();
      if (raw === "") return `Fill the ${column.name} column.`;
      if (column.type === "INTEGER") {
        if (!/^[+-]?[0-9]+$/.test(raw)) return `${column.name} needs an integer.`;
        row.push(Number(raw));
      } else {
        row.push(raw);
      }
    }
    return [row];
  }

  function rowsFromJson(): Cell[][] | string {
    let value: unknown;
    try {
      value = JSON.parse(text);
    } catch {
      return "This is not valid JSON. Paste an array of rows, e.g. [[5, \"Zara\", 95, 20]].";
    }
    if (!Array.isArray(value) || value.length === 0 || !value.every(Array.isArray)) {
      return "Paste an array of rows: [[5, \"Zara\", 95, 20]] with one inner array per row.";
    }
    return value as Cell[][];
  }

  async function submit() {
    const rows = mode === "form" ? rowFromFields() : rowsFromJson();
    if (typeof rows === "string") { setError(rows); return; }
    setError("");
    const result = await onInsert(table.name, rows);
    if (result !== true) setError(result);
    else { setOpen(false); setText(""); }
  }

  return <details className="add-row" open={open} onToggle={event => {
    const details = event.currentTarget as HTMLDetailsElement;
    setOpen(details.open);
    if (!details.open) setError("");
  }}>
    <summary>Add row</summary>
    {open && <div className="add-row-body">
      <div className="row-mode" role="group" aria-label="Row input mode">
        <button className={mode === "form" ? "mode-button selected" : "mode-button"} type="button"
          aria-pressed={mode === "form"} onClick={() => { setMode("form"); setError(""); }}>Row form</button>
        <button className={mode === "json" ? "mode-button selected" : "mode-button"} type="button"
          aria-pressed={mode === "json"} onClick={() => { setMode("json"); setError(""); }}>Paste JSON</button>
      </div>
      {mode === "form"
        ? <div className="add-row-fields">
          {table.columns.map((column, index) => <label key={column.name}>
            <span>{column.name}</span>
            <input value={fields[index]} disabled={busy}
              placeholder={column.type === "INTEGER" ? "integer" : "text"}
              inputMode={column.type === "INTEGER" ? "numeric" : "text"}
              onChange={event => setFields(fields.map((value, i) => i === index ? event.target.value : value))} />
          </label>)}
        </div>
        : <textarea className="add-row-json" rows={4} value={text} disabled={busy}
          spellCheck={false} aria-label={`Rows as JSON for ${table.name}`}
          placeholder={`[[5, "Zara", 95, 20]]\n[6, "Dev", 72, 30]`}
          onChange={event => setText(event.target.value)} />}
      {error && <p className="add-row-error" role="alert">{error}</p>}
      <div className="insert-actions">
        <button className="button secondary compact" type="button" disabled={busy}
          onClick={() => void submit()}>
          {mode === "form" ? "Insert row" : `Insert rows`}
        </button>
        <small>{table.columns.map(column => column.name).join(" · ")}</small>
      </div>
    </div>}
  </details>;
}
