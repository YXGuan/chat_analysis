"""Pick a few real users from WildChat-4.8M and load all of their chats.

WildChat-4.8M has 3.2 million real ChatGPT conversations (non-toxic only) in 86
parquet files, about 15 GB in total. Users are only known by a hashed IP address
and their browser details. The dataset card suggests combining the two to link
chats from the same person, which is what this does.

The first run reads just those columns for every chat (about 170 MB, 3 to 4
minutes) and saves the users who have a good number of chats. Later runs reuse
that list and download only the chats of the users they pick.
"""

import asyncio
import hashlib
import io
import json
import random
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

import instructor
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import requests
from pydantic import BaseModel, Field

from kura.embedding import OpenAIEmbeddingModel
from kura.types import Conversation, Message
from kura.utils import get_model_request_kwargs

DATA_URL = "https://huggingface.co/datasets/allenai/WildChat-4.8M/resolve/main/data"
NUM_FILES = 86
MIN_CHATS = 30  # fewer chats don't give clustering much to work with
MAX_CHATS = 100  # more are often scripts, and cost more to summarise
MIN_LANGUAGE_SHARE = 0.95  # share of a user's chats that must be in the chosen language
MIN_DISTINCT_OPENINGS = 0.7  # share of chats that must start differently (skips scripts)
# With a topic, the model has already read what each user works on, and people often
# re-send the same code or question, so more repeats are allowed
MIN_DISTINCT_OPENINGS_TOPIC = 0.25
MIN_USABLE_CHATS = 20  # after dropping chats with empty messages
MAX_MESSAGES = 8  # later turns are dropped to keep LLM costs predictable
MAX_MESSAGE_CHARS = 2000  # long messages (pasted code, essays) are cut to this
TOPIC_SAMPLE = 3  # chats read from every candidate to rank them by topic
TOPIC_SHORTLIST = 60  # best-ranked users who get a closer look
TOPIC_CHECK = 13  # chats per shortlisted user that the model reads
TOPIC_VOTES = 5  # times the model picks matches, with users in a different order each time
USER_KEY = ["hashed_ip", "user_agent", "accept_language"]
CHAT_COLUMNS = ["timestamp", "model", "language", "country", "turn", "redacted", "conversation"]

_local = threading.local()


def _session() -> requests.Session:
    """Return this thread's HTTP session, so connections get reused."""
    if not hasattr(_local, "session"):
        _local.session = requests.Session()
    return _local.session


