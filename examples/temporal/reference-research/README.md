# Example Result: 3 WildChat Users Who Do Science Research

This folder holds one finished Kura run. It covers every chat from 3 real
people in WildChat whose chats are mostly about science or physics research.
The report is in `gpt-6-luna/report.html`.

## How to see it

From the repo root, with the virtual environment active:

```bash
python examples/local/view.py wildchat-3-english-users-about-science-or-physics-research
```

This opens the report at http://localhost:8000. It needs no API key and makes
no model calls.

You can also open `gpt-6-luna/report.html` straight from disk. GitHub shows
the file as code instead of a page, so download it first if you are on GitHub.

## How it was made

It was made on October 22, 2026, with the code in commit `cc0803c`. Setup,
from the repo root:

```bash
uv sync --group visualization
source .venv/bin/activate
export OPENAI_API_KEY=sk-...
```

Then this one command:

```bash
python examples/local/run.py --dataset wildchat --topic "science or physics research"
```

Every other option kept its default:

| Option | Value |
| --- | --- |
| `--users` | 3 |
| `--language` | English |
| `--model` | gpt-6-luna |
| `--cluster-size` | 5 |
| `--top-clusters` | 5 |

## What the script did

1. It found 1,462 WildChat users who have 30 to 100 chats, mostly in English.
2. It ranked them by how close their first messages are to "science or
   physics research", using OpenAI embeddings.
3. For the 60 closest users, GPT-6 Luna read 13 first messages each and wrote
   one sentence about what that person mostly works on.
4. GPT-6 Luna compared the 60 sentences 5 times, with the people in a
   different order each time. 5 people were strong matches in most rounds.
5. The script kept the best 3 and loaded all of their chats.
6. Kura summarized the 120 chats, grouped them into 24 base clusters, and then
   merged those into 11, then 6, and then 3 top-level groups.

The [main README](../../README.md#finding-users-who-chat-about-a-topic) explains
these steps in more detail.

## The 3 users

| User | Chats | Dates | Country | What they mostly work on |
| --- | --- | --- | --- | --- |
| User 1 | 40 | Nov 29, 2023 to Feb 22, 2024 | Peru | Computational genomics and bioinformatics: sequencing data, genome assembly and alignment, and scripts in Python, shell, and Rust |
| User 2 | 44 | Sep 22, 2024 to Sep 29, 2024 | Poland | Material Point Method (MPM) physics simulations in Taichi and C++, including Eigen and OpenGL versions |
| User 3 | 36 | Apr 25, 2023 to Apr 28, 2023 | Saudi Arabia | MATLAB traffic-flow simulations, such as the Krauss, Gipps, and IDM car-following models |

The "works on" sentences were written by GPT-6 Luna. They also appear on each
user's card in the report.

## The top-level groups

| Group | Chats |
| --- | --- |
| Build and visualize traffic and material simulations | 81 |
| Debug and optimize computational genomics code | 23 |
| Get help with Linux tasks, work emails, and laptop chargers | 16 |

The last group shows that some of these people's chats are not about their
research.

## Files

| File | What it holds |
| --- | --- |
| `gpt-6-luna/report.html` | The report, with the data and chart code built in |
| `gpt-6-luna/conversations.jsonl` | The 120 chats |
| `gpt-6-luna/summaries.jsonl` | One short summary per chat |
| `gpt-6-luna/clusters.jsonl` | The 24 base clusters |
| `gpt-6-luna/meta_clusters.jsonl` | The clusters combined into a tree |
| `gpt-6-luna/dimensionality.jsonl` | The tree with 2D map positions |
| `gpt-6-luna/settings.json` | The clustering settings used |

## Running it again

Because these files are saved, running the same command reuses them. It
rebuilds the report in seconds, but it still asks for an API key. To make the
result again from the start, delete the `gpt-6-luna` folder first. The first
full run downloads part of WildChat, which can take 10 minutes or more.

A new run might not give exactly the same users or clusters, because model
answers can change a little from run to run. `--seed` makes no difference when
you use `--topic`.

## Where the data comes from

The chats come from
[WildChat-4.8M](https://huggingface.co/datasets/allenai/WildChat-4.8M) by the
Allen Institute for AI, shared under the
[ODC-BY license](https://opendatacommons.org/licenses/by/1-0/). The dataset
hides personal details. Users are known only by a hashed IP address and
browser details, and these files leave out both. Each chat keeps only its first
8 messages, and each message is cut to 2,000 characters.
