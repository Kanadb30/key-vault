---
name: SQL Compiler Query Workbench
description: A navy, light-surface, teal-accented compiler inspector.
colors:
  nav: "#172b3a"
  surface: "#fff"
  text: "#1d303e"
  muted: "#556774"
  rule: "#d8e1e7"
  accent: "#006c7b"
  accent-light: "#e8f4f5"
  success: "#226444"
  failure: "#a32b35"
  workspace: "#f2f5f7"
  control-rule: "#c5d1d9"
  accent-hover: "#005664"
  focus: "#007c92"
  code-surface: "#f5f8fa"
typography:
  title: {fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: "1.625rem", fontWeight: 650, lineHeight: 1.25, letterSpacing: "-.025em"}
  title-mobile: {fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: "1.5rem", fontWeight: 650, lineHeight: 1.25, letterSpacing: "-.025em"}
  section-title: {fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: ".9375rem", fontWeight: 650}
  body: {fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: ".8125rem", fontWeight: 400}
  label: {fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: ".75rem", fontWeight: 400}
  button: {fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: ".8125rem", fontWeight: 600}
  button-compact: {fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', fontSize: ".75rem", fontWeight: 600}
  code: {fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace', fontSize: ".8125rem", lineHeight: 1.8}
  editor: {fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace', fontSize: ".8125rem", lineHeight: 1.85}
  editor-mobile: {fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace', fontSize: ".75rem", lineHeight: 1.85}
  plan: {fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace', fontSize: ".8125rem", lineHeight: 1.95}
  plan-mobile: {fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace', fontSize: ".75rem", lineHeight: 1.95}
rounded:
  square: "0"
  tag: "3px"
  control: "4px"
  panel: "5px"
  circle: "50%"
spacing:
  "4": "4px"
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "20": "20px"
components:
  button-primary: {backgroundColor: "{colors.accent}", textColor: "{colors.surface}", typography: "{typography.button}", rounded: "{rounded.control}", padding: "9px 15px"}
  button-primary-hover: {backgroundColor: "{colors.accent-hover}"}
  button-secondary: {backgroundColor: "{colors.surface}", textColor: "{colors.text}", typography: "{typography.button}", rounded: "{rounded.control}", padding: "9px 15px"}
  button-secondary-compact: {backgroundColor: "{colors.surface}", textColor: "{colors.text}", typography: "{typography.button-compact}", rounded: "{rounded.control}", padding: "8px 11px"}
  input-sql: {typography: "{typography.editor}", rounded: "{rounded.square}", padding: "18px"}
  select-preset: {backgroundColor: "{colors.surface}", textColor: "{colors.text}", typography: "{typography.label}", rounded: "{rounded.control}", padding: "7px 25px 7px 9px"}
  nav-item: {rounded: "{rounded.control}", padding: "11px 10px"}
  plan-tag: {backgroundColor: "{colors.code-surface}", rounded: "{rounded.tag}", padding: "3px 6px"}
  result-panel: {backgroundColor: "{colors.surface}", rounded: "{rounded.panel}"}
  stage-button: {padding: "16px 7px 17px"}
  plan-pair: {backgroundColor: "{colors.surface}", typography: "{typography.plan}"}
---

# Design System: SQL Compiler Query Workbench

## Overview

**Creative North Star: "Query workbench"**

A familiar Kibana-style workbench: navy navigation, white working surfaces, cool-gray dividers, and teal actions. The light workspace supports a projector-friendly compiler walkthrough. Density serves inspection rather than dashboard decoration.

This records the implemented console, not a new identity proposal. The confirmed workbench direction overrides seed `8c05e545`; system sans and code-focused monospace are intentional brief-pinned choices.

**Key Characteristics:**
- Light, bordered working surfaces against navy navigation.
- Compact interface text with spacious, scrollable compiler artifacts.
- Explicit selection, execution status, and evidence provenance.

## Colors

### Primary
Teal `accent` identifies Run, selected compiler stages, artifact disclosures, and rewrite cues. `accent-hover` deepens the primary action; `accent-light` distinguishes the optimized plan tag.

### Neutral
`nav` anchors navigation. `workspace` separates white `surface` panels without shadows. `text` carries primary content; `muted` carries supporting labels. `rule` divides surfaces and `control-rule` outlines controls. `code-surface` provides quiet backing for line numbers, tags, and SQL evidence.

Sidecar tonal ramps are generated preview aids, not additional shipped palette tokens.

### Status and focus
`success` and `failure` communicate execution and verification outcomes. Stale evidence uses amber; diagnostics use pale red surfaces. `focus` is the light-workspace keyboard outline; navy navigation uses a lighter cyan outline.

**The Visible State Rule.** Pair status color with labels or symbols; retain the selected-stage underline and keyboard focus outline.

## Typography

Use the frontmatter's system sans stack for interface text. Monospace belongs to SQL, plans, AST/JSON artifacts, schema identifiers, and numeric result cells—not headings or navigation. There is no display face or external font dependency.

The hierarchy is deliberately short: title, section title, body, and label. Buttons use semibold text; stage labels are also semibold. Small timing, provenance, and schema annotations are subordinate metadata, not a body-text template. Metrics use semibold tabular figures; tables preserve numeric alignment.

**The Plan Readability Rule.** Keep plans at the `plan` role on desktop (13px) and `plan-mobile` role at the mobile breakpoint (12px), with preserved whitespace and horizontal scrolling. Do not shrink code to force it into a pane.

## Layout

The desktop shell has a schema/navigation rail (214px) and a fluid workspace capped at 1760px. Workspace padding is 30px vertically at the top and 34px horizontally. Within it, source precedes the stage strip and inspector; measured work and result/verification panels follow. These are the current console's composition, not mandatory sections for every future surface.

Seven stage controls share the available width. Plans occupy equal columns; results use a narrower rows panel and wider verification panel (0.85:1.15). Internal rules, compact toolbars, and repeated small gaps establish density; panel padding varies by context rather than following an invented uniform card grid.

- At 1600px and above, workspace padding expands.
- At 1190px and below, the rail narrows to 190px, stage contents become vertical, and execution-trace panes stack.
- At 900px and below, navigation becomes a top band, the data section stacks full width, runtime status remains visible, and plans stack.
- At 620px and below, workspace gutters become 14px, header actions share the row, toolbars wrap, results stack, and the stage strip scrolls horizontally. The selected stage is brought into view. SQL and plans scroll within their own regions.
- The document supports a minimum viewport width of 320px.

## Elevation & Depth

The interface has no box shadows. Navy/light contrast, white panels, thin borders, and restrained tinted evidence regions establish depth. Hover changes surface or border color without lifting controls. Buttons transition background and border color over 150ms; reduced-motion preferences remove transitions.

## Shapes

Panels are gently squared using `panel` corners; controls use `control`, and compact plan tags use `tag`. Editor interiors remain square. Stage numbers and the connection indicator are circular. One-pixel borders separate regions; the active stage has a stronger bottom rule. Icons are inline, round-capped SVG strokes, normally 18px with a 1.6-unit stroke, not font glyphs.

## Components

- **Buttons:** Teal primary Run; white, outlined secondary bundle actions, including a compact variant. Standard controls have a 40px minimum height; compact controls use 36px. Hover darkens teal or strengthens the secondary border. Disabled buttons reduce opacity and use an unavailable cursor. A running query changes the Run label and disables repeat submission.
- **SQL editor and preset field:** A native resizable textarea with a separate line-number gutter, plus a labeled native select. The editor preserves whitespace and uses an inset focus outline. Desktop editor height starts at 164px; vertical resizing is bounded. The select and textarea retain accessible names.
- **Navigation and catalog:** The selected frontend uses a lighter navy plate and border. SQL, Builder, Natural language, and Elastic DSL are implemented; frontend changes are disabled during compilation. Desktop schema entries use native disclosures. The data section stays reachable at every width: the preloaded dataset, per-table add-row forms, and reset are part of the primary navigation, not a modal. Mobile keeps the section visible, not runtime truth: available fixture storage and the actual Rust connection state remain explicit.
- **Data controls:** The dataset picker, per-table row form, JSON paste, and reset reuse the same control borders and focus treatment as the rest of the workbench. Inline validation errors appear where the user typed; the evidence bar flags "Data changed since this run" instead of silently discarding recorded evidence.
- **Builder and storage selection:** Native labeled selects, checkboxes, and typed filter fields inherit the same control borders, spacing, and focus treatment. Ordered projection and AND filters are visible. Storage is chosen explicitly; an unavailable engine option is disabled rather than substituted silently. Generated SQL and NL catalog-lowering evidence are inspectable below the input; the inspector distinguishes the NL surface AST from the lowered shared query AST.
- **Stage strip:** Numbered buttons show stage labels, status, and timing. Selection combines teal text, a pale fill, and bottom rule; failures show an alert symbol, while skipped stage markers use dashed borders. Buttons expose pressed state and control the artifact region.
- **Plans and tags:** Original and optimized plans remain comparable, with labeled panes and passive bordered tags. Matching predicate lines receive a pale teal highlight. The rewrite-evidence band explains movement and node provenance below both panes.
- **Result and verification panels:** White bordered containers with separated headers. Tables use muted header bands, thin row rules, horizontal overflow, and a subtle row hover. Verification combines a status icon/text, concise explanation, and inset SQL evidence; it is not a decorative success card.
- **Diagnostics and empty/loading states:** Red-tinted alerts include source evidence and a Locate action when available; the source span uses a wavy underline as well as color. Connection errors offer Retry. Empty artifacts explain what was not produced; loading uses static placeholder bars and text. Stale/replayed evidence stays explicitly labeled.

## Do's and Don'ts

### Do:
- **Do** preserve the light workbench, navy navigation, and restrained teal action hierarchy.
- **Do** retain readable, scrollable plans and the labeled before/after comparison.
- **Do** expose focus, status labels, and the provenance of displayed evidence.
- **Do** distinguish the selected storage backend and actual runtime engine availability.

### Don't:
- **Don't** turn this compiler inspector into a marketing page or an unsupported metrics dashboard.
- **Don't** use monospace for interface headings or shrink code to avoid overflow.
- **Don't** hide stale, failed, skipped, or unavailable states behind success styling.
- **Don't** add decorative shadows, gradients, or display typography absent from this implemented world.
