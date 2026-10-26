import { useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { Button, Card, SearchField } from "@heroui/react";
import {
  ChevronDown,
  ChevronRight,
  Circle,
  GitBranch,
  List,
  Route,
} from "lucide-react";
import { clusterScope, userColor } from "./clusters";
import type { ClusterScope } from "./clusters";
import { TopicChart } from "./TopicChart";
import { formatDate, LAYOUTS } from "./types";
import type { Chat, Layout, Profile, Topic } from "./types";

const ICONS = { list: List, tree: GitBranch, flow: Route, circle: Circle };

function UserMix({
  topic,
  scope,
  data,
  user,
}: {
  topic: Topic;
  scope: ClusterScope;
  data: Profile;
  user: string;
}) {
  const mix = scope.mixes.get(topic.id)!;
  const label = data.users
    .map((u, i) => `${u.label}: ${mix[i]} chats`)
    .join(", ");
  return (
    <span className="cluster-mix" role="img" aria-label={label} title={label}>
      {mix.map(
        (value, i) =>
          value > 0 && (
            <span
              key={data.users[i].label}
              style={{
                flex: value,
                background:
                  user === "all" || user === data.users[i].label
                    ? userColor(i)
                    : "var(--border)",
              }}
            />
          ),
      )}
    </span>
  );
}

function ClusterList({
  scope,
  data,
  user,
  selected,
  onSelect,
}: {
  scope: ClusterScope;
  data: Profile;
  user: string;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(
    () => new Set(scope.roots.map((t) => t.id)),
  );
  const row = (topic: Topic, depth: number) => {
    const children = scope.children.get(topic.id) || [];
    const open = expanded.has(topic.id);
    return (
      <li key={topic.id}>
        <div
          className={`cluster-row ${selected === topic.id ? "is-selected" : ""}`}
          style={{ "--depth": depth } as CSSProperties}
        >
          {children.length ? (
            <Button
              variant="ghost"
              size="sm"
              isIconOnly
              className="cluster-twisty"
              aria-label={`${open ? "Collapse" : "Expand"} ${topic.name}`}
              aria-expanded={open}
              aria-controls={`branch-${topic.id}`}
              onPress={() =>
                setExpanded((current) => {
                  const next = new Set(current);
                  if (next.has(topic.id)) next.delete(topic.id);
                  else next.add(topic.id);
                  return next;
                })
              }
            >
              {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </Button>
          ) : (
            <span />
          )}
          <Button
            variant="ghost"
            className={`cluster-name ${depth === 0 ? "cluster-root" : ""}`}
            aria-pressed={selected === topic.id}
            onPress={() => onSelect(topic.id)}
          >
            {topic.name}
          </Button>
          <UserMix topic={topic} scope={scope} data={data} user={user} />
          <span className="cluster-count">{scope.count(topic)}</span>
        </div>
        {children.length > 0 && (
          <ul id={`branch-${topic.id}`} hidden={!open}>
            {children.map((child) => row(child, depth + 1))}
          </ul>
        )}
      </li>
    );
  };
  return (
    <>
      <div className="cluster-list-tools">
        <Button
          size="sm"
          variant="outline"
          onPress={() => setExpanded(new Set(scope.topics.map((t) => t.id)))}
        >
          Expand all
        </Button>
        <Button
          size="sm"
          variant="outline"
          onPress={() => setExpanded(new Set())}
        >
          Collapse all
        </Button>
        <span>Chats</span>
      </div>
      <ul className="cluster-list" aria-label="Cluster outline">
        {scope.roots.map((topic) => row(topic, 0))}
      </ul>
    </>
  );
}

function SourceConversation({ chat, color }: { chat: Chat; color: string }) {
  return (
    <article className="cluster-chat">
      <div className="cluster-chat-meta">
        <i className="swatch" style={{ background: color }} />
        <span>
          {chat.metadata.user} · {formatDate(chat.created_at, true)} ·{" "}
          {chat.messages.length} messages
        </span>
      </div>
      <p>
        {chat.summary ||
          chat.messages.find((m) => m.role === "user")?.content ||
          "Conversation"}
      </p>
      <details className="cluster-conversation">
        <summary>
          Show conversation <ChevronRight size={12} />
        </summary>
        {chat.messages.map((message, i) => (
          <div
            key={i}
            className={`cluster-message ${message.role === "assistant" ? "is-assistant" : ""}`}
          >
            <span>{message.role}</span>
            <p>{message.content}</p>
          </div>
        ))}
      </details>
    </article>
  );
}

function ClusterDetails({
  data,
  scope,
  topic,
  user,
  onSelect,
}: {
  data: Profile;
  scope: ClusterScope;
  topic: Topic | null;
  user: string;
  onSelect: (id: string | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(20);
  const ids = topic ? new Set(topic.chats) : null;
  const chats = scope.chats.filter((chat) => !ids || ids.has(chat.chat_id));
  const matches = chats
    .filter(
      (chat) =>
        !query ||
        `${chat.summary || ""} ${chat.messages.map((m) => m.content).join(" ")}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  const children = topic ? scope.children.get(topic.id) || [] : scope.roots;
  const path = topic ? scope.path(topic) : [];
  return (
    <Card
      className="cluster-details"
      aria-label="Cluster details and conversations"
    >
      <Card.Header>
        <nav className="cluster-crumbs" aria-label="Cluster path">
          <button
            onClick={() => onSelect(null)}
            aria-current={!topic ? "page" : undefined}
          >
            All conversations
          </button>
          {path.map((ancestor) => (
            <span key={ancestor.id}>
              <ChevronRight size={11} />
              <button
                onClick={() => onSelect(ancestor.id)}
                aria-current={ancestor.id === topic?.id ? "page" : undefined}
              >
                {ancestor.name}
              </button>
            </span>
          ))}
        </nav>
        <Card.Title>{topic?.name || "All conversations"}</Card.Title>
        <Card.Description>
          {topic?.description ||
            "Choose a cluster to explore its topics and source conversations, or browse the full history below."}
        </Card.Description>
      </Card.Header>
      <Card.Content>
        <p className="cluster-detail-stats">
          {topic && `Level ${path.length} · `}
          {chats.length} chats{user !== "all" && ` from ${user}`}
        </p>
        <div className="cluster-breakdown" aria-label="Chats per user">
          {data.users.map((u, i) => (
            <span
              key={u.label}
              className={user !== "all" && user !== u.label ? "is-muted" : ""}
            >
              <i className="swatch" style={{ background: userColor(i) }} />
              {u.label}: {topic ? scope.mixes.get(topic.id)![i] : u.total}
            </span>
          ))}
        </div>
        {children.length > 0 && (
          <>
            <h3>{topic ? "Smaller clusters inside" : "Browse by cluster"}</h3>
            <ul className="cluster-subtopics">
              {children.map((child) => (
                <li key={child.id}>
                  <button onClick={() => onSelect(child.id)}>
                    {child.name}
                  </button>
                  <span className="cluster-count">{scope.count(child)}</span>
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="cluster-chats-heading">
          <h3>
            Conversations ({matches.length}
            {query ? ` of ${chats.length}` : ""})
          </h3>
          {topic && (
            <button onClick={() => onSelect(null)}>View all chats</button>
          )}
        </div>
        <SearchField
          aria-label="Search cluster conversations"
          value={query}
          onChange={(value) => {
            setQuery(value);
            setLimit(20);
          }}
          variant="secondary"
          className="cluster-search"
        >
          <SearchField.Group>
            <SearchField.SearchIcon />
            <SearchField.Input placeholder="Search these conversations…" />
            <SearchField.ClearButton aria-label="Clear conversation search" />
          </SearchField.Group>
        </SearchField>
        <div className="cluster-chats">
          {matches.slice(0, limit).map((chat) => (
            <SourceConversation
              key={chat.chat_id}
              chat={chat}
              color={userColor(
                data.users.findIndex((u) => u.label === chat.metadata.user),
              )}
            />
          ))}
          {!matches.length && (
            <div className="cluster-empty">
              <p>No conversations match this search.</p>
              <Button variant="outline" size="sm" onPress={() => setQuery("")}>
                Clear search
              </Button>
            </div>
          )}
          {matches.length > limit && (
            <Button
              className="cluster-more"
              variant="outline"
              size="sm"
              onPress={() => setLimit(limit + 20)}
            >
              Show more conversations ({matches.length - limit} remaining)
            </Button>
          )}
        </div>
      </Card.Content>
    </Card>
  );
}

export default function ClusterExplorer({
  data,
  user,
}: {
  data: Profile;
  user: string;
}) {
  const [layout, setLayout] = useState<Layout>("list");
  const [selected, setSelected] = useState<string | null>(null);
  const scope = useMemo(() => clusterScope(data, user), [data, user]);
  const topic =
    selected && scope.counts.get(selected) ? scope.byId.get(selected)! : null;
  const levels = Math.max(0, ...scope.topics.map((t) => scope.path(t).length));
  return (
    <div className="cluster-workspace">
      <Card className="cluster-explorer">
        <Card.Header>
          <Card.Title>Explore the clusters</Card.Title>
          <div
            className="cluster-views"
            role="group"
            aria-label="Choose a cluster view"
          >
            <span>View</span>
            {LAYOUTS.map((view) => {
              const Icon = ICONS[view.id];
              return (
                <Button
                  key={view.id}
                  size="sm"
                  variant="outline"
                  aria-pressed={layout === view.id}
                  onPress={() => setLayout(view.id)}
                >
                  <Icon size={13} />
                  {view.name}
                </Button>
              );
            })}
          </div>
          <p className="cluster-help">
            {LAYOUTS.find((view) => view.id === layout)?.description}
          </p>
          <div className="cluster-legend">
            {data.users.map((u, i) => (
              <span
                key={u.label}
                className={user !== "all" && user !== u.label ? "is-muted" : ""}
              >
                <i className="swatch" style={{ background: userColor(i) }} />
                {u.label}
              </span>
            ))}
          </div>
          <p className="cluster-guide">
            {layout === "list"
              ? "The bar next to each cluster shows its mix of users."
              : layout === "flow"
                ? "Each band’s color shows whose chats it carries."
                : user === "all"
                  ? "Color shows the user with the most chats. Paler clusters mix users."
                  : `Darker clusters contain a larger share of chats from ${user}.`}
          </p>
          <p className="cluster-levels">
            {levels} levels · {scope.roots.length} broad themes ·{" "}
            {scope.topics.length - scope.roots.length} smaller clusters
          </p>
        </Card.Header>
        <Card.Content>
          {layout === "list" ? (
            <ClusterList
              key={user}
              scope={scope}
              data={data}
              user={user}
              selected={topic?.id || null}
              onSelect={setSelected}
            />
          ) : (
            <TopicChart
              scope={scope}
              data={data}
              user={user}
              layout={layout}
              selected={topic?.id || null}
              onSelect={setSelected}
            />
          )}
        </Card.Content>
        <Card.Footer className="cluster-footer">
          <span>Select a cluster to read its chats</span>
          <Button
            size="sm"
            variant="ghost"
            isDisabled={!topic}
            onPress={() => setSelected(null)}
          >
            Clear selection
          </Button>
        </Card.Footer>
      </Card>
      <ClusterDetails
        key={`${user}:${topic?.id || "all"}`}
        data={data}
        scope={scope}
        topic={topic}
        user={user}
        onSelect={setSelected}
      />
    </div>
  );
}
