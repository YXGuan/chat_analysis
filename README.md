# Temporal Kura

Explore what changes in someone's recorded questions and what keeps returning.
The app combines weekly timelines with a cluster explorer and source conversations.
Import your own ChatGPT history, or try the included WildChat samples.
Cluster views are List, Tree, Flow, and Circle.

The interface uses HeroUI v3 React components, its semantic design tokens, light
and dark themes, and React Aria interactions. HeroUI's official React agent skill
and documentation helpers are installed in
[.agents/skills/heroui-react](.agents/skills/heroui-react/SKILL.md).

## Open the app

From the repository root:

```bash
uv sync --group dev
npm --prefix ui ci
npm run setup:codex
.local/tools/node_modules/.bin/codex login
npm run dev
```

Open the localhost address printed by Vite. This starts the UI and the local
import service on `127.0.0.1:8014`. Browsing saved data makes no model calls.
If you already signed in to Codex on this computer, that login is reused.
The repo installs its own compatible Codex CLI, pinned to **0.163.0**, without
changing the system installation.

For a production build, run `npm run build`, then
`.venv/bin/python -m kura.cli.cli start-app`. Open `http://127.0.0.1:8014`.
A static file server can show the public examples, but uploads and private
histories require the local service.

## Import your ChatGPT history

Click **Import history** in the header. Choose the original export ZIP, the
extracted export folder, `conversations.json`, or all of the
`conversations-*.json` shards. You can also enter an export path on this computer.
ChatGPT exports are available through Settings → Data controls → Export data.

Preview the conversation count and choose a period. The default is the latest
**three calendar months in the export**, anchored to its latest conversation
creation date, rather than today's date. The boundary day is included. You can
choose one month, six months, a year, or all history instead. Name the dataset,
then select **Analyze my history**. The dialog shows progress by batch; it can be
closed while processing and reconnects after a page reload. When analysis
finishes, open your timeline. Saved imports appear in the dataset selector.

The importer follows the selected conversation branch and preserves visible
user and assistant text. The model reads user messages only. Image, audio,
attachment-only chats, hidden reasoning, and alternative branches are excluded;
the preview reports chats with no readable user text. Native source IDs and
full retained text remain available in the conversation reader.

Private normalized exports, model checkpoints, and profiles are kept in the
ignored `.local/kura/` directory, outside `ui/public/` and the built static files.
Readable user text is sent to OpenAI through your Codex login for analysis.
The originals are never modified. Model errors leave the import intact; retry
reuses valid completed batches for the same source and model.

The same workflow is available from the command line:

```bash
.venv/bin/python -m kura.cli.cli import-history /path/to/chatgpt-export \
  --months 3 --name "My ChatGPT history"
```

Add `--prepare-only` to preview and save the import without contacting a model.
There is no API key or provider choice to configure for the default workflow.

## Included example datasets

| Dataset            | Chats | Users | GPT-6 Luna hierarchy         |
| ------------------ | ----: | ----: | ---------------------------- |
| Personal histories |   122 |     2 | 4 themes, 14 specific topics |
| Science & physics  |   120 |     3 | 5 themes, 12 specific topics |

Personal histories keeps the original two users selected for longitudinal
coverage. Science & physics imports the conversations from the reference at
`examples/temporal/reference-research/gpt-6-luna`.
GPT-6 Luna independently reanalyzed both sets from retained **user** messages;
this app does not reuse the earlier assistant-reviewed labels or the reference
run's original cluster assignments.

Switch between broad themes and specific topics in the weekly chart. Counts show
activity; shares compare topic mix. Empty weeks remain visible. Click a segment
to read its chats, or open Topics to explore the clusters as a list, tree, flow,
or nested circles. Source conversations stay beside the selected cluster.

Changes compare each user's first and last four calendar weeks, with at least
five chats in each non-overlapping window. Some research users have only a few
days of data; their drift deltas are suppressed. Category assignments remain
fixed across every week. The app's analysis dialog explains the descriptive
recurrence rules and limitations.

