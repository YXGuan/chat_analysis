import type { Profile, User, Week } from "./types";

export type Grouping = "day" | "week" | "fortnight" | "month";
export type Detail = "themes" | "topics";
export type Visibility = { themes: string[]; topics: string[] };
export const GROUPINGS: { id: Grouping; label: string; title: string }[] = [
  { id: "day", label: "Day", title: "Daily activity" },
  { id: "week", label: "1 week", title: "Weekly activity" },
  { id: "fortnight", label: "2 weeks", title: "Two-week activity" },
  { id: "month", label: "Month", title: "Monthly activity" },
];

const DAY = 86_400_000;
const MONDAY_ANCHOR = Date.UTC(1970, 0, 5);
function utcDate(value: string) {
  return new Date(
    value.length === 10 || /Z|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z",
  );
}

export function periodStart(value: string, grouping: Grouping): string {
  const date = utcDate(value);
  date.setUTCHours(0, 0, 0, 0);
  if (grouping === "month") date.setUTCDate(1);
  if (grouping === "week" || grouping === "fortnight") {
    const days = grouping === "week" ? 7 : 14;
    date.setTime(
      MONDAY_ANCHOR +
        Math.floor((date.getTime() - MONDAY_ANCHOR) / (days * DAY)) *
          days *
          DAY,
    );
  }
  return date.toISOString().slice(0, 10);
}

export function nextPeriod(start: string, grouping: Grouping): string {
  const date = utcDate(start);
  if (grouping === "month") date.setUTCMonth(date.getUTCMonth() + 1);
  else
    date.setUTCDate(
      date.getUTCDate() +
        (grouping === "day" ? 1 : grouping === "week" ? 7 : 14),
    );
  return date.toISOString().slice(0, 10);
}

export function periodLabel(start: string, grouping: Grouping): string {
  const date = utcDate(start);
  const format = (d: Date) =>
    d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    });
  if (grouping === "month")
    return date.toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    });
  if (grouping === "week") return `Week of ${format(date)}`;
  if (grouping === "day") return format(date);
  const end = utcDate(nextPeriod(start, grouping));
  end.setUTCDate(end.getUTCDate() - 1);
  return `${format(date)} – ${format(end)}`;
}

function comparison(
  weeks: Week[],
  previous: User["comparison"],
  categories: string[],
) {
  const early = weeks.slice(0, previous.window_weeks);
  const late = weeks.slice(-previous.window_weeks);
  const earlyTotal = early.reduce((sum, w) => sum + w.total, 0);
  const lateTotal = late.reduce((sum, w) => sum + w.total, 0);
  const sufficient =
    weeks.length >= previous.window_weeks * 2 &&
    Math.min(earlyTotal, lateTotal) >= previous.min_window_chats;
  return {
    ...previous,
    sufficient,
    early: { ...previous.early, total: earlyTotal },
    late: { ...previous.late, total: lateTotal },
    shifts: categories.map((category) => {
      const early_count = early.reduce(
        (sum, w) => sum + (w.counts[category] || 0),
        0,
      );
      const late_count = late.reduce(
        (sum, w) => sum + (w.counts[category] || 0),
        0,
      );
      const early_share = earlyTotal ? early_count / earlyTotal : null;
      const late_share = lateTotal ? late_count / lateTotal : null;
      const delta = sufficient ? late_share! - early_share! : null;
      return {
        category,
        early_count,
        late_count,
        early_share,
        late_share,
        delta,
        active_weeks: weeks.filter((w) => w.counts[category] > 0).length,
        stable:
          sufficient &&
          early_count >= 2 &&
          late_count >= 2 &&
          Math.abs(delta!) <= 0.1,
      };
    }),
  };
}

/** Keep the original calendar span and comparison windows when hiding categories. */
export function filterTimeline(
  data: Profile,
  detail: Detail,
  hidden: Visibility,
): Profile {
  const base =
    detail === "topics" && data.topic_timeline
      ? {
          ...data,
          ...data.topic_timeline,
          taxonomy: data.clusters.filter((t) => t.parent_id),
        }
      : data;
  const hiddenThemes = new Set(hidden.themes),
    hiddenTopics = new Set(hidden.topics);
  const taxonomy = base.taxonomy.filter((t) =>
    detail === "topics"
      ? !hiddenTopics.has(t.id) && !hiddenThemes.has(t.parent_id || "")
      : !hiddenThemes.has(t.id),
  );
  const categories = taxonomy.map((t) => t.id),
    visible = new Set(categories);
  const chats = Object.fromEntries(
    Object.entries(data.chats).filter(([, chat]) =>
      visible.has(detail === "topics" ? chat.topic_id || "" : chat.category),
    ),
  );
  return {
    ...base,
    taxonomy,
    categories,
    chats,
    users: base.users.map((user) => {
      const weeks = user.weeks.map((week) => {
        const chat_ids = week.chat_ids.filter((id) => id in chats);
        const counts: Record<string, number> = Object.fromEntries(
          categories.map((id) => [id, 0]),
        );
        for (const id of chat_ids)
          counts[
            detail === "topics" ? chats[id].topic_id! : chats[id].category
          ]++;
        return { ...week, chat_ids, counts, total: chat_ids.length };
      });
      return {
        ...user,
        weeks,
        total: weeks.reduce((sum, w) => sum + w.total, 0),
        active_weeks: weeks.filter((w) => w.total > 0).length,
        comparison: comparison(weeks, user.comparison, categories),
      };
    }),
  };
}

/** Aggregate retained source chats, never weekly approximations, into UTC periods. */
export function buildTimeline(
  data: Profile,
  user: string,
  grouping: Grouping,
  detail: Detail,
) {
  const users = data.users.filter((u) => user === "all" || u.label === user);
  if (!users.length) return { periods: [], users: [] };
  const first = users.map((u) => periodStart(u.first, grouping)).sort()[0];
  const last = users
    .map((u) => periodStart(u.last, grouping))
    .sort()
    .reverse()[0];
  const periods: string[] = [];
  for (
    let period = first;
    period <= last;
    period = nextPeriod(period, grouping)
  )
    periods.push(period);
  const buckets = users.map((u) => {
    const start = periodStart(u.first, grouping),
      end = periodStart(u.last, grouping);
    return {
      label: u.label,
      periods: periods
        .filter((p) => p >= start && p <= end)
        .map((period) => ({
          period,
          total: 0,
          counts: {} as Record<string, number>,
          chat_ids: [] as string[],
        })),
    };
  });
  const byUser = new Map(
    buckets.map((u) => [u.label, new Map(u.periods.map((p) => [p.period, p]))]),
  );
  for (const chat of Object.values(data.chats)) {
    const bucket = byUser
      .get(chat.metadata.user)
      ?.get(periodStart(chat.created_at, grouping));
    if (!bucket) continue;
    const category = detail === "topics" ? chat.topic_id! : chat.category;
    bucket.total++;
    bucket.counts[category] = (bucket.counts[category] || 0) + 1;
    bucket.chat_ids.push(chat.chat_id);
  }
  return { periods, users: buckets };
}
