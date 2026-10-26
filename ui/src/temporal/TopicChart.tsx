import * as d3 from "d3";
import { sankey, sankeyLinkHorizontal } from "d3-sankey";
import type { SankeyLink } from "d3-sankey";
import type { KeyboardEvent } from "react";
import { userColor } from "./clusters";
import type { ClusterScope } from "./clusters";
import type { Layout, Profile, Topic } from "./types";

type Branch = { topic: Topic | null; children?: Branch[]; count: number };
type FlowNode = { id: string; name: string; topic?: Topic; slot?: number };
type FlowLink = { value: number; slot: number };
const W = 800;
const short = (text: string, length: number) =>
  text.length > length ? `${text.slice(0, Math.max(1, length - 1))}…` : text;

export function TopicChart({
  scope,
  data,
  user,
  layout,
  selected,
  onSelect,
}: {
  scope: ClusterScope;
  data: Profile;
  user: string;
  layout: Exclude<Layout, "list">;
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const branch = (topic: Topic): Branch => {
    const children = (scope.children.get(topic.id) || []).map(branch);
    return {
      topic,
      count: scope.count(topic),
      ...(children.length ? { children } : {}),
    };
  };
  const root = d3
    .hierarchy<Branch>({
      topic: null,
      count: scope.chats.length,
      children: scope.roots.map(branch),
    })
    .sum((node) => (node.children ? 0 : node.count))
    .sort((a, b) => (b.value || 0) - (a.value || 0));
  const title = (topic: Topic | null) =>
    `${topic?.name || "All conversations"}: ${topic ? scope.count(topic) : scope.chats.length} chats`;
  const selectProps = (topic: Topic | null) => ({
    role: "button" as const,
    tabIndex: 0,
    "aria-label": title(topic),
    "aria-pressed": topic ? selected === topic.id : !selected,
    className: `cluster-shape ${topic && selected === topic.id ? "is-selected" : ""}`,
    onClick: () => onSelect(topic?.id || null),
    onKeyDown: (event: KeyboardEvent<SVGGElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onSelect(topic?.id || null);
      }
    },
  });
  const paint = (topic: Topic | null) =>
    topic ? scope.paint(topic) : { color: "var(--muted)", opacity: 0.5 };

  if (!scope.chats.length)
    return <p className="cluster-empty">No clusters for this user.</p>;

  if (layout === "tree") {
    const H = Math.max(360, root.leaves().length * 30 + 50);
    const labelWidth = 260;
    const columnWidth = (W - labelWidth - 65) / Math.max(1, root.height);
    const tree = d3
      .tree<Branch>()
      .size([H - 50, root.height * columnWidth])
      .separation((a, b) => (a.parent === b.parent ? 1 : 1.4))(root);
    const radius = (value: number) =>
      3 + 8 * Math.sqrt(value / Math.max(1, root.value || 0));
    return (
      <div className="cluster-chart-scroll">
        <svg
          className="cluster-chart cluster-tree-chart"
          viewBox={`0 0 ${W} ${H}`}
          role="group"
          aria-label="Tree of clusters"
        >
          <g transform="translate(40,25)">
            {tree.links().map((link, i) => (
              <path
                key={i}
                className="cluster-tree-link"
                strokeWidth={
                  1 +
                  5 * Math.sqrt((link.target.value || 0) / (root.value || 1))
                }
                d={
                  d3
                    .linkHorizontal<
                      d3.HierarchyPointLink<Branch>,
                      d3.HierarchyPointNode<Branch>
                    >()
                    .x((node) => node.y)
                    .y((node) => node.x)(link) || ""
                }
              />
            ))}
            {tree.descendants().map((node, i) => {
              const { color, opacity } = paint(node.data.topic);
              const r = radius(node.value || 0);
              return (
                <g
                  key={i}
                  transform={`translate(${node.y},${node.x})`}
                  {...selectProps(node.data.topic)}
                >
                  <title>{title(node.data.topic)}</title>
                  <circle className="cluster-hit" r={13} />
                  <circle
                    className="cluster-node"
                    r={r}
                    fill={color}
                    fillOpacity={opacity}
                  />
                  <text
                    className={`cluster-chart-label ${node.children ? "is-strong" : ""}`}
                    x={!node.depth ? -12 : node.children ? 0 : r + 7}
                    y={node.depth && node.children ? -r - 7 : 4}
                    textAnchor={
                      !node.depth ? "end" : node.children ? "middle" : "start"
                    }
                  >
                    {node.data.topic
                      ? short(
                          node.data.topic.name,
                          node.children ? Math.floor(columnWidth / 6) : 42,
                        )
                      : "All"}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
    );
  }

  if (layout === "flow") {
    const users = data.users
      .map((u, slot) => ({ ...u, slot }))
      .filter((u) => user === "all" || u.label === user);
    const nodes: FlowNode[] = [
      ...users.map((u) => ({
        id: `user:${u.label}`,
        name: u.label,
        slot: u.slot,
      })),
      ...scope.topics.map((topic) => ({
        id: topic.id,
        name: topic.name,
        topic,
      })),
    ];
    const links: SankeyLink<FlowNode, FlowLink>[] = [];
    for (const topic of scope.topics) {
      for (const u of users) {
        const value = scope.mixes.get(topic.id)![u.slot];
        if (value)
          links.push({
            source:
              topic.parent_id && scope.byId.has(topic.parent_id)
                ? topic.parent_id
                : `user:${u.label}`,
            target: topic.id,
            value,
            slot: u.slot,
          });
      }
    }
    const H = Math.max(420, root.leaves().length * 32 + 50);
    const graph = sankey<FlowNode, FlowLink>()
      .nodeId((node) => node.id)
      .nodeWidth(12)
      .nodePadding(16)
      .nodeSort(null)
      .extent([
        [4, 12],
        [W - 245, H - 12],
      ])({ nodes, links });
    const linkPath = sankeyLinkHorizontal<FlowNode, FlowLink>();
    const columnStarts = [...new Set(graph.nodes.map((node) => node.x0!))].sort(
      (a, b) => a - b,
    );
    return (
      <div className="cluster-chart-scroll">
        <svg
          className="cluster-chart cluster-flow-chart"
          viewBox={`0 0 ${W} ${H}`}
          role="group"
          aria-label="Flow of chats from users into clusters"
        >
          {graph.links.map((link, i) => (
            <path
              key={i}
              className="cluster-flow-link"
              d={linkPath(link) || ""}
              stroke={userColor(link.slot)}
              strokeWidth={Math.max(1, link.width || 0)}
            >
              <title>{`${data.users[link.slot].label}: ${typeof link.source === "object" ? link.source.name : ""} → ${typeof link.target === "object" ? link.target.name : ""} · ${link.value} chats`}</title>
            </path>
          ))}
          {graph.nodes.map((node) => {
            const next = columnStarts.find((x) => x > node.x0!);
            const room = (next || W) - node.x1! - 14;
            return (
              <g key={node.id} {...(node.topic ? selectProps(node.topic) : {})}>
                <title>
                  {node.name}: {node.value} chats
                </title>
                <rect
                  className="cluster-node"
                  x={node.x0}
                  y={node.y0}
                  width={node.x1! - node.x0!}
                  height={Math.max(1, node.y1! - node.y0!)}
                  rx={2}
                  fill={
                    node.slot !== undefined
                      ? userColor(node.slot)
                      : "var(--muted)"
                  }
                />
                {node.topic && (
                  <rect
                    className="cluster-hit"
                    x={node.x0! - 4}
                    y={node.y0}
                    width={20}
                    height={Math.max(16, node.y1! - node.y0!)}
                  />
                )}
                <text
                  className={`cluster-chart-label ${!node.topic?.parent_id ? "is-strong" : ""}`}
                  x={node.x1! + 6}
                  y={(node.y0! + node.y1!) / 2 + 4}
                >
                  {short(
                    `${node.name} · ${node.value}`,
                    Math.floor(room / 6.2),
                  )}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  const packed = d3.pack<Branch>().size([640, 640]).padding(12)(root);
  const circles = packed.children || [];
  const top = Math.max(
    0,
    Math.min(...circles.map((node) => node.y - node.r)) - 8,
  );
  const bottom = Math.min(
    640,
    Math.max(...circles.map((node) => node.y + node.r)) + 8,
  );
  return (
    <svg
      className="cluster-chart cluster-circle-chart"
      viewBox={`0 ${top} 640 ${bottom - top}`}
      role="group"
      aria-label="Nested circles of clusters"
    >
      {packed
        .descendants()
        .filter((node) => node.depth)
        .map((node) => {
          const topic = node.data.topic!;
          const { color, opacity } = paint(topic);
          return (
            <g key={topic.id} {...selectProps(topic)}>
              <title>{title(topic)}</title>
              <circle
                className="cluster-node"
                cx={node.x}
                cy={node.y}
                r={node.r}
                fill={color}
                fillOpacity={node.children ? 0.09 : opacity * 0.65}
                stroke={color}
                strokeOpacity={node.children ? 0.4 : 0.2}
              />
              {node.children && node.r > 48 && (
                <text
                  className="cluster-chart-label is-strong"
                  textAnchor="middle"
                  x={node.x}
                  y={node.y - node.r + 18}
                >
                  {short(topic.name, Math.floor(node.r / 3.8))}
                </text>
              )}
              {!node.children && node.r > 25 && (
                <>
                  <text
                    className="cluster-chart-label"
                    textAnchor="middle"
                    x={node.x}
                    y={node.y - 2}
                  >
                    {short(topic.name, Math.floor(node.r / 3.3))}
                  </text>
                  <text
                    className="cluster-chart-label"
                    textAnchor="middle"
                    x={node.x}
                    y={node.y + 16}
                  >
                    {node.value} chats
                  </text>
                </>
              )}
            </g>
          );
        })}
    </svg>
  );
}
