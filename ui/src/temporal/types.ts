export type Topic = {
  id: string;
  name: string;
  description: string;
  color: string;
  parent_id?: string | null;
  level?: number;
  chats?: string[];
  x?: number;
  y?: number;
};
export type Chat = {
  chat_id: string;
  created_at: string;
  metadata: { user: string; [key: string]: unknown };
  messages: { role: string; content: string }[];
  category: string;
  topic_id?: string;
  summary?: string;
  confidence?: number;
  note?: string;
  label_note?: string;
};
export type Week = {
  week: string;
  total: number;
  counts: Record<string, number>;
  chat_ids: string[];
};
export type Shift = {
  category: string;
  early_count: number;
  late_count: number;
  early_share: number | null;
  late_share: number | null;
  delta: number | null;
  active_weeks: number;
  stable: boolean;
};
export type User = {
  label: string;
  total: number;
  first: string;
  last: string;
  active_weeks: number;
  summary?: string;
  weeks: Week[];
  comparison: {
    sufficient: boolean;
    window_weeks: number;
    min_window_chats: number;
    early: { first: string; last: string; total: number };
    late: { first: string; last: string; total: number };
    shifts: Shift[];
  };
};
export type Profile = {
  title?: string;
  taxonomy: Topic[];
  categories: string[];
  clusters: Topic[];
  weeks: string[];
  users: User[];
  topic_timeline?: { categories: string[]; weeks: string[]; users: User[] };
  chats: Record<string, Chat>;
  method: string;
  analysis: {
    model: string;
    execution: string;
    input_chats: number;
    source_sha256: string;
    generated_at?: string;
  };
  source: { name: string; url: string; license: string; kind?: string };
};
export type View = "timeline" | "explorer";
export type Layout = "list" | "tree" | "flow" | "circle";
export const LAYOUTS: { id: Layout; name: string; description: string }[] = [
  {
    id: "list",
    name: "List",
    description:
      "Every cluster as an outline you can open and close. Select a name to read its conversations.",
  },
  {
    id: "tree",
    name: "Tree",
    description:
      "Follow the branches from broad themes to specific topics. Bigger dots and thicker lines mean more chats.",
  },
  {
    id: "flow",
    name: "Flow",
    description:
      "Follow each user’s chats into broad themes and smaller clusters. Thicker bands mean more chats.",
  },
  {
    id: "circle",
    name: "Circle",
    description:
      "Clusters nest inside their broader groups. Larger circles hold more conversations.",
  },
];
export const formatDate = (s: string, year = false) =>
  new Date(
    s.length === 10
      ? s + "T12:00:00Z"
      : /Z|[+-]\d\d:\d\d$/.test(s)
        ? s
        : s + "Z",
  ).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    ...(year ? { year: "numeric" } : {}),
    timeZone: "UTC",
  });
export const percent = (v: number | null) =>
  v === null ? "—" : `${Math.round(v * 100)}%`;
export const change = (v: number | null) =>
  v === null ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(1)} pp`;
export function monday(value: string) {
  const d = new Date(/Z|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z");
  d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
  return d.toISOString().slice(0, 10);
}
