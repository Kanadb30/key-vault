import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // The server owns one session dataset for its whole lifespan. Restore the
  // demo set before each test so order can never leak rows between cases.
  const response = await page.request.post("/api/data/dataset", { data: { v: 1, dataset: "default-v1" } });
  expect(response.ok(), "workspace data is reachable").toBeTruthy();
});

test("initial workbench shows real plans, rows, and honest backend status", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Before pushdown" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "After pushdown" })).toBeVisible();
  await expect(page.getByText(/Rust engine (ready|not connected)/)).toBeVisible();
  await expect(page.getByText("Asha", { exact: true })).toBeVisible();
  await expect(page.getByText("Meera", { exact: true })).toBeVisible();
  await expect(page.getByText("Passed", { exact: true })).toBeVisible();
  const nav = await page.getByRole("navigation", { name: "Compiler stages" }).boundingBox();
  const selected = await page.getByRole("button", { name: /Pushdown/ }).boundingBox();
  expect(selected!.x).toBeGreaterThanOrEqual(nav!.x);
  expect(selected!.x + selected!.width).toBeLessThanOrEqual(nav!.x + nav!.width);
  await expect(page.getByRole("button", { name: /Visual builder/ })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await page.screenshot({ path: `/tmp/opencode/sql-console-${info.project.name}.png`, fullPage: true });
});

