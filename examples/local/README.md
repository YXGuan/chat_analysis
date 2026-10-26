# Run Kura Locally

This folder runs the whole Kura pipeline on a set of chats, then opens an HTML
report you can explore. It defaults to headless Codex GPT-6 Luna. To import a
personal ChatGPT export with a date preview, use **Import history** in the main
app or `python -m kura.cli.cli import-history /path/to/export`. The older
API pipeline is available only with `--engine api`; for that option you
need an OpenAI API key.

| File                                | What it does                                                       |
| ----------------------------------- | ------------------------------------------------------------------ |
| `run.py`                            | Runs the pipeline and builds the report                            |
| `view.py`                           | Shows the reports you already have, without running anything again |
| `wildchat.py`                       | Picks real users from WildChat-4.8M and loads their chats          |
| `report.py`, `report_template.html` | Build the report                                                   |

## One-time setup

From the repo root:

```bash
uv sync --group visualization
source .venv/bin/activate
npm run setup:codex
.local/tools/node_modules/.bin/codex login
```

## Run it

```bash
# 190 made-up chats
python examples/local/run.py

# Every chat from 3 real English-speaking users in WildChat
python examples/local/run.py --dataset wildchat

# 2 different users
python examples/local/run.py --dataset wildchat --users 2 --seed 7
```

When the run ends, the report opens in your browser. Add `--no-open` to skip that.

## See your results without running again

```bash
# A page that lists every result, at http://localhost:8000
python examples/local/view.py

# Go straight to one result's report
python examples/local/view.py wildchat-3-english-users
```

This only shows results you already made. It doesn't summarize or cluster
anything, makes no model calls, and doesn't need an API key. It runs a small web
server that only this computer can reach. Press Ctrl+C to stop it. If port 8000
is busy, it uses the next free port and prints the address.

If a report is missing or older than its data, the viewer rebuilds it from the
saved files first, which takes about a second. You can also open any
`report.html` file directly, since it works without a server.

## The report

The report is one file, `report.html`, in the results folder. The data and
chart libraries are built into it, so it opens straight from disk. There is no
server and nothing to upload. (The first report downloads the D3 chart library
once.)

It shows the same clusters in 11 ways:

| View        | What it shows best                                                  |
| ----------- | ------------------------------------------------------------------- |
| List        | Every cluster as an outline. The easiest way to read names          |
| Tree        | A node-link tree. Each group branches into the clusters inside it   |
| Radial tree | The same branches in a circle, with base clusters around the edge   |
| Sunburst    | Rings from the center out. Slice width shows the number of chats    |
| Icicle      | Like the sunburst, but in columns, so names are easier to read      |
| Treemap     | Boxes sized by chats, inside the frame of their top-level group     |
| Circles     | Clusters as circles inside the circles of their groups              |
| Network     | A graph linking each user to the clusters they chat about           |
| Flow        | How each user's chats split into groups, then into smaller clusters |
| Map         | Kura's 2D map. Similar clusters sit close together                  |
| Table       | Every cluster with its numbers                                      |

Some things work the same in every view:

- **Colors.** Each user keeps one color everywhere. A cluster takes the color
  of the user with the most chats in it. Paler means the cluster mixes users.
- **Picking a user.** Use the buttons at the top to show only one user's chats.
  Every view, number, and list updates.
- **Details.** Click any cluster to see its description, the clusters inside
  it, and its chats. Open a chat to read it.
- **Bookmarks.** The address bar remembers the view and user, such as
  `report.html#view=sunburst&user=User%202`.

## How many levels?

Kura builds the tree from the bottom up:

1. It splits the chats into base clusters of about `--cluster-size` chats each.
2. It merges those clusters into bigger groups, adding one level each round.
3. It stops when there are at most `--top-clusters` groups at the top.

Both settings default to 5 here. More chats, or smaller settings, give more
levels. Kura's own defaults are 10 and 10, which gave only 2 levels for the 190
sample chats.

If you change these settings, the script runs the clustering steps again but
keeps the summaries.

## Running on WildChat

