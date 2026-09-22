# GhostQA dashboard design

Living notes for the presentation layer. Do not change research semantics
to make the UI look better.

## Concept

Technical editorial research workspace.

The dashboard is a tool built by an engineering/research team that also
has to present clearly to judges. Overview and Evidence read like a lab
notebook with a grid. Live is denser and more like an instrument panel.

Personality comes from type hierarchy, paper/graphite surfaces, and a
single restrained teal accent. It does not come from scanlines, neon
borders, or a HUD costume.

## Theme

Root attribute: `html[data-theme="light"| "dark"]`.

- Persistence key: `localStorage.ghostqa-theme`
- First visit with no saved choice: `prefers-color-scheme`, else light
- Explicit user choice is not overwritten on refresh
- Inline head script sets `data-theme` before stylesheet paint
- `meta[name="theme-color"]` follows the active theme
- Cytoscape styles read CSS variables and restyle on theme change

Light: warm paper background, near-white surfaces, ink text, teal accent,
amber only for warnings and defect marks.

Dark: graphite, muted teal, crisp text, no neon glow, no CRT overlay.

## Token roles

Colors live in `static/styles/tokens.css`. Components consume roles:

`--bg`, `--bg-subtle`, `--surface`, `--surface-2`, `--surface-raised`,
`--text`, `--text-strong`, `--muted`, `--line`, `--line-strong`,
`--accent`, `--accent-hover`, `--accent-dim`, `--on-accent`,
`--success`, `--warning`, `--danger`,
`--graph-node`, `--graph-label`, `--graph-edge`,
`--graph-new`, `--graph-similar`, `--graph-identical`,
`--graph-flagged`, `--graph-active`, `--shadow-*`.

Do not spread raw hex through component CSS or Cytoscape styles.

## Typography

IBM Plex Sans + Noto Sans SC for UI and Chinese prose.
IBM Plex Mono for IDs, metrics, commands, versions, state names.

Chinese headings use the body sans, not a display/sci-fi face.
Body reading text is at least 16px on small screens.

## Surfaces

Prefer section rhythm, dividers, and one raised panel where it helps.
A border around every paragraph is not the system.

Buttons: primary, ghost, quiet/icon. Hover 150–200ms. No neon CTA.

## Copy voice

Write like a person on the team explaining the work.

- Concrete verbs and numbers from published artifacts
- Domain English is fine (return phase, ddmin, manifest)
- No “不只是 / 不仅…还”, no platform slogans, no “AI 驱动全流程”

v0.3.9 is Outcome A on an inspected BuggyShop mechanism plus DeepBench
historical regression. Do not imply holdout generalization.

v0.3.8 may say the return loop is enough to explain that coverage lock.
It may not claim fingerprint explosion is disproven everywhere.

## Anti-patterns

- cyberpunk / sci-fi HUD / scanlines / neon-on-black as identity
- purple SaaS gradients, glassmorphism stacks, giant marketing heroes
- all-monospace UI, card soup, KPI sales tiles
- dark-only Cytoscape or inline SVG
- emoji as icons

## QA matrix

Check both themes at 1920×1080, 1440×900, 1366×768, 1024×768,
430×932, 390×844, 375×812.

Also: theme persistence, hard reload, reduced motion, Live run with a
theme switch after the graph has nodes, no horizontal overflow, focus
visible, theme button ≥44×44.
