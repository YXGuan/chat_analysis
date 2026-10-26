# Chat Analysis UI

A React 19 and HeroUI v3 interface for the saved GPT-6 Luna analyses in
`public/data/`. It includes a stacked activity chart with day, one-week,
two-week, and calendar-month groupings, two hierarchy levels,
a combined cluster and conversation explorer with List, Tree, Flow, and Circle
views, search, and light/dark themes. Legacy `view=conversations` links open the
combined explorer.

Click chart labels to hide or show themes and topics, or use **Show all** to
restore them. Hidden themes also hide their topics. Counts, shares, changes,
and linked conversations use visible chats while the original date span stays
fixed. Visibility is saved per dataset in browser storage; grouping is saved in
browser storage and the URL. Empty periods remain visible, and clicking a bar
opens its exact conversations. Change comparisons retain four-week windows.

Run `npm test` with Node.js 22.6+ to check calendar boundaries, aggregation,
visibility, and comparison calculations using synthetic data.

```bash
cd ..
npm run dev
```

`npm run build` type-checks the entire UI and writes the production app to
`../kura/static/dist`. `src/TemporalApp.tsx` is the entry point; the original
copied Kura uploader remains in `src/App.tsx`.

HeroUI's official agent skill and documentation scripts live in
`../.agents/skills/heroui-react`. The project uses the v3 compound component APIs,
Tailwind v4, semantic theme variables, and React Aria keyboard interactions.

Use **Import history** to preview and analyze a native ChatGPT export. The Vite
server proxies `/api` to the loopback import service on port 8014. Imports use
headless Codex GPT-6 Luna by default and are stored in ignored `.local/kura/`,
not in the public data folder. The UI reads saved analysis while browsing. See the [repository README](../README.md) for the
model provenance, dataset attribution, and commands to rebuild analysis exports.