def _get_range(url: str, start: int, end: int) -> bytes:
    """Download bytes start to end - 1 of a file, retrying brief network errors."""
    headers = {"Range": f"bytes={start}-{end - 1}"}
    for wait in (1, 2, 4):
        try:
            response = _session().get(url, headers=headers, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            time.sleep(wait)
    response = _session().get(url, headers=headers, timeout=60)
    response.raise_for_status()
    return response.content


class HttpRangeFile(io.RawIOBase):
    """A read-only file that downloads only the bytes that are read."""

    def __init__(self, url: str, size: int) -> None:
        super().__init__()
        self.url, self.size, self.pos = url, size, 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        self.pos = base + offset
        return self.pos

    def read(self, size: Optional[int] = -1) -> bytes:
        end = self.size if size is None or size < 0 else min(self.size, self.pos + size)
        if end <= self.pos:
            return b""
        data = _get_range(self.url, self.pos, end)
        self.pos = end
        return data


def _resolve(file_index: int) -> tuple[str, int]:
    """Return the direct download link and size of one data file.

    Hugging Face allows 3,000 of these lookups per 5 minutes, so each file is
    looked up once and then read through its direct link.
    """
    url = f"{DATA_URL}/train-{file_index:05d}-of-{NUM_FILES:05d}.parquet"
    response = _session().head(url, allow_redirects=False, timeout=30)
    response.raise_for_status()
    if "location" in response.headers:
        return response.headers["location"], int(response.headers["x-linked-size"])
    return url, int(response.headers["content-length"])


def _scan_users(cache_path: Path, include_timestamps: bool = False) -> pa.Table:
    """Find every browser user with MIN_CHATS to MAX_CHATS chats and save where their chats are."""
    print("Finding WildChat users. This reads about 170 MB and takes 3 to 4 minutes, but only once.")
    with ThreadPoolExecutor(16) as pool:
        links = list(pool.map(_resolve, range(NUM_FILES)))
        metas = list(pool.map(lambda link: pq.ParquetFile(HttpRangeFile(*link)).metadata, links))
    chunks = [(f, rg) for f, meta in enumerate(metas) for rg in range(meta.num_row_groups)]

    def read_chunk(chunk: tuple[int, int]) -> pa.Table:
        f, rg = chunk
        parquet = pq.ParquetFile(HttpRangeFile(*links[f]), metadata=metas[f], pre_buffer=True)
        columns = ["language", "hashed_ip", "header"]
        if include_timestamps:
            columns.append("timestamp")
        table = parquet.read_row_group(rg, columns=columns)
        header = table.column("header").combine_chunks()
        n = table.num_rows
        data = {
            "file": pa.array([f] * n, pa.int16()),
            "row_group": pa.array([rg] * n, pa.int16()),
            "row": pa.array(range(n), pa.int32()),
            "hashed_ip": pc.fill_null(table.column("hashed_ip"), ""),
            "user_agent": pc.fill_null(header.field("user-agent"), ""),
            "accept_language": pc.fill_null(header.field("accept-language"), ""),
            "language": pc.fill_null(table.column("language"), ""),
        }
        if include_timestamps:
            data["timestamp"] = table.column("timestamp")
        return pa.table(data)

    parts = []
    with ThreadPoolExecutor(32) as pool:
        for done, part in enumerate(pool.map(read_chunk, chunks), 1):
            parts.append(part)
            if done % 500 == 0 or done == len(chunks):
                print(f"  read {done} of {len(chunks)} chunks")
    index = pa.concat_tables(parts)

    # People chat in a web browser; scripts that called the chatbot's API don't
    index = index.filter(
        pc.and_(
            pc.starts_with(index["user_agent"], pattern="Mozilla/"),
            pc.not_equal(index["hashed_ip"], ""),
        )
    )
    counts = index.group_by(USER_KEY).aggregate([("row", "count")])
    counts = counts.filter(
        pc.and_(
            pc.greater_equal(counts["row_count"], MIN_CHATS),
            pc.less_equal(counts["row_count"], MAX_CHATS),
        )
    )
    users = index.join(counts.select(USER_KEY), keys=USER_KEY, join_type="inner")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(users, cache_path)
    return users


def _read_rows(
    spots: pd.DataFrame,
    links: dict[int, tuple[str, int]],
) -> list[dict[str, Any]]:
    """Download the given rows, reading only the chunks that hold them."""
    wanted: dict[tuple[int, int], list[int]] = {}
    for f, rg, row in spots[["file", "row_group", "row"]].itertuples(index=False):
        wanted.setdefault((int(f), int(rg)), []).append(int(row))
    for f in {f for f, _ in wanted}:
        if f not in links:
            links[f] = _resolve(f)

    def read_chunk(chunk: tuple[int, int]) -> list[dict[str, Any]]:
        f, rg = chunk
        parquet = pq.ParquetFile(HttpRangeFile(*links[f]), pre_buffer=True)
        table = parquet.read_row_group(rg, columns=CHAT_COLUMNS)
        return table.take(wanted[chunk]).to_pylist()

    with ThreadPoolExecutor(8) as pool:
        return [row for rows in pool.map(read_chunk, wanted) for row in rows]


def shorten(text: str) -> str:
    """Cut text to MAX_MESSAGE_CHARS and mark where it was cut."""
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    return text[:MAX_MESSAGE_CHARS] + " ... [shortened]"


def to_conversation(row: dict[str, Any], user: str) -> Optional[Conversation]:
    """Turn one WildChat row into a Kura Conversation, or None to skip it."""
    turns = [t for t in row["conversation"] if t["role"] in ("user", "assistant")]
    # Some users sent empty messages, which leaves nothing to summarise
    if not turns or any(
        t["role"] == "user" and not (t["content"] or "").strip() for t in turns
    ):
        return None

    created_at = row["timestamp"]
    return Conversation(
        # conversation_hash is not unique, but each turn_identifier is
        chat_id=str(turns[0]["turn_identifier"]),
        created_at=created_at,
        messages=[
            Message(
                # Only assistant turns have their own timestamp
                created_at=t["timestamp"] or created_at,
                role=t["role"],
                content=shorten(t["content"] or ""),
            )
            for t in turns[:MAX_MESSAGES]
        ],
        metadata={
            "user": user,
            "model": row["model"],
            "language": row["language"],
            "country": row["country"] or "Unknown",
            "turns": row["turn"],
            "redacted": row["redacted"],
        },
    )


def _openings_differ(conversations: list[Conversation], min_share: float) -> bool:
    """Check that enough chats start differently. Scripts tend to send the same opening."""
    openings = {" ".join(c.messages[0].content.lower().split())[:80] for c in conversations}
    return len(openings) >= min_share * len(conversations)


def _first_message(conversation: Any) -> str:
    """Return a chat's first user message on one line, cut to 600 characters."""
    for turn in conversation or []:
        if turn.get("role") == "user":
            return " ".join((turn.get("content") or "").split())[:600]
    return ""


def _saved_first_messages(cache_dir: Path) -> dict[str, str]:
    """Return the first messages saved so far, keyed by "file:chunk:row"."""
    path = cache_dir / "wildchat-first-messages.jsonl"
    saved: dict[str, str] = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                item = json.loads(line)
                saved[item["spot"]] = item["text"]
    return saved


def _read_first_messages(
    rows: pd.DataFrame, need: dict[tuple[str, str, str], int], saved: dict[str, str], cache_dir: Path
) -> None:
    """Read chunks until each user in `need` has that many first messages saved.

    The first messages can only be read a whole chunk (about 1,000 chats, 5 MB)
    at a time. So this picks the chunks that cover the most users still short of
    messages, and saves the first message of every candidate chat in each chunk.
    """
    rows = rows.assign(spot=rows["file"].astype(str) + ":" + rows["row_group"].astype(str) + ":" + rows["row"].astype(str))
    users = list(zip(rows["hashed_ip"], rows["user_agent"], rows["accept_language"]))
    have = Counter(user for user, spot in zip(users, rows["spot"]) if saved.get(spot))
    short = {user: n - have[user] for user, n in need.items() if n > have[user]}

    unsaved: dict[tuple[int, int], Counter] = {}
    for user, f, rg, spot in zip(users, rows["file"], rows["row_group"], rows["spot"]):
        if user in short and spot not in saved:
            unsaved.setdefault((int(f), int(rg)), Counter())[user] += 1
    chunks = []
    while short and unsaved:
        chunk = max(unsaved, key=lambda c: sum(min(n, short.get(u, 0)) for u, n in unsaved[c].items()))
        if not any(short.get(u, 0) for u in unsaved[chunk]):
            break
        chunks.append(chunk)
        for user, n in unsaved.pop(chunk).items():
            if user in short:
                short[user] -= n
                if short[user] <= 0:
                    del short[user]
    if not chunks:
        return

    chosen = set(chunks)
    by_chunk: dict[tuple[int, int], list[tuple[int, str]]] = {}
    for f, rg, row, spot in zip(rows["file"], rows["row_group"], rows["row"], rows["spot"]):
        if (int(f), int(rg)) in chosen and spot not in saved:
            by_chunk.setdefault((int(f), int(rg)), []).append((int(row), spot))
    links = {f: _resolve(f) for f in {f for f, _ in chunks}}

    def read_chunk(chunk: tuple[int, int]) -> list[tuple[str, str]]:
        f, rg = chunk
        parquet = pq.ParquetFile(HttpRangeFile(*links[f]), pre_buffer=True)
        columns = ["conversation.list.element.content", "conversation.list.element.role"]
        table = parquet.read_row_group(rg, columns=columns)
        wanted = by_chunk[chunk]
        conversations = table.column("conversation").take([row for row, _ in wanted]).to_pylist()
        return [(spot, _first_message(c)) for (_, spot), c in zip(wanted, conversations)]

    print(f"  Reading first messages from {len(chunks)} chunks of about 5 MB (saved for next time)...")
    path = cache_dir / "wildchat-first-messages.jsonl"
    with ThreadPoolExecutor(16) as pool, open(path, "a") as f:
        for done, found in enumerate(pool.map(read_chunk, chunks), 1):
            for spot, text in found:
                saved[spot] = text
                f.write(json.dumps({"spot": spot, "text": text}) + "\n")
            if done % 50 == 0 or done == len(chunks):
                print(f"    {done} of {len(chunks)} chunks")


async def _similarity(texts: list[str], topic: str) -> list[float]:
    """Score how close each text is to the topic (higher is closer), using OpenAI embeddings."""
    embedder = OpenAIEmbeddingModel()
    try:
        vectors = np.array(await embedder.embed([topic] + texts))
    finally:
        await embedder.client.close()  # close it while its event loop is still running
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors[1:] @ vectors[0]).tolist()