## Analysis model and provenance

The repository defaults to **headless `codex exec` with `gpt-6-luna` and low
reasoning effort**. The adapter prefers `KURA_CODEX_BIN`, then the compatible
project-local CLI, then PATH. It uses ephemeral execution, a read-only sandbox,
no web access or model tools, and structured JSON output from a clean temporary
working directory. Model or account errors are shown explicitly; a different
model is never selected as a fallback. `examples/local/run.py` also defaults to
this adapter; the older OpenAI API pipeline requires `--engine api` explicitly.

The first pass discovers one fixed two-level hierarchy across the whole selected
period, with a bounded text excerpt from every chat. Subsequent batches receive
full user text and use schema-enforced topic IDs and deterministic short chat
IDs. Every batch must cover exactly its source chats, and final counts must
agree at both hierarchy levels. Native IDs are restored before export.

The included public samples were analyzed earlier by GPT-6 Luna agents within
a Codex session. New imported histories use the verified project-local headless
CLI and record `execution: local-codex-cli`. These are hosted model calls through
Codex, not on-device inference.

Raw model results are in [data/analysis](data/analysis). The UI's saved data is in
[ui/public/data](ui/public/data), including model and execution route, input and
analysis checksums, complete assignments, summaries, confidence, source chats,
and counts at both hierarchy levels. Confidence is model-reported and
uncalibrated. Labels are interpretive; individual mixed cases include notes.

To rebuild the UI data from the saved Luna results without another model call:

```bash
.venv/bin/python examples/temporal/codex_analysis.py \
  --input examples/temporal/sample/conversations.jsonl \
  --import-analysis data/analysis/personal.gpt-6-luna.json \
  --output ui/public/data/personal.json \
  --work-dir .cache/codex-analysis/personal

.venv/bin/python examples/temporal/codex_analysis.py \
  --input examples/temporal/reference-research/gpt-6-luna/conversations.jsonl \
  --import-analysis data/analysis/research.gpt-6-luna.json \
  --output ui/public/data/research.json \
  --work-dir .cache/codex-analysis/research
```

The compatibility script also uses the headless adapter when `--import-analysis`
is omitted. `--prepare-only` writes the prompt and schema without contacting a
model. See [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive)
for the structured-output execution interface.

## Data and interpretation

Data comes from [AllenAI WildChat-4.8M](https://huggingface.co/datasets/allenai/WildChat-4.8M)
under [ODC-BY](https://opendatacommons.org/licenses/by/1-0/). User groups combine
hashed IP and browser details; they can merge people on shared networks or split
one person's activity. The histories are incomplete. The loader retains the
first eight messages and shortens each to 2,000 characters. Text may contain
personal details despite the source's redaction.

The original Kura codebase was adapted from the upstream Kura checkout at commit
`cc0803c6c4561c9ad76009426f565a8fb0314f95`; see [README.kura.md](README.kura.md).
The original UI source remains in `ui/src/App.tsx`; the temporal app enters via
`ui/src/TemporalApp.tsx`.

The earlier [standalone bar-chart prototype](examples/temporal/sample/report.html)
and [baseline notes](examples/temporal/README.md) are preserved with their original
assistant-reviewed labels. They are separate from the new Luna analysis.

## Validation

Before publishing changes, run `python3 scripts/check_publication.py` and install
the commit checks with `.venv/bin/pre-commit install`. The privacy workflow scans
files and Git history with Gitleaks, including a Logfire credential rule. Private
exports, caches, credentials, databases, and generated reports stay ignored.
The bundled public WildChat samples are intentionally included. See the
[publication audit](docs/publication-audit.md) for the scope and findings.

```bash
.venv/bin/pytest tests/ -q
cd ui
npm run build
```

Model-output validation rejects missing or invented chats, duplicate assignments,
invalid hierarchies, invalid confidence ranges, and missing or duplicate users.
Both hierarchy levels must conserve the source chat counts and match checksums.
