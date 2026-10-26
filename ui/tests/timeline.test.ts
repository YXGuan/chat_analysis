import assert from "node:assert/strict";
import test from "node:test";
import {
  buildTimeline,
  filterTimeline,
  GROUPINGS,
  nextPeriod,
  periodLabel,
  periodStart,
} from "../src/temporal/timeline.ts";
import type { Chat, Profile, User, Week } from "../src/temporal/types.ts";

const shown = { themes: [], topics: [] };
function profile(
  entries: { date: string; category?: string; user?: string }[],
): Profile {
  const chats: Chat[] = entries.map((entry, i) => ({
    chat_id: `chat-${i}`,
    created_at: entry.date,
    category: entry.category || "a",
    topic_id: `${entry.category || "a"}-topic`,
    metadata: { user: entry.user || "User 1" },
    messages: [],
  }));
  const taxonomy = ["a", "b"].map((id) => ({
    id,
    name: id,
    color: "#000",
    description: "",
  }));
  const users: User[] = [...new Set(chats.map((c) => c.metadata.user))].map(
    (label) => {
      const mine = chats.filter((c) => c.metadata.user === label);
      const dates = mine
        .map((c) => new Date(c.created_at).toISOString())
        .sort();
      const first = dates[0],
        last = dates[dates.length - 1];
      const weeks: Week[] = [];
      for (
        let week = periodStart(first, "week");
        week <= periodStart(last, "week");
        week = nextPeriod(week, "week")
      ) {
        const items = mine.filter(
          (c) => periodStart(c.created_at, "week") === week,
        );
        weeks.push({
          week,
          total: items.length,
          counts: {},
          chat_ids: items.map((c) => c.chat_id),
        });
      }
      return {
        label,
        first,
        last,
        total: mine.length,
        active_weeks: weeks.filter((w) => w.total).length,
        weeks,
        comparison: {
          sufficient: false,
          window_weeks: 4,
          min_window_chats: 5,
          shifts: [],
          early: {
            first: weeks[0].week,
            last: weeks[Math.min(3, weeks.length - 1)].week,
            total: 0,
          },
          late: {
            first: weeks[Math.max(0, weeks.length - 4)].week,
            last: weeks[weeks.length - 1].week,
            total: 0,
          },
        },
      };
    },
  );
  return {
    chats: Object.fromEntries(chats.map((c) => [c.chat_id, c])),
    taxonomy,
    categories: ["a", "b"],
    users,
    weeks: users[0].weeks.map((w) => w.week),
    clusters: [
      ...taxonomy,
      ...taxonomy.map((t) => ({ ...t, id: `${t.id}-topic`, parent_id: t.id })),
    ],
    topic_timeline: { categories: ["a-topic", "b-topic"], weeks: [], users },
    method: "synthetic",
    source: { name: "Synthetic", url: "", license: "" },
    analysis: {
      model: "test",
      execution: "test",
      input_chats: chats.length,
      source_sha256: "test",
    },
  };
}

test("UTC days, Monday weeks, and months handle offsets and year boundaries", () => {
  assert.equal(periodStart("2026-09-17T23:30:00-04:00", "day"), "2026-09-18");
  assert.equal(periodStart("2026-01-01", "week"), "2025-12-29");
  assert.equal(periodStart("2026-03-01T00:30:00+02:00", "month"), "2026-02-01");
  assert.equal(periodStart("2026-09-17T12:00:00", "day"), "2026-09-17");
});

test("two-week periods have stable shared Monday boundaries, including before the anchor", () => {
  assert.equal(periodStart("1970-01-05", "fortnight"), "1970-01-05");
  assert.equal(periodStart("1970-01-18T23:59:59Z", "fortnight"), "1970-01-05");
  assert.equal(periodStart("1970-01-19", "fortnight"), "1970-01-19");
  assert.equal(periodStart("1970-01-04", "fortnight"), "1969-12-22");
  assert.equal(nextPeriod("2025-12-29", "fortnight"), "2026-01-12");
  assert.equal(
    periodLabel("2025-12-29", "fortnight"),
    "Dec 29, 2025 – Jan 11, 2026",
  );
});

test("calendar months include leap days and empty months without approximating weekly counts", () => {
  const data = filterTimeline(
    profile([
      { date: "2024-01-31T23:59:59Z" },
      { date: "2024-03-01T00:00:00Z" },
    ]),
    "themes",
    shown,
  );
  const chart = buildTimeline(data, "User 1", "month", "themes");
  assert.deepEqual(chart.periods, ["2024-01-01", "2024-02-01", "2024-03-01"]);
  assert.deepEqual(
    chart.users[0].periods.map((p) => p.total),
    [1, 0, 1],
  );
  assert.equal(nextPeriod("2024-02-01", "month"), "2024-03-01");
  assert.equal(periodStart("2024-02-29T23:59:59Z", "month"), "2024-02-01");
});