class UserSummary(BaseModel):
    """What one user mostly works on."""

    summary: str = Field(description="What this person mostly works on, in one sentence")


class TopicMatches(BaseModel):
    """Which people match a topic."""

    strong: list[int] = Field(description="People who clearly do the work the topic describes, best first")
    # Giving near misses their own list keeps them from being squeezed into the strong one
    partial: list[int] = Field(description="People who are only related to the topic")


async def _match_topic(
    users: dict[tuple[str, str, str], list[str]], topic: str, model: str, cache_dir: Path
) -> list[tuple[tuple[str, str, str], str]]:
    """Return the users who match the topic, best first, each with a one-sentence summary.

    First the model sums up each user from their first messages, read together so
    a bare paste of code makes sense next to their other chats. Summaries don't
    depend on the topic, so they are saved and reused. Then the model compares
    all the summaries at once and picks the matches. It does this several times,
    with the users in a different order each time, and only users picked by most
    of these votes are kept. That makes the picks much steadier.
    """
    client = instructor.from_provider(f"openai/{model}", async_client=True)
    extra = get_model_request_kwargs(model)
    limit = asyncio.Semaphore(20)
    path = cache_dir / f"wildchat-user-summaries-{model}.jsonl"
    saved: dict[str, str] = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                item = json.loads(line)
                saved[item["user"]] = item["summary"]

    async def summarize(texts: list[str]) -> str:
        numbered = "\n\n".join(f"{i}. {text}" for i, text in enumerate(texts, 1))
        async with limit:
            try:
                result = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You will see the first messages of several chats "
                         "from one person, numbered. Say in one sentence what this person mostly works on."},
                        {"role": "user", "content": numbered},
                    ],
                    response_model=UserSummary, temperature=0, **extra,
                )
                return result.summary
            except Exception:  # one failed summary shouldn't stop the search
                return ""

    async def vote(order: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        numbered = "\n".join(f"{i}. {summaries[key]}" for i, key in enumerate(order, 1))
        async with limit:
            try:
                result = await client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You will see short descriptions of what some people "
                         f"mostly work on, numbered. The topic is: {topic}. In 'strong', list the people who "
                         "clearly do the work the topic describes, best match first. If the topic has more than "
                         "one part, such as a field and a kind of work, every part must fit. In 'partial', list "
                         "the people who are only related: they work in a nearby field, study or teach the "
                         "subject, do homework or exam problems on it, or explore it in a hobby, game, or story. "
                         "Leave everyone else out."},
                        {"role": "user", "content": numbered},
                    ],
                    response_model=TopicMatches, temperature=0, **extra,
                )
            except Exception:  # a failed vote just doesn't count
                return []
        return [order[n - 1] for n in dict.fromkeys(result.strong) if 1 <= n <= len(order)]

    try:
        todo = [key for key in users if "|".join(key) not in saved]
        written = await asyncio.gather(*(summarize(users[key]) for key in todo))
        with open(path, "a") as f:
            for key, summary in zip(todo, written):
                if summary:
                    saved["|".join(key)] = summary
                    f.write(json.dumps({"user": "|".join(key), "summary": summary}) + "\n")
        summaries = {key: saved["|".join(key)] for key in users if saved.get("|".join(key))}
        orders = []
        for i in range(TOPIC_VOTES):
            order = list(summaries)
            random.Random(i).shuffle(order)
            orders.append(order)
        ballots = await asyncio.gather(*(vote(order) for order in orders))
    finally:
        await client.client.close()  # close it while its event loop is still running

    places: dict[tuple[str, str, str], list[int]] = {}
    for ballot in ballots:
        for place, key in enumerate(ballot):
            places.setdefault(key, []).append(place)
    kept = [key for key, found in places.items() if len(found) > TOPIC_VOTES / 2]
    kept.sort(key=lambda key: (-len(places[key]), sum(places[key]) / len(places[key])))
    return [(key, summaries[key]) for key in kept]


