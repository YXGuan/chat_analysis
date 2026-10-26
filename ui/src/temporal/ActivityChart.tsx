import { useId, useMemo } from "react";
import type { Profile } from "./types";
import { formatDate, percent } from "./types";
import { buildTimeline, GROUPINGS, periodLabel } from "./timeline";
import type { Detail, Grouping } from "./timeline";

export function ActivityChart({
  data,
  user,
  mode,
  highlight,
  grouping,
  detail,
  selectedPeriod,
  onSelect,
}: {
  data: Profile;
  user: string;
  mode: "count" | "share";
  highlight: string | null;
  grouping: Grouping;
  detail: Detail;
  selectedPeriod: string | null;
  onSelect: (category: string, period: string, user: string) => void;
}) {
  const id = useId();
  const { periods, users } = useMemo(
    () => buildTimeline(data, user, grouping, detail),
    [data, user, grouping, detail],
  );
  const W = Math.max(1000, periods.length * (users.length > 1 ? 44 : 28) + 60),
    H = 306,
    left = 42,
    bottom = 34,
    top = 24;
  const height = H - bottom - top,
    step = (W - left - 12) / Math.max(1, periods.length);
  const max =
    mode === "share"
      ? 1
      : Math.max(1, ...users.flatMap((u) => u.periods.map((p) => p.total)));
  const tickMax = mode === "count" ? Math.max(4, Math.ceil(max / 4) * 4) : 1;
  return (
    <div className="weekly-scroll">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ minWidth: W > 1200 ? W : 760 }}
        className="weekly-chart"
        aria-labelledby={`${id}-title`}
        role="group"
      >
        <title id={`${id}-title`}>
          {GROUPINGS.find((g) => g.id === grouping)!.title} by {detail},{" "}
          {user === "all" ? "all users side by side" : user}
        </title>
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i} className="chart-grid">
            <line
              x1={left}
              x2={W - 12}
              y1={top + height * (1 - i / 4)}
              y2={top + height * (1 - i / 4)}
            />
            <text
              x={left - 12}
              y={top + height * (1 - i / 4) + 4}
              textAnchor="end"
            >
              {mode === "share" ? i * 25 + "%" : (tickMax * i) / 4}
            </text>
          </g>
        ))}
        {periods.map((period, wi) => (
          <g key={period}>
            {(wi % Math.max(1, Math.ceil(periods.length / 13)) === 0 ||
              wi === periods.length - 1) && (
              <text
                className="axis-label"
                x={left + step * (wi + 0.5)}
                y={H - 10}
                textAnchor="middle"
              >
                {grouping === "month"
                  ? new Date(period).toLocaleDateString("en-US", {
                      month: "short",
                      year: "numeric",
                      timeZone: "UTC",
                    })
                  : formatDate(period)}
              </text>
            )}
            {users.map((u, ui) => {
              const item = u.periods.find((p) => p.period === period);
              const width = Math.min(36, (step * 0.78) / users.length),
                x =
                  left +
                  step * (wi + 0.5) -
                  (width * users.length) / 2 +
                  ui * width;
              if (!item?.total)
                return item ? (
                  <text
                    key={u.label}
                    x={x + width / 2}
                    y={top + height - 4}
                    textAnchor="middle"
                    className="empty-week"
                  >
                    ·
                  </text>
                ) : null;
              let accumulated = 0;
              return (
                <g key={u.label}>
                  {data.taxonomy.map((topic) => {
                    const count = item.counts[topic.id] || 0;
                    if (!count) return null;
                    const value = mode === "share" ? count / item.total : count,
                      h = (height * value) / tickMax;
                    const y =
                      top + height - (height * (accumulated + value)) / tickMax;
                    accumulated += value;
                    const label = `${u.label}, ${periodLabel(period, grouping)}, ${topic.name}: ${count} of ${item.total} visible chats, ${percent(count / item.total)}`;
                    return (
                      <rect
                        className="weekly-segment"
                        key={topic.id}
                        x={x + 0.75}
                        y={y}
                        width={width - 1.5}
                        height={h}
                        fill={topic.color}
                        opacity={
                          highlight && highlight !== topic.id
                            ? 0.16
                            : users.length > 1
                              ? 1 - ui * 0.18
                              : 1
                        }
                        stroke={
                          selectedPeriod === period
                            ? "var(--foreground)"
                            : "var(--surface)"
                        }
                        strokeWidth={selectedPeriod === period ? 1.3 : 0.5}
                        tabIndex={0}
                        role="button"
                        aria-label={label}
                        onClick={() => onSelect(topic.id, period, u.label)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onSelect(topic.id, period, u.label);
                          }
                        }}
                      >
                        <title>{label}</title>
                      </rect>
                    );
                  })}
                  {periods.length <= 32 && mode === "count" && (
                    <text
                      className="bar-count"
                      x={x + width / 2}
                      y={top + height - (height * item.total) / tickMax - 7}
                      textAnchor="middle"
                    >
                      {item.total}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        ))}
      </svg>
    </div>
  );
}