[WildChat-4.8M](https://huggingface.co/datasets/allenai/WildChat-4.8M) has 3.2
million real chats with ChatGPT, from April 2023 to July 2025. This version
leaves out toxic chats and hides personal details. Users are only known by a
hashed IP address and their browser details. The dataset card suggests
combining the two to link chats from the same person, and the script does that.

The full dataset is about 15 GB, so the script doesn't download it. The first
time, it reads only the user columns (about 170 MB). That takes 3 to 4 minutes,
and the result is saved in `output/.cache/`. To be picked, a user must:

- chat in a web browser (not a script calling the chatbot's API),
- have 30 to 100 chats,
- write at least 95% of their chats in the chosen language (`--language`), and
- start most chats differently, which skips scripted users.

The script then downloads only the chats of the users it picks, and labels them
User 1, User 2, and User 3.

### Finding users who chat about a topic

```bash
python examples/local/run.py --dataset wildchat --topic "science or physics research"
```

With `--topic`, the script picks the users whose work best matches the topic,
instead of picking at random:

1. It reads the first message of at least 3 chats from every user who could be
   picked. Chats can only be downloaded in chunks of about 1,000, so this reads
   about 370 chunks (1.7 GB) and takes about 5 minutes the first time. The
   messages are saved, so later searches, even for other topics, skip this step.
2. It ranks the users by how close those messages are to the topic, using
   OpenAI embeddings. This costs about a cent.
3. For the 60 closest users, the model reads 13 first messages each and writes
   one sentence about what that person mostly works on. These summaries don't
   depend on the topic, so they are saved too.
4. The model compares all 60 summaries and sorts people into strong matches and
   partial matches, such as people who only study the subject or do homework
   on it. It does this 5 times, with the people in a different order each
   time. Only people who are strong matches in most of these votes are kept,
   best first.
5. The script loads all chats of the best matches.

The summary sentence is printed as each user is picked, and it appears on the
user's card in the report. Some of a picked user's chats will still be about
other things, and the report shows you which ones. Results go in a folder such
as `output/wildchat-3-english-users-about-science-or-physics-research/`.

The words you use matter. For example, "science research" may also find social
science, while "physics or chemistry research" won't.

Some things to know:

- The same `--seed` always picks the same users. Change it to get new ones.
- Each chat keeps only its first 8 messages. Each message is cut to 2,000
  characters, and cut text ends with `... [shortened]`.
- Chats with an empty user message are skipped.
- Hugging Face allows 3,000 file lookups per 5 minutes. The script looks up each
  file once and reads the rest straight from the download server.
- A "user" is one hashed IP address with one exact set of browser details. If
  someone's browser details change, for example after a browser update, their
  chats split into more than one user. Each picked user's chats all come from
  the same person, but they may not be all of that person's chats.

## Where results go

Each sample and model gets its own folder, such as
`examples/local/output/wildchat-3-english-users/gpt-6-luna/`:

| File                   | What it holds                     |
| ---------------------- | --------------------------------- |
| `report.html`          | The report                        |
| `conversations.jsonl`  | The chats                         |
| `summaries.jsonl`      | One short summary per chat        |
| `clusters.jsonl`       | The base clusters                 |
| `meta_clusters.jsonl`  | The clusters combined into a tree |
| `dimensionality.jsonl` | The tree with 2D map positions    |
| `settings.json`        | The clustering settings used      |

Running the script again reuses these files, so it finishes in seconds. To start
over, delete that folder.

For the legacy API pipeline, explicitly add `--engine api` and set
`OPENAI_API_KEY` in your terminal. Topic-based WildChat sampling still requires
that explicit API option.

## Using another model

`--engine api --model` takes an OpenAI API model name, such as `--model gpt-4.1-mini`. Kura adds
the request settings GPT-6 Luna needs on its own.

## A note on the main README example

The main README passes `model=cluster_model` to
`generate_base_clusters_from_conversation_summaries`. That function expects
`clustering_model=` instead. It silently ignores `model=` and falls back to its
default model. `run.py` uses the correct name.