test("visual builder runs the shared pipeline and edits typed filters", async ({ page }, info) => {  await page.goto("/");
  await page.getByRole("button", { name: "Visual builder", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Visual query builder" })).toBeVisible();
  await expect(page.getByLabel("Filter 1 value")).toHaveValue("80");
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("Generated SQL · builder frontend")).toBeVisible();
  await expect(page.getByText("Asha", { exact: true })).toBeVisible();
  await expect(page.getByText("Meera", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `/tmp/opencode/sql-builder-${info.project.name}.png`, fullPage: true });
  await page.getByLabel("Filter 1 value").fill("90");
  await page.getByLabel("Filter 1 value").press("Control+Enter");
  await expect(page.getByText("1 row", { exact: true })).toBeVisible();
  await expect(page.getByText("Meera", { exact: true })).toHaveCount(0);
});

test("the data panel inserts a row, flags stale evidence, and shows it after a rerun", async ({ page }, info) => {
  await page.goto("/");
  const studentCard = page.locator(".catalog details", { has: page.locator("summary", { hasText: "student" }) });
  await studentCard.locator(".add-row > summary").click();
  await page.getByRole("button", { name: "Insert row" }).click();
  await expect(page.getByText("Fill the id column.")).toBeVisible();
  const integers = page.locator(".add-row-fields input[placeholder='integer']");
  await integers.nth(0).fill("5");
  await page.locator(".add-row-fields input[placeholder='text']").fill("Zara");
  await integers.nth(1).fill("95");
  await integers.nth(2).fill("20");
  await expect(page.getByText("5 rows", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Insert row" }).click();
  await expect(page.getByText("Data changed since this run · run again for current rows")).toBeVisible();
  await expect(page.getByText("5 rows", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("Live run · fixture data", { exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Zara", exact: true })).toBeVisible();
  await expect(page.getByText("Data changed since this run")).toHaveCount(0);
  await studentCard.locator(".add-row > summary").click();
  await page.getByRole("button", { name: "Paste JSON" }).click();
  await page.getByLabel("Rows as JSON for student").fill("this is not json");
  await page.getByRole("button", { name: "Insert rows" }).click();
  await expect(page.getByText("This is not valid JSON.")).toBeVisible();
  await page.getByLabel("Rows as JSON for student").fill('[[6, "Dev", 72, 30]]');
  await page.getByRole("button", { name: "Insert rows" }).click();
  await expect(page.getByText("6 rows", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(page.getByText("4 rows", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `/tmp/opencode/sql-data-${info.project.name}.png`, fullPage: true });
});

test("a bigger preloaded dataset changes the catalog and the measured work", async ({ page }, info) => {
  await page.goto("/");
  await page.getByLabel("Preloaded dataset").selectOption("classroom-60");
  await expect(page.getByText("60 rows", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Natural language", exact: true }).click();
  await page.getByRole("textbox", { name: "Natural language query" }).fill("show student names and department names and marks where marks > 80");
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("23 rows", { exact: true })).toBeVisible();
  await expect(page.locator(".metrics-band")).toContainText("360");
  await expect(page.locator(".metrics-band")).toContainText("138");
  await expect(page.getByRole("cell", { name: "Rohan Nair", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByLabel("Preloaded dataset").selectOption("default-v1");
  await expect(page.getByText("4 rows", { exact: true })).toBeVisible();
  await page.screenshot({ path: `/tmp/opencode/sql-dataset-${info.project.name}.png`, fullPage: true });
});

test("natural language compiles new projections through real tokens and two ASTs", async ({ page }, info) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Natural language", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Natural language query" })).toBeEnabled();
  const source = "show student names and department names and marks where marks > 80";
  await page.getByRole("textbox", { name: "Natural language query" }).fill(source);
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("Generated SQL · nl frontend")).toBeVisible();
  await expect(page.getByText("NL field resolution and join inference")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "marks", exact: true })).toBeVisible();
  const stages = page.getByRole("navigation", { name: "Compiler stages" });
  await stages.getByRole("button", { name: /Tokens/ }).click();
  await expect(page.getByRole("cell", { name: "COMMAND", exact: true })).toBeVisible();
  await expect(page.getByText("These tokens come from your NL input, not the generated SQL.")).toBeVisible();
  await stages.getByRole("button", { name: /AST/ }).click();
  await expect(page.getByRole("heading", { name: "Natural-language AST", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Lowered shared query AST", exact: true })).toBeVisible();
  await expect(page.getByText("NL grammar (Lark EBNF)", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `/tmp/opencode/sql-nl-${info.project.name}.png`, fullPage: true });
  await page.getByRole("textbox", { name: "Natural language query" }).fill("delete all rows");
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("NL_PARSE_UNEXPECTED_TOKEN", { exact: true })).toBeVisible();
});

test("NL binder errors highlight the words the user actually typed", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Natural language", exact: true }).click();
  const source = "show names from student\nwhere grade > 80";
  await page.getByRole("textbox", { name: "Natural language query" }).fill(source);
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("BIND_UNKNOWN_COLUMN", { exact: true })).toBeVisible();
  await expect(page.locator(".error-source mark")).toHaveText("grade");
  await page.getByRole("button", { name: "Locate in editor" }).click();
  expect(await page.getByRole("textbox", { name: "Natural language query" }).evaluate((element: HTMLTextAreaElement) =>
    [element.selectionStart, element.selectionEnd],
  )).toEqual([source.indexOf("grade"), source.indexOf("grade") + 5]);
});

test("an old backend cannot masquerade as the new NL compiler", async ({ page }) => {
  await page.route("**/api/workspace", async route => {
    const response = await route.fetch();
    const data = await response.json();
    delete data.nl_language;
    await route.fulfill({ response, json: data });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Natural language", exact: true }).click();
  await expect(page.getByText("Restart the compiler server to enable the NL grammar.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Run query", exact: true })).toBeDisabled();
});

test("Elastic DSL runs directly and reports unsupported operators by path", async ({ page, request }, info) => {
  const workspace = await (await request.get("/api/workspace")).json();
  await page.goto("/");
  await page.getByRole("button", { name: "Elastic DSL", exact: true }).click();
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("Generated SQL · elastic frontend")).toBeVisible();
  await expect(page.getByText("Asha", { exact: true })).toBeVisible();
  await page.screenshot({ path: `/tmp/opencode/sql-elastic-${info.project.name}.png`, fullPage: true });
  const dsl = JSON.parse(workspace.examples.elastic);
  dsl.query = { bool: { should: [] } };
  await page.getByRole("textbox", { name: "Elastic JSON query" }).fill(JSON.stringify(dsl));
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("DSL_UNSUPPORTED_OPERATOR", { exact: true })).toBeVisible();
  await expect(page.getByText("$.query.bool.should", { exact: true })).toBeVisible();
});

test("all connected storage backends produce verified rows", async ({ page, request }) => {
  const workspace = await (await request.get("/api/workspace")).json();
  await page.goto("/");
  await expect(page.getByText("Live run · fixture data")).toBeVisible();
  for (const backend of ["sqlite", ...(workspace.engine.available ? ["kb_db"] : [])]) {
    await page.getByLabel("Storage backend").selectOption(backend);
    await page.getByRole("button", { name: "Run query", exact: true }).click();
    await expect(page.getByText(`Live run · ${backend} storage`, { exact: true })).toBeVisible();
    await expect(page.getByText("Asha", { exact: true })).toBeVisible();
    await expect(page.getByText("Passed", { exact: true })).toBeVisible();
  }
});

test("all seven stages are inspectable", async ({ page }) => {
  await page.goto("/");
  const stages = page.getByRole("navigation", { name: "Compiler stages" });
  await expect(stages.getByRole("button")).toHaveCount(7);
  await stages.getByRole("button", { name: /Tokens/ }).click();
  await expect(page.getByRole("heading", { name: "The token stream" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "COMP_OP", exact: true })).toBeVisible();
  await stages.getByRole("button", { name: /AST/ }).click();
  await expect(page.getByRole("heading", { name: "Abstract syntax tree" })).toBeVisible();
  await stages.getByRole("button", { name: /Bind/ }).click();
  await expect(page.getByRole("heading", { name: "Resolved references" })).toBeVisible();
  await stages.getByRole("button", { name: /Plan/ }).click();
  await expect(page.getByRole("heading", { name: "The logical plan" })).toBeVisible();
  await stages.getByRole("button", { name: /Execute/ }).click();
  await expect(page.getByRole("heading", { name: "Execution trace" })).toBeVisible();
  await stages.getByRole("button", { name: /Verify/ }).click();
  await expect(page.getByRole("heading", { name: "SQLite verification" })).toBeVisible();
});

test("changed source is not presented as current evidence; keyboard runs", async ({ page }) => {
  await page.goto("/");
  const editor = page.getByRole("textbox", { name: "SQL query" });
  await expect(editor).toBeEnabled();
  await editor.fill("SELECT name FROM student WHERE marks > 90;");
  await expect(page.getByText("Source changed · showing previous run")).toBeVisible();
  await editor.press("Control+Enter");
  await expect(page.getByText("Live run · fixture data")).toBeVisible();
  await expect(page.getByText("Asha", { exact: true })).toBeVisible();
  await expect(page.getByText("Meera", { exact: true })).toHaveCount(0);
  await expect(page.getByText("1 row", { exact: true })).toBeVisible();
});

test("semantic errors highlight the source and can select the offending span", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("textbox", { name: "SQL query" })).toBeEnabled();
  await page.getByLabel("Load an example query").selectOption("unknown-column");
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Semantic error" })).toBeVisible();
  await expect(page.getByText("BIND_UNKNOWN_COLUMN", { exact: true })).toBeVisible();
  await expect(page.locator(".error-source mark")).toHaveText("grade");
  await page.getByRole("button", { name: "Locate in editor" }).click();
  expect(await page.getByRole("textbox", { name: "SQL query" }).evaluate((element: HTMLTextAreaElement) =>
    [element.selectionStart, element.selectionEnd],
  )).toEqual([7, 12]);
  await expect(page.getByText("Asha", { exact: true })).toHaveCount(0);
});

test("transport failure retains previous evidence and offers retry", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Live run · fixture data")).toBeVisible();
  await page.route("**/api/query", route => route.abort());
  await page.getByRole("button", { name: "Run query", exact: true }).click();
  await expect(page.getByText("Compiler connection problem", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeVisible();
  await expect(page.getByText("Request failed · showing previous run", { exact: true })).toBeVisible();
  await expect(page.getByText("Asha", { exact: true })).toBeVisible();
});

test("exported bundle can be loaded as clearly labeled recorded evidence", async ({ page, request }) => {
  const response = await request.get("/api/workspace");
  const { initial_bundle: bundle } = await response.json();
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Export JSON" })).toBeEnabled();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("queryrun-sql.json");
  await page.getByLabel("Import a QueryRun bundle").setInputFiles({
    name: "queryrun.json", mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(bundle)),
  });
  await expect(page.getByText("Replay · recorded bundle", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Before pushdown" })).toBeVisible();
});

test("invalid bundle files produce a recoverable error", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Live run · fixture data")).toBeVisible();
  await page.getByLabel("Import a QueryRun bundle").setInputFiles({
    name: "invalid.json", mimeType: "application/json", buffer: Buffer.from('{"run_schema_version":99}'),
  });
  await expect(page.getByText("This file is not a supported QueryRun v1 bundle.")).toBeVisible();
  await expect(page.getByText("Asha", { exact: true })).toBeVisible();
});

test("malformed nested artifacts and empty diagnostic stages are rejected", async ({ page, request }) => {
  const response = await request.get("/api/workspace");
  const { initial_bundle: original } = await response.json();
  await page.goto("/");
  await expect(page.getByText("Live run · fixture data")).toBeVisible();
  const badTokens = structuredClone(original);
  badTokens.stages[0].artifact.tokens = [null];
  const badStage = structuredClone(original);
  badStage.errors = [{ stage: "", code: "INTERNAL", message: "bad", origin: "console", locator: null }];
  const unsafeInteger = structuredClone(original);
  unsafeInteger.stages[1].artifact.tree.where[0].literal.value = 9007199254740992;
  for (const invalid of [badTokens, badStage, unsafeInteger]) {
    await page.getByLabel("Import a QueryRun bundle").setInputFiles({
      name: "bad-bundle.json", mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(invalid)),
    });
    await expect(page.getByText("This file is not a supported QueryRun v1 bundle.")).toBeVisible();
    await expect(page.getByText("Asha", { exact: true })).toBeVisible();
  }
});
