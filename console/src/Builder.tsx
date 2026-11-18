import type { CatalogTable } from "./types";

type Filter = { column: string; op: string; value: string | number };
type Model = {
  table: string; columns: string[]; filters: Filter[];
  join?: { table: string; left: string; right: string };
};
export default function Builder({ source, catalog, operators, onChange }: {
  source: string; catalog: CatalogTable[]; operators: Record<string, string[]>;
  onChange: (value: string) => void;
}) {
  let model: Model;
  try {
    model = JSON.parse(source);
    if (!model || !catalog.some(t => t.name === model.table) || !Array.isArray(model.columns) ||
      !model.columns.every(c => typeof c === "string") ||
      (model.join && (!catalog.some(t => t.name === model.join!.table) ||
        typeof model.join.left !== "string" || typeof model.join.right !== "string")) ||
      !Array.isArray(model.filters) || model.filters.some(f => !f || typeof f.column !== "string" ||
        typeof f.op !== "string" || !["number", "string"].includes(typeof f.value))) throw new Error();
  } catch {
    return <p className="frontend-help">This builder configuration is invalid. Use “Load example” to reset it.</p>;
  }
  const update = (patch: Partial<Model>) => onChange(JSON.stringify({ ...model, ...patch }, null, 2));
  const tables = catalog.filter(table => table.name === model.table || table.name === model.join?.table);
  const columns = tables.flatMap(table => table.columns.map(column => ({ ...column, key: `${table.name}.${column.name}` })));
  const editFilter = (index: number, patch: Partial<Filter>) =>
    update({ filters: model.filters.map((filter, i) => i === index ? { ...filter, ...patch } : filter) });
  return <div className="builder-form" id="source" tabIndex={-1}>
    <div className="builder-table-row">
      <label>From table<select id="builder-table" value={model.table} onChange={e => onChange(JSON.stringify({
        table: e.target.value, columns: [], filters: [],
      }, null, 2))}>{catalog.map(table => <option key={table.name}>{table.name}</option>)}</select></label>
      <label>Inner join<select value={model.join?.table ?? ""} onChange={e => {
        const table = catalog.find(t => t.name === e.target.value);
        update({
          join: table ? { table: table.name, left: `${model.table}.${catalog.find(t => t.name === model.table)!.columns[0].name}`, right: `${table.name}.${table.columns[0].name}` } : undefined,
          columns: model.columns.filter(c => !model.join || !c.startsWith(model.join.table + ".")),
          filters: model.filters.filter(f => !model.join || !f.column.startsWith(model.join.table + ".")),
        });
      }}><option value="">No join</option>{catalog.filter(t => t.name !== model.table).map(t => <option key={t.name}>{t.name}</option>)}</select></label>
    </div>
    {model.join && <div className="builder-table-row" id="builder-join">
      <label>Left join key<select value={model.join.left} onChange={e => update({ join: {
        ...model.join!, left: e.target.value,
        right: columns.find(c => c.key.startsWith(model.join!.table + ".") && c.type === columns.find(left => left.key === e.target.value)?.type)?.key ?? "",
      } })}>
        {columns.filter(c => c.key.startsWith(model.table + ".")).map(c => <option key={c.key}>{c.key}</option>)}</select></label>
      <span className="join-equals">=</span>
      <label>Right join key<select value={model.join.right} onChange={e => update({ join: { ...model.join!, right: e.target.value } })}>
        {columns.filter(c => c.key.startsWith(model.join!.table + ".") && c.type === columns.find(col => col.key === model.join!.left)?.type).map(c => <option key={c.key}>{c.key}</option>)}</select></label>
    </div>}
    <fieldset id="builder-columns"><legend>Columns to return</legend><div className="column-options">
      {columns.map(column => <label key={column.key}><input type="checkbox" checked={model.columns.includes(column.key)}
        onChange={e => update({ columns: e.target.checked ? [...model.columns, column.key] : model.columns.filter(c => c !== column.key) })} />
        <code>{column.key}</code><small>{column.type}</small></label>)}
    </div></fieldset>
    <fieldset><legend>WHERE · match all filters (AND)</legend>
      {model.filters.map((filter, i) => {
        const type = columns.find(c => c.key === filter.column)?.type ?? "INTEGER";
        return <div className="filter-row" key={i} id={`builder-filters[${i}]`}>
          <label><span>Column</span><select aria-label={`Filter ${i + 1} column`} value={filter.column} onChange={e => {
            const nextType = columns.find(c => c.key === e.target.value)?.type;
            editFilter(i, { column: e.target.value, op: "=", value: nextType === "INTEGER" ? 0 : "" });
          }}>{columns.map(c => <option key={c.key}>{c.key}</option>)}</select></label>
          <label><span>Comparison</span><select aria-label={`Filter ${i + 1} operator`} value={filter.op}
            onChange={e => editFilter(i, { op: e.target.value })}>{(operators[type] ?? ["="]).map(op => <option key={op}>{op}</option>)}</select></label>
          <label><span>Value</span><input aria-label={`Filter ${i + 1} value`} type="text" inputMode={type === "INTEGER" ? "numeric" : "text"}
            value={filter.value} onChange={e => {
              const value = e.target.value;
              editFilter(i, { value: type === "INTEGER" && /^[+-]?\d+$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : value });
            }} /></label>
          <button className="button secondary compact" aria-label={`Remove filter ${i + 1}`}
            onClick={() => update({ filters: model.filters.filter((_, index) => index !== i) })}>Remove</button>
        </div>;
      })}
      <button className="button secondary compact" disabled={!columns.length || model.filters.length >= 64}
        onClick={() => update({ filters: [...model.filters, { column: columns[0].key, op: "=", value: columns[0].type === "INTEGER" ? 0 : "" }] })}>Add filter</button>
    </fieldset>
    <p className="frontend-help">The server generates SQL and runs the real parser. Reordering column selections preserves select-list order.</p>
  </div>;
}