def _rank_by_topic(
    frame: pd.DataFrame,
    candidates: list[tuple[str, str, str]],
    topic: str,
    model: str,
    cache_dir: Path,
) -> list[tuple[tuple[str, str, str], str]]:
    """Return the users who chat about `topic`, best first, each with a one-sentence summary.

    1. Read the first message of a few chats from every candidate, and rank the
       candidates by how close those messages are to the topic.
    2. For the closest users, read more first messages, have the model sum up
       each user, and have it pick the users whose work matches the topic.
    """
    rows = frame[frame.set_index(USER_KEY).index.isin(candidates)]
    groups = rows.groupby(USER_KEY, sort=True)
    saved = _saved_first_messages(cache_dir)

    def messages(key: tuple[str, str, str], count: int) -> list[str]:
        spots = groups.get_group(key)
        found = (saved.get(f"{f}:{rg}:{r}", "") for f, rg, r in zip(spots["file"], spots["row_group"], spots["row"]))
        return [text for text in found if text][:count]

    print(f"Looking for users who chat about: {topic}")
    _read_first_messages(rows, {key: TOPIC_SAMPLE for key in candidates}, saved, cache_dir)
    pairs = [(key, text) for key in candidates for text in messages(key, 2 * TOPIC_SAMPLE)]
    closeness: dict[tuple[str, str, str], list[float]] = {}
    for (key, _), score in zip(pairs, asyncio.run(_similarity([t for _, t in pairs], topic))):
        closeness.setdefault(key, []).append(score)
    shortlist = sorted(closeness, key=lambda key: -float(np.mean(closeness[key])))[:TOPIC_SHORTLIST]

    print(f"  Checking {TOPIC_CHECK} chats from each of the {len(shortlist)} closest users with {model}...")
    _read_first_messages(rows, {key: TOPIC_CHECK for key in shortlist}, saved, cache_dir)
    users = {key: messages(key, TOPIC_CHECK) for key in shortlist}
    return asyncio.run(_match_topic(users, topic, model, cache_dir))


