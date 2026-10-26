import type { Profile, Topic } from "./types";

export const USER_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"];
export const userColor = (index: number) =>
  USER_COLORS[index % USER_COLORS.length];

export function clusterScope(data: Profile, user: string) {
  const chats = Object.values(data.chats).filter(
    (chat) => user === "all" || chat.metadata.user === user,
  );
  const ids = new Set(chats.map((chat) => chat.chat_id));
  const byId = new Map(data.clusters.map((topic) => [topic.id, topic]));
  const counts = new Map<string, number>();
  const mixes = new Map<string, number[]>();
  for (const topic of data.clusters) {
    counts.set(
      topic.id,
      (topic.chats || []).filter((id) => ids.has(id)).length,
    );
    mixes.set(
      topic.id,
      data.users.map(
        (u) =>
          (topic.chats || []).filter(
            (id) => data.chats[id]?.metadata.user === u.label,
          ).length,
      ),
    );
  }
  const topics = data.clusters.filter((topic) => counts.get(topic.id)! > 0);
  const sort = (a: Topic, b: Topic) =>
    counts.get(b.id)! - counts.get(a.id)! || a.name.localeCompare(b.name);
  const children = new Map<string | null, Topic[]>();
  for (const topic of topics) {
    const parent =
      topic.parent_id && byId.has(topic.parent_id) ? topic.parent_id : null;
    children.set(parent, [...(children.get(parent) || []), topic]);
  }
  for (const siblings of children.values()) siblings.sort(sort);
  const roots = children.get(null) || [];
  const count = (topic: Topic) => counts.get(topic.id) || 0;
  const path = (topic: Topic) => {
    const ancestors: Topic[] = [topic];
    let current = topic;
    while (current.parent_id && byId.has(current.parent_id)) {
      current = byId.get(current.parent_id)!;
      ancestors.unshift(current);
    }
    return ancestors;
  };
  const paint = (topic: Topic) => {
    const mix = mixes.get(topic.id)!;
    const total = mix.reduce((a, b) => a + b, 0) || 1;
    const index =
      user === "all"
        ? mix.indexOf(Math.max(...mix))
        : data.users.findIndex((u) => u.label === user);
    const tied =
      user === "all" && mix.filter((n) => n === mix[index]).length > 1;
    return {
      color: tied ? "var(--muted)" : userColor(index),
      opacity: 0.3 + 0.7 * (mix[index] / total),
    };
  };
  return {
    chats,
    topics,
    roots,
    byId,
    counts,
    mixes,
    children,
    count,
    path,
    paint,
  };
}

export type ClusterScope = ReturnType<typeof clusterScope>;
