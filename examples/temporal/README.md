# A first temporal Kura experiment

These notes describe the preserved assistant-reviewed baseline. The current HeroUI app uses fresh GPT-6 Luna analysis; see the [repository README](../../README.md).

This report asks two questions: which conversation topics changed in share, and
which kept returning? It uses a fixed set of topic labels and real timestamps,
with one category per conversation and Monday–Sunday weeks in UTC.

## The selected histories

The original WildChat loader was extended to index timestamps and filter for
temporal coverage. A seeded shuffle (`42`) chose the first two usable English
browser groups with 30–100 chats, at least ten active weeks, at least 84 days of
coverage, and varied openings. Selection did not use topic labels or the amount
of apparent drift.

| Anonymous group | Recorded chats | First / last recorded chat | Active / calendar weeks |
| --- | ---: | --- | ---: |
| User 1 | 33 | Nov 27, 2023 – Feb 25, 2024 | 10 / 13 |
| User 2 | 89 | Jun 25, 2024 – Sep 24, 2024 | 14 / 14 |

The users have different calendar spans. Compare mode preserves calendar dates,
so its side-by-side bar positions do not imply simultaneous activity. Each user's
early/late comparison uses their own first and last four calendar weeks.

The sample's [selection manifest](sample/selection.json),
[conversations](sample/conversations.jsonl), and [topic labels](sample/labels.json)
are included. Browser headers and the source IP hashes are not included; each
group has a derived anonymous ID. Conversation text is the public dataset's
retained text and may still contain names or other details.

Source: [AllenAI WildChat-4.8M](https://huggingface.co/datasets/allenai/WildChat-4.8M),
licensed under [ODC-BY](https://opendatacommons.org/licenses/by/1-0/). The loader
keeps the first eight messages, shortens each message to 2,000 characters, and
excludes chats containing empty user turns. This is a partial observed history.
An IP/browser group can merge people on shared networks or split one person
after browser or network changes.

## What the sample suggests

These figures use the assistant-reviewed labels and compare chat shares in the
first and last four weeks, rather than raw activity counts:

| Group / topic | Early chats | Late chats | Share change |
| --- | ---: | ---: | ---: |
| User 1 / Software & bioinformatics | 8 of 12 | 10 of 12 | 66.7% → 83.3% |
| User 1 / Population health & statistics | 4 of 12 | 0 of 12 | 33.3% → 0% |
| User 2 / Rehab techniques & assessment | 5 of 21 | 16 of 26 | 23.8% → 61.5% |
| User 2 / Clinical concepts & study | 10 of 21 | 3 of 26 | 47.6% → 11.5% |
| User 2 / Correspondence & logistics | 6 of 21 | 7 of 26 | 28.6% → 26.9% |

Software remains a recurring focus for User 1, even as its share increases. User
2's recorded questions shift toward concrete rehabilitation techniques and
assessment, while correspondence stays at a similar share. This is descriptive
evidence from small windows; it does not establish enduring personal interests,
statistical significance, or the disappearance of a topic outside this sample.

## Labels and uncertainty

The sample has assistant-reviewed topic labels from the retained user turns. It
does not use a separately run Kura summarization or clustering model. Labels are
interpretive and provisional. Grammar-editing requests keep their underlying
medical or technical topic when one is clear; correspondence stays separate when
the request concerns messages, scheduling, or records. Clinical definitions and
quiz requests are separated from concrete treatment plans and assessments. This
distinction is an exploratory choice and can affect the apparent drift.

The label file contains the taxonomy descriptions, a complete chat-ID map, and
notes for mixed cases. Related colors group computing/biology, clinical topics,
and communication/work. Click any weekly segment to inspect its chats and notes.

For a freshly selected sample, `categories.py` supplies a separate keyword
baseline that scores distinct matching words in user messages. Its limitations
are visible in this dataset: grammar instructions can obscure an underlying
medical topic. Supply reviewed labels or Kura cluster assignments for better
topic comparisons. Never treat a change in classifier behavior as interest drift.

## Run or rebuild

```bash
# Standard-library-only rebuild of the bundled sample
python3 examples/temporal/run.py \
  --input examples/temporal/sample/conversations.jsonl \
  --assignments examples/temporal/sample/labels.json \
  --output examples/temporal/output/reviewed-sample

# Download another sample; Kura dependencies required
uv run python examples/temporal/run.py --users 2 --seed 7

# Inspect the keyword baseline on the same real sample
python3 examples/temporal/run.py \
  --input examples/temporal/sample/conversations.jsonl \
  --output examples/temporal/output/keyword-baseline
```

All reports are self-contained HTML. `profile.json` stores the weekly counts,
comparison windows, source checksum, labels, and conversations. The code rejects
duplicate chat IDs and missing category assignments, keeps empty weeks, and
suppresses drift deltas for overlapping or insufficiently populated windows.

The recurring-focus card prefers a topic with a similar share, then the most
active weeks, among topics with at least two chats in both windows. “Similar” is
within ten percentage points. Other/mixed topics are excluded from these cards.

## Next step toward temporal Kura

Run Kura's summarization and clustering on the combined histories, then map each
chat to one fixed parent topic for this temporal view. Preserve the hierarchy so
we can distinguish a stable domain from a shift within it, such as clinical
theory to treatment planning. Review representative chats and ambiguous labels
before comparing windows. Fit one taxonomy across the full retrospective sample;
independently clustering every week would make category movement uninterpretable.

The temporal aggregation is independent of how those labels are produced:

```python
from kura.temporal import build_temporal_profile

profile = build_temporal_profile(
    conversation_dicts,
    assignments={"chat-id": "fixed-topic-id"},
    window_weeks=4,
    min_window_chats=5,
)
```