test("every grouping conserves chats, topic counts, and separate user totals", () => {
  const source = profile([
    { date: "2026-01-05T12:00:00Z", user: "User 1" },
    { date: "2026-01-19T12:00:00Z", user: "User 1", category: "b" },
    { date: "2026-02-23T12:00:00Z", user: "User 1" },
    { date: "2026-01-06T12:00:00Z", user: "User 2", category: "b" },
    { date: "2026-02-01T12:00:00Z", user: "User 2", category: "b" },
  ]);
  const before = structuredClone(source);
  for (const detail of ["themes", "topics"] as const) {
    const filtered = filterTimeline(source, detail, shown);
    for (const { id } of GROUPINGS) {
      const chart = buildTimeline(filtered, "all", id, detail);
      assert.deepEqual(
        chart.users.map((u) => u.periods.reduce((sum, p) => sum + p.total, 0)),
        [3, 2],
      );
      for (const user of chart.users)
        for (const p of user.periods) {
          assert.equal(
            Object.values(p.counts).reduce((sum, n) => sum + n, 0),
            p.total,
          );
          assert.equal(p.chat_ids.length, p.total);
        }
      const oneUser = buildTimeline(filtered, "User 2", id, detail);
      assert.equal(oneUser.users.length, 1);
      assert.equal(
        oneUser.users[0].periods.reduce((sum, p) => sum + p.total, 0),
        2,
      );
    }
  }
  assert.deepEqual(source, before);
});

test("hiding themes also hides their topics, while keeping original empty periods and users", () => {
  const source = profile([
    { date: "2026-01-05T12:00:00Z", category: "a" },
    { date: "2026-02-23T12:00:00Z", category: "b" },
    { date: "2026-01-06T12:00:00Z", user: "User 2", category: "a" },
  ]);
  const hidden = { themes: ["a"], topics: [] };
  const filtered = filterTimeline(source, "topics", hidden);
  assert.deepEqual(filtered.categories, ["b-topic"]);
  assert.deepEqual(
    filtered.users.map((u) => u.total),
    [1, 0],
  );
  const chart = buildTimeline(filtered, "User 1", "month", "topics");
  assert.deepEqual(
    chart.users[0].periods.map((p) => p.total),
    [0, 1],
  );
  assert.equal(filtered.users[0].first, source.users[0].first);
  assert.equal(filtered.users[0].weeks.length, 8);
  const allHidden = filterTimeline(source, "themes", {
    themes: ["a", "b"],
    topics: [],
  });
  assert.equal(Object.keys(allHidden.chats).length, 0);
  assert.equal(allHidden.taxonomy.length, 0);
  assert.ok(
    allHidden.users.every((u) => !u.comparison.sufficient && u.total === 0),
  );
});

test("shares and change comparisons use visible chats within the original four-week windows", () => {
  const entries = [
    ...Array.from({ length: 5 }, () => ({
      date: "2026-01-05T12:00:00Z",
      category: "a",
    })),
    ...Array.from({ length: 2 }, () => ({
      date: "2026-01-05T12:00:00Z",
      category: "b",
    })),
    ...Array.from({ length: 6 }, () => ({
      date: "2026-02-23T12:00:00Z",
      category: "a",
    })),
    ...Array.from({ length: 9 }, () => ({
      date: "2026-02-23T12:00:00Z",
      category: "b",
    })),
  ];
  const source = profile(entries);
  const full = filterTimeline(source, "themes", shown);
  assert.equal(full.users[0].comparison.shifts[0].early_share, 5 / 7);
  assert.equal(full.users[0].comparison.shifts[0].late_share, 6 / 15);
  const filtered = filterTimeline(source, "themes", {
    themes: ["b"],
    topics: [],
  });
  const cmp = filtered.users[0].comparison;
  assert.ok(cmp.sufficient);
  assert.equal(cmp.early.total, 5);
  assert.equal(cmp.late.total, 6);
  assert.equal(cmp.shifts[0].early_share, 1);
  assert.equal(cmp.shifts[0].late_share, 1);
  assert.equal(cmp.shifts[0].delta, 0);
  assert.equal(cmp.early.first, full.users[0].comparison.early.first);
  assert.equal(cmp.late.last, full.users[0].comparison.late.last);
});

test("hiding individual topics leaves theme mode intact and suppresses insufficient comparisons", () => {
  const source = profile([
    { date: "2026-01-05T12:00:00Z" },
    { date: "2026-01-06T12:00:00Z", category: "b" },
  ]);
  const hidden = { themes: [], topics: ["a-topic"] };
  assert.equal(filterTimeline(source, "themes", hidden).users[0].total, 2);
  const topics = filterTimeline(source, "topics", hidden);
  assert.equal(topics.users[0].total, 1);
  assert.equal(topics.users[0].comparison.sufficient, false);
  assert.ok(topics.users[0].comparison.shifts.every((s) => s.delta === null));
});
