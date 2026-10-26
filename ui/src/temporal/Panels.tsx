import { Button, Card, Chip, Modal, SearchField } from "@heroui/react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  ChevronRight,
  CircleHelp,
  MessageSquare,
  RotateCcw,
  Sparkles,
  X,
} from "lucide-react";
import type { Chat, Profile } from "./types";
import { change, formatDate, percent } from "./types";

export function Stats({
  data,
  user,
  detail = "themes",
  filtered = false,
}: {
  data: Profile;
  user: string;
  detail?: "themes" | "topics";
  filtered?: boolean;
}) {
  const users = data.users.filter((u) => user === "all" || u.label === user),
    total = users.reduce((s, u) => s + u.total, 0),
    active = new Set(
      users.flatMap((u) => u.weeks.filter((w) => w.total).map((w) => w.week)),
    ).size;
  const first = users.map((u) => u.first).sort()[0],
    last = users
      .map((u) => u.last)
      .sort()
      .reverse()[0];
  const items = [
    {
      label: filtered ? "Visible chats" : "Chats",
      value: total,
    },
    {
      label: "Active weeks",
      value: active,
    },
    {
      label: filtered
        ? `Visible ${detail}`
        : detail === "topics"
          ? "Topics"
          : "Themes",
      value: data.taxonomy.length,
    },
    {
      label: "Date range",
      value: `${formatDate(first, true)} – ${formatDate(last, true)}`,
    },
  ];
  return (
    <dl className="stats-grid">
      {items.map((s) => (
        <div key={s.label} className="stat-item">
          <dt>{s.label}</dt>
          <dd>{s.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Insights({ data, user }: { data: Profile; user: string }) {
  const cmp = data.users.find((u) => u.label === user)!.comparison,
    shifts = cmp.shifts.filter((s) => s.delta !== null);
  const up = shifts
      .filter((s) => s.delta! > 0)
      .sort((a, b) => b.delta! - a.delta!)[0],
    down = shifts
      .filter((s) => s.delta! < 0)
      .sort((a, b) => a.delta! - b.delta!)[0],
    recurring = shifts
      .filter((s) => s.early_count >= 2 && s.late_count >= 2)
      .sort(
        (a, b) =>
          Number(b.stable) - Number(a.stable) ||
          b.active_weeks - a.active_weeks,
      )[0];
  return (
    <div className="insight-grid">
      {[
        { label: "Increasing", shift: up, icon: ArrowUpRight },
        { label: "Recurring", shift: recurring, icon: RotateCcw },
        { label: "Decreasing", shift: down, icon: ArrowDownLeft },
      ].map((item, i) => {
        const t = data.taxonomy.find((t) => t.id === item.shift?.category);
        return (
          <Card className={`insight-card insight-${i}`} key={item.label}>
            <div className="insight-top">
              <span className="insight-icon">
                <item.icon size={17} />
              </span>
              <span>{item.label}</span>
            </div>
            <Card.Title>
              {!cmp.sufficient
                ? "Not enough history"
                : t?.name || "No clear pattern"}
            </Card.Title>
            <Card.Description>
              {!cmp.sufficient
                ? `${cmp.min_window_chats} chats per window required`
                : item.shift
                  ? i === 1
                    ? `${item.shift.active_weeks} active weeks · ${percent(item.shift.early_share)} → ${percent(item.shift.late_share)}`
                    : `${percent(item.shift.early_share)} → ${percent(item.shift.late_share)}`
                  : "—"}
            </Card.Description>
            {cmp.sufficient && item.shift && i !== 1 && (
              <strong className="insight-delta">
                {change(item.shift.delta)}
              </strong>
            )}
          </Card>
        );
      })}
    </div>
  );
}

export function Comparison({ data, user }: { data: Profile; user: string }) {
  const cmp = data.users.find((u) => u.label === user)!.comparison;
  return (
    <Card className="comparison-card">
      <Card.Header>
        <Card.Title>Topic comparison</Card.Title>
        <Card.Description>
          First / last {cmp.window_weeks} calendar weeks · {user}
        </Card.Description>
      </Card.Header>
      <Card.Content>
        <table className="data-table">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Early</th>
              <th>Late</th>
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {[...cmp.shifts]
              .sort((a, b) => (b.late_share || 0) - (a.late_share || 0))
              .map((s) => (
                <tr key={s.category}>
                  <td>
                    <i
                      className="swatch"
                      style={{
                        background: data.taxonomy.find(
                          (t) => t.id === s.category,
                        )?.color,
                      }}
                    />
                    {data.taxonomy.find((t) => t.id === s.category)?.name}
                  </td>
                  <td title={`${s.early_count} chats`}>
                    {percent(s.early_share)}
                  </td>
                  <td title={`${s.late_count} chats`}>
                    {percent(s.late_share)}
                  </td>
                  <td
                    className={
                      s.delta && s.delta > 0
                        ? "positive"
                        : s.delta && s.delta < 0
                          ? "negative"
                          : ""
                    }
                  >
                    {change(s.delta)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        <p className="comparison-dates">
          Early: weeks of {formatDate(cmp.early.first)} –{" "}
          {formatDate(cmp.early.last, true)}
          <br />
          Late: weeks of {formatDate(cmp.late.first)} –{" "}
          {formatDate(cmp.late.last, true)}
        </p>
      </Card.Content>
    </Card>
  );
}

export function Evidence({
  chats,
  data,
  heading,
  filter,
  filtered,
  clear,
  query,
  setQuery,
  wide = false,
}: {
  chats: Chat[];
  data: Profile;
  heading: string;
  filter: string;
  filtered: boolean;
  clear: () => void;
  query: string;
  setQuery: (q: string) => void;
  wide?: boolean;
}) {
  return (
    <Card className={`evidence-card ${wide ? "evidence-wide" : ""}`}>
      <Card.Header className="evidence-header">
        <div>
          <Card.Title>{heading}</Card.Title>
          <Card.Description>{filter}</Card.Description>
        </div>
        <Chip size="sm" variant="soft">
          {chats.length} chats
        </Chip>
        {filtered && (
          <Button
            variant="ghost"
            size="sm"
            isIconOnly
            aria-label="Clear filters"
            onPress={clear}
          >
            <X size={15} />
          </Button>
        )}
      </Card.Header>
      <Card.Content>
        <SearchField
          aria-label="Search conversations"
          value={query}
          onChange={setQuery}
          className="chat-search"
          variant="secondary"
        >
          <SearchField.Group>
            <SearchField.SearchIcon />
            <SearchField.Input placeholder="Search conversations…" />
            <SearchField.ClearButton />
          </SearchField.Group>
        </SearchField>
        <div className="conversation-list">
          {chats.length ? (
            chats.map((c) => (
              <details className="conversation" key={c.chat_id}>
                <summary>
                  <div className="conversation-meta">
                    <span>
                      {formatDate(c.created_at, true)} · {c.metadata.user}
                    </span>
                    <span>
                      {data.clusters.find((t) => t.id === c.topic_id)?.name ||
                        data.taxonomy.find((t) => t.id === c.category)?.name}
                    </span>
                    <ChevronRight size={13} />
                  </div>
                  <p>
                    {c.summary ||
                      c.messages.find(
                        (m) =>
                          m.role === "user" &&
                          m.content.trim().toLowerCase() !== "hi",
                      )?.content ||
                      c.messages[0]?.content}
                  </p>
                </summary>
                <div className="annotation">
                  <Sparkles size={13} />
                  <span>
                    {data.analysis.model} ·{" "}
                    {typeof c.confidence === "number"
                      ? `${Math.round(c.confidence * 100)}% model confidence (uncalibrated)`
                      : "topic annotation"}
                    {c.note ? ` · ${c.note}` : ""}
                  </span>
                </div>
                {c.messages.map((m, i) => (
                  <div className={`chat-message message-${m.role}`} key={i}>
                    <span>{m.role}</span>
                    <p>{m.content}</p>
                  </div>
                ))}
              </details>
            ))
          ) : (
            <div className="empty-state">
              <MessageSquare size={24} />
              <p>No conversations match this selection.</p>
              <Button
                variant="secondary"
                onPress={() => {
                  clear();
                  setQuery("");
                }}
              >
                Clear filters
              </Button>
            </div>
          )}
        </div>
      </Card.Content>
    </Card>
  );
}

export function About({ data }: { data: Profile | null }) {
  return (
    <Modal>
      <Button
        size="sm"
        isIconOnly
        variant="ghost"
        aria-label="About this analysis"
      >
        <CircleHelp size={17} />
      </Button>
      <Modal.Backdrop>
        <Modal.Container size="lg">
          <Modal.Dialog>
            <Modal.CloseTrigger />
            <Modal.Header>
              <Modal.Icon>
                <Sparkles size={22} />
              </Modal.Icon>
              <Modal.Heading>About this analysis</Modal.Heading>
            </Modal.Header>
            <Modal.Body className="method-body">
              {data?.source.kind === "chatgpt" ? (
                <p>
                  This analysis uses the selected period from your ChatGPT
                  export. It follows each conversation’s selected branch, keeps
                  readable user and assistant text, and uses only user messages
                  for topic analysis. Images, audio, attachments, and hidden
                  reasoning are excluded. Private imports and analysis results
                  are saved on this computer.
                </p>
              ) : (
                <p>
                  These are partial conversation histories from AllenAI
                  WildChat-4.8M. A user group shares an IP hash and browser
                  details. Shared networks can merge people; network and browser
                  changes can split a history.
                </p>
              )}
              <h3>One taxonomy, across every week</h3>
              <p>
                GPT-6 Luna reads retained user messages, creates broad themes
                and specific topics, and assigns each chat once. Grammar
                requests keep their subject matter. These labels and model
                confidence are interpretive and can be wrong. Inspect the
                conversations.
              </p>
              <h3>Compare like with like</h3>
              <p>
                Group activity by UTC day, Monday–Sunday week, two-week period,
                or calendar month. Two-week periods use consistent Monday
                boundaries across histories. Empty periods remain visible. Hide
                themes or topics using the chart labels; your browser remembers
                the selection for each history. Share mode divides by that
                user's visible chats in each period. Hidden themes also hide
                their topics. Summary counts and changes use visible chats.
                Changes compare the first and last four calendar weeks of each
                user's own span. Non-overlapping windows each need at least five
                chats.
              </p>
              <p>
                A recurring focus has at least two chats in each window. The
                card prefers a similar share (within 10 percentage points), then
                the topic seen in the most active weeks. These rules are
                descriptive and do not establish statistical significance or
                lasting personal interests.
              </p>
              <h3>Analysis provenance</h3>
              <div className="provenance-grid">
                <span>Model</span>
                <b>{data?.analysis.model || "—"}</b>
                <span>Execution</span>
                <b>
                  {data?.analysis.execution === "codex-session"
                    ? "GPT-6 Luna agent in this Codex session"
                    : data?.analysis.execution || "—"}
                </b>
                <span>Coverage</span>
                <b>
                  {data?.analysis.input_chats || 0} chats · one label per chat
                </b>
              </div>
              <p className="checksum">
                Source SHA-256: {data?.analysis.source_sha256 || "—"}
              </p>
              {data?.source.url && (
                <a href={data.source.url} target="_blank" rel="noreferrer">
                  {data.source.name} · {data.source.license}{" "}
                  <ArrowUpRight size={12} />
                </a>
              )}
            </Modal.Body>
            <Modal.Footer>
              <Button slot="close" variant="secondary">
                Done
              </Button>
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  );
}