def load_wildchat_users(
    num_users: int,
    language: str,
    seed: int,
    cache_dir: Path,
    topic: Optional[str] = None,
    model: str = "gpt-6-luna",
    *,
    min_active_weeks: int = 1,
    min_span_days: int = 0,
) -> list[Conversation]:
    """Pick `num_users` users who chat in `language` and return all their chats.

    Without a topic, users are picked at random, and the same seed always picks
    the same users. With a topic, the users who chat about it most are picked first.
    """
    if num_users < 1 or min_active_weeks < 1 or min_span_days < 0:
        raise ValueError("User count and active weeks must be positive; span cannot be negative")
    temporal = min_active_weeks > 1 or min_span_days > 0
    suffix = "-temporal" if temporal else ""
    cache_path = cache_dir / f"wildchat-users-{MIN_CHATS}-{MAX_CHATS}{suffix}.parquet"
    users = pq.read_table(cache_path) if cache_path.exists() else _scan_users(cache_path, temporal)
    frame = users.to_pandas()
    groups = frame.groupby(USER_KEY, sort=True)

    in_language = groups["language"].agg(
        lambda langs: (langs.str.lower() == language.lower()).mean()
    )
    candidates = sorted(in_language[in_language >= MIN_LANGUAGE_SHARE].index)
    print(f"{len(candidates)} WildChat users have {MIN_CHATS} to {MAX_CHATS} chats, mostly in {language}.")
    if temporal:
        dates = pd.to_datetime(frame["timestamp"], utc=True)
        frame["week"] = (dates - pd.to_timedelta(dates.dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")
        frame["timestamp"] = dates
        groups = frame.groupby(USER_KEY, sort=True)
        active = groups["week"].nunique()
        spans = groups["timestamp"].agg(lambda values: (values.max() - values.min()).days)
        candidates = [key for key in candidates if active[key] >= min_active_weeks and spans[key] >= min_span_days]
        print(f"  {len(candidates)} span at least {min_span_days} days and {min_active_weeks} active weeks.")
    summaries: dict[tuple[str, str, str], str] = {}
    if topic:
        summaries = dict(_rank_by_topic(frame, candidates, topic, model, cache_dir))
        candidates = list(summaries)
        print(f"  {len(candidates)} of them clearly match the topic.")
    else:
        random.Random(seed).shuffle(candidates)

    picked: list[Conversation] = []
    links: dict[int, tuple[str, int]] = {}
    found = 0
    for key in candidates:
        label = f"User {found + 1}"
        rows = _read_rows(groups.get_group(key), links)
        conversations = [c for row in rows if (c := to_conversation(row, label))]
        min_distinct = MIN_DISTINCT_OPENINGS_TOPIC if topic else MIN_DISTINCT_OPENINGS
        if len(conversations) < MIN_USABLE_CHATS or not _openings_differ(conversations, min_distinct):
            print("  Skipping a user whose chats look scripted or empty.")
            continue

        conversations.sort(key=lambda c: c.created_at)
        if temporal:
            weeks = {c.created_at.date() - pd.Timedelta(days=c.created_at.weekday()) for c in conversations}
            span = (conversations[-1].created_at - conversations[0].created_at).days
            if len(weeks) < min_active_weeks or span < min_span_days:
                continue
        # A reproducible anonymous group ID; never persist browser headers or IP hashes.
        source_id = hashlib.sha256(json.dumps(list(key)).encode()).hexdigest()[:16]
        for conversation in conversations:
            conversation.metadata["source_user_id"] = source_id
        country = Counter(c.metadata["country"] for c in conversations).most_common(1)[0][0]
        first, last = conversations[0].created_at, conversations[-1].created_at
        print(f"  {label}: {len(conversations)} chats, {first:%b %d, %Y} to {last:%b %d, %Y}, {country}")
        summary = summaries.get(key, "")
        if summary:
            print(f"    Works on: {summary}")
            for conversation in conversations:
                conversation.metadata["user_summary"] = summary
        picked.extend(conversations)
        found += 1
        if found == num_users:
            break

    if found < num_users:
        print(f"Only found {found} matching users.")
    return picked
