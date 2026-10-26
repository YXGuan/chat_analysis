import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Button, Card, Tabs } from "@heroui/react";
import {
  ArrowUpRight,
  BarChart3,
  CircleHelp,
  Download,
  Eye,
  EyeOff,
  GitBranch,
  Moon,
  Sun,
} from "lucide-react";
import {
  About,
  Comparison,
  Evidence,
  Insights,
  Stats,
} from "./temporal/Panels";
import { ActivityChart } from "./temporal/ActivityChart";
import ImportHistory from "./temporal/ImportHistory";
import HistorySelect from "./temporal/HistorySelect";
import type { HistoryDataset } from "./temporal/HistorySelect";
const ClusterExplorer = lazy(() => import("./temporal/ClusterExplorer"));
import {
  filterTimeline,
  GROUPINGS,
  periodLabel,
  periodStart,
} from "./temporal/timeline";
import type { Detail, Grouping, Visibility } from "./temporal/timeline";
import type { Profile, Topic, View } from "./temporal/types";

const BUILTIN_DATASETS: HistoryDataset[] = [
  { id: "personal", name: "Sample · personal histories" },
  { id: "research", name: "Sample · science & physics" },
];
const initial = new URLSearchParams(location.search);
const EMPTY_VISIBILITY: Visibility = { themes: [], topics: [] };
const VISIBILITY_KEY = "chat-analysis-visibility";
function savedVisibility(): Record<string, Visibility> {
  try {
    const saved = JSON.parse(localStorage.getItem(VISIBILITY_KEY) || "{}");
    return Object.fromEntries(
      Object.entries(saved).flatMap(([key, value]) => {
        const item = value as Visibility | null;
        return item && Array.isArray(item.themes) && Array.isArray(item.topics)
          ? [
              [
                key,
                {
                  themes: item.themes.filter((id) => typeof id === "string"),
                  topics: item.topics.filter((id) => typeof id === "string"),
                },
              ],
            ]
          : [];
      }),
    );
  } catch {
    return {};
  }
}
function savedGrouping(): Grouping {
  try {
    const value =
      initial.get("group") || localStorage.getItem("chat-analysis-grouping");
    return GROUPINGS.find((g) => g.id === value)?.id || "week";
  } catch {
    return "week";
  }
}

export default function TemporalApp() {
  const [dataset, setDataset] = useState(
    initial.get("dataset") === "research" ||
      /^[a-f0-9]{32}$/.test(initial.get("dataset") || "")
      ? initial.get("dataset")!
      : "personal",
  );
  const [datasets, setDatasets] = useState(() => [
    ...BUILTIN_DATASETS,
    ...(/^[a-f0-9]{32}$/.test(initial.get("dataset") || "")
      ? [{ id: initial.get("dataset")!, name: "My imported history" }]
      : []),
  ]);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/datasets", { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : []))
      .then((saved: HistoryDataset[]) => {
        setDatasets((current) => [
          ...BUILTIN_DATASETS,
          ...saved,
          ...current.filter(
            (item) =>
              !BUILTIN_DATASETS.some((builtin) => builtin.id === item.id) &&
              !saved.some((item2) => item2.id === item.id),
          ),
        ]);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);
  const [view, setView] = useState<View>(
    ["explorer", "conversations"].includes(initial.get("view") || "")
      ? "explorer"
      : "timeline",
  );
  const [user, setUser] = useState(initial.get("user") || "User 1");
  const [data, setData] = useState<Profile | null>(null),
    [error, setError] = useState(""),
    [attempt, setAttempt] = useState(0);
  const [dataDataset, setDataDataset] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail>("themes");
  const [grouping, setGrouping] = useState<Grouping>(savedGrouping);
  const [visibility, setVisibility] = useState(savedVisibility);
  const hidden = visibility[dataset] || EMPTY_VISIBILITY;
  useEffect(() => {
    try {
      localStorage.setItem(VISIBILITY_KEY, JSON.stringify(visibility));
    } catch {
      /* Keep in-memory preferences when browser storage is unavailable. */
    }
  }, [visibility]);
  useEffect(() => {
    try {
      localStorage.setItem("chat-analysis-grouping", grouping);
    } catch {
      /* Grouping also remains in the URL. */
    }
  }, [grouping]);
  const [mode, setMode] = useState<"count" | "share">("count");
  const [category, setCategory] = useState<string | null>(null),
    [period, setPeriod] = useState<string | null>(null),
    [evidenceUser, setEvidenceUser] = useState<string | null>(null);
  const [query, setQuery] = useState(""),
    [dark, setDark] = useState(localStorage.getItem("kura-theme") === "dark");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("kura-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError("");
    setCategory(null);
    setPeriod(null);
    setEvidenceUser(null);
    setQuery("");
    fetch(
      BUILTIN_DATASETS.some((item) => item.id === dataset)
        ? `${import.meta.env.BASE_URL}data/${dataset}.json`
        : `/api/datasets/${dataset}`,
      {
        signal: controller.signal,
      },
    )
      .then((r) => {
        if (!r.ok)
          throw new Error(`Saved analysis could not be loaded (${r.status}).`);
        return r.json();
      })
      .then((d: Profile) => {
        setData(d);
        setDataDataset(dataset);
        setUser((u) =>
          (u === "all" && d.users.length > 1) ||
          d.users.some((x) => x.label === u)
            ? u
            : d.users[0].label,
        );
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [dataset, attempt]);
  useEffect(() => {
    history.replaceState(
      null,
      "",
      `?dataset=${dataset}&view=${view}&user=${encodeURIComponent(user)}&group=${grouping}`,
    );
  }, [dataset, view, user, grouping]);
  const timelineData = useMemo(
    () => (data ? filterTimeline(data, detail, hidden) : null),
    [data, detail, hidden],
  );
  const legend =
    (detail === "topics"
      ? data?.clusters.filter((t) => t.parent_id)
      : data?.taxonomy) || [];
  const hiddenCount = legend.length - (timelineData?.taxonomy.length || 0);
  const shownChats =
    timelineData?.users
      .filter((u) => user === "all" || u.label === user)
      .reduce((sum, u) => sum + u.total, 0) || 0;
  const totalChats =
    data?.users
      .filter((u) => user === "all" || u.label === user)
      .reduce((sum, u) => sum + u.total, 0) || 0;
  const users =
      timelineData?.users.filter((u) => user === "all" || u.label === user) ||
      [],
    reference = users[0];
  const clear = () => {
    setCategory(null);
    setPeriod(null);
    setEvidenceUser(null);
  };
  const showAll = () => {
    setVisibility((current) => ({ ...current, [dataset]: EMPTY_VISIBILITY }));
  };
  const toggleVisibility = (topic: Topic) => {
    const visible = timelineData!.taxonomy.some((t) => t.id === topic.id);
    setVisibility((current) => {
      const previous = current[dataset] || EMPTY_VISIBILITY;
      return {
        ...current,
        [dataset]: {
          ...previous,
          themes:
            detail === "topics" && !visible
              ? previous.themes.filter((id) => id !== topic.parent_id)
              : previous.themes,
          [detail]: visible
            ? [...previous[detail], topic.id]
            : previous[detail].filter((id) => id !== topic.id),
        },
      };
    });
    clear();
  };
  const visibleChats = useMemo(() => {
    if (!timelineData) return [];
    return Object.values(timelineData.chats)
      .filter(
        (c) =>
          (user === "all" || c.metadata.user === user) &&
          (!evidenceUser || c.metadata.user === evidenceUser) &&
          (!category ||
            (detail === "topics" ? c.topic_id : c.category) === category) &&
          (!period || periodStart(c.created_at, grouping) === period) &&
          (!query ||
            `${c.summary || ""} ${c.messages
              .filter((m) => m.role === "user")
              .map((m) => m.content)
              .join(" ")}`
              .toLowerCase()
              .includes(query.toLowerCase())),
      )
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
  }, [
    timelineData,
    user,
    category,
    period,
    evidenceUser,
    query,
    detail,
    grouping,
  ]);
  const exportData = () => {
    if (!data) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `kura-${dataset}-${data.analysis.model}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="?dataset=personal&view=timeline"
          aria-label="Chat Analysis"
        >
          <span className="brand-icon" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>Chat Analysis</span>
        </a>
        <nav aria-label="Main navigation">
          {(
            [
              { id: "timeline", icon: BarChart3, name: "Timeline" },
              { id: "explorer", icon: GitBranch, name: "Topics" },
            ] as const
          ).map((item) => (
            <Button
              key={item.id}
              variant="ghost"
              className={`nav-button ${view === item.id ? "nav-selected" : ""}`}
              onPress={() => {
                setView(item.id);
                clear();
              }}
              aria-current={view === item.id ? "page" : undefined}
              aria-label={item.name}
            >
              <item.icon size={17} />
              <span>{item.name}</span>
            </Button>
          ))}
        </nav>
      </aside>
      <div className="workspace">
        <header className="app-header">
          <div className="breadcrumb">
            <span>{datasets.find((d) => d.id === dataset)?.name}</span>
          </div>
          <div className="header-actions">
            <Button
              isIconOnly
              size="sm"
              variant="ghost"
              aria-label={dark ? "Use light theme" : "Use dark theme"}
              onPress={() => setDark(!dark)}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </Button>
            <About data={data} />
            <ImportHistory
              onImported={(id, name) => {
                setDatasets((current) => [
                  ...current.filter((item) => item.id !== id),
                  { id, name },
                ]);
                setDataset(id);
                setView("timeline");
                setUser("You");
                clear();
              }}
            />
            <Button
              size="sm"
              variant="outline"
              onPress={exportData}
              isDisabled={!data}
            >
              <Download size={14} />
              Export data
            </Button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <h1>{view === "timeline" ? "Timeline" : "Topics"}</h1>
            </div>
            <HistorySelect
              datasets={datasets}
              dataset={dataset}
              user={user}
              data={dataDataset === dataset ? data : null}
              onChange={(nextDataset, nextUser) => {
                setDataset(nextDataset);
                setUser(nextUser);
                clear();
                setQuery("");
              }}
            />
          </div>
          {error ? (
            <Card className="error-card">
              <CircleHelp size={25} />
              <Card.Title>We couldn’t open this analysis.</Card.Title>
              <Card.Description>{error}</Card.Description>
              <Button
                variant="secondary"
                onPress={() => setAttempt(attempt + 1)}
              >
                Try again
              </Button>
            </Card>
          ) : !data || !reference ? (
            <div className="loading-state">
              <div className="loading-line" />
              <p>Opening the saved analysis…</p>
            </div>
          ) : (
            <>
              <Stats
                data={view === "timeline" ? timelineData! : data}
                user={user}
                detail={view === "timeline" ? detail : "themes"}
                filtered={view === "timeline" && hiddenCount > 0}
              />
              {view === "timeline" && (
                <>
                  <Card className="timeline-card">
                    <Card.Header className="chart-heading">
                      <div>
                        <Card.Title>
                          {GROUPINGS.find((g) => g.id === grouping)!.title}
                        </Card.Title>
                        <Card.Description>
                          {shownChats} of {totalChats} chats shown · shares use
                          visible chats
                        </Card.Description>
                      </div>
                      <Tabs
                        selectedKey={mode}
                        onSelectionChange={(key) =>
                          setMode(String(key) as "count" | "share")
                        }
                        variant="secondary"
                      >
                        <Tabs.ListContainer>
                          <Tabs.List aria-label="Chart metric">
                            <Tabs.Tab id="count">
                              Count
                              <Tabs.Indicator />
                            </Tabs.Tab>
                            <Tabs.Tab id="share">
                              Share
                              <Tabs.Indicator />
                            </Tabs.Tab>
                          </Tabs.List>
                        </Tabs.ListContainer>
                      </Tabs>
                    </Card.Header>
                    <Card.Content>
                      <div className="chart-granularity">
                        <Tabs
                          selectedKey={detail}
                          onSelectionChange={(key) => {
                            setDetail(String(key) as "themes" | "topics");
                            clear();
                          }}
                          variant="secondary"
                        >
                          <Tabs.ListContainer>
                            <Tabs.List aria-label="Topic detail">
                              <Tabs.Tab id="themes">
                                Themes
                                <Tabs.Indicator />
                              </Tabs.Tab>
                              <Tabs.Tab id="topics">
                                Topics
                                <Tabs.Indicator />
                              </Tabs.Tab>
                            </Tabs.List>
                          </Tabs.ListContainer>
                        </Tabs>
                        <Tabs
                          selectedKey={grouping}
                          onSelectionChange={(key) => {
                            setGrouping(String(key) as Grouping);
                            clear();
                          }}
                          variant="secondary"
                        >
                          <Tabs.ListContainer>
                            <Tabs.List aria-label="Group activity by">
                              {GROUPINGS.map((g) => (
                                <Tabs.Tab id={g.id} key={g.id}>
                                  {g.label}
                                  <Tabs.Indicator />
                                </Tabs.Tab>
                              ))}
                            </Tabs.List>
                          </Tabs.ListContainer>
                        </Tabs>
                      </div>
                      <div className="visibility-heading">
                        <span>
                          Click a {detail === "themes" ? "theme" : "topic"} to
                          hide or show it
                        </span>
                        {hiddenCount > 0 && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onPress={() => {
                              showAll();
                              clear();
                            }}
                          >
                            Show all ({hiddenCount} hidden)
                          </Button>
                        )}
                      </div>
                      <div
                        className="legend"
                        aria-label={`${detail === "themes" ? "Theme" : "Topic"} visibility`}
                      >
                        {legend.map((t) => {
                          const visible = timelineData!.taxonomy.some(
                            (item) => item.id === t.id,
                          );
                          return (
                            <Button
                              key={t.id}
                              size="sm"
                              variant="ghost"
                              aria-label={`${visible ? "Hide" : "Show"} ${t.name}`}
                              aria-pressed={visible}
                              className={`legend-button ${visible ? "legend-visible" : "legend-hidden"}`}
                              onPress={() => toggleVisibility(t)}
                            >
                              <i
                                className="swatch"
                                style={{ background: t.color }}
                              />
                              <span>{t.name}</span>
                              {visible ? (
                                <Eye size={12} />
                              ) : (
                                <EyeOff size={12} />
                              )}
                            </Button>
                          );
                        })}
                      </div>
                      {timelineData!.taxonomy.length ? (
                        <ActivityChart
                          data={timelineData!}
                          user={user}
                          mode={mode}
                          highlight={category}
                          grouping={grouping}
                          detail={detail}
                          selectedPeriod={period}
                          onSelect={(c, w, u) => {
                            setCategory(c);
                            setPeriod(w);
                            setEvidenceUser(u);
                          }}
                        />
                      ) : (
                        <div className="chart-empty">
                          <EyeOff size={24} />
                          <p>All {detail} are hidden.</p>
                          <Button variant="secondary" onPress={showAll}>
                            Show all {detail}
                          </Button>
                        </div>
                      )}
                    </Card.Content>
                  </Card>
                  <div className="section-title">
                    <h2>Changes</h2>
                    <span>
                      {reference.label} · first{" "}
                      {reference.comparison.window_weeks} vs last{" "}
                      {reference.comparison.window_weeks} weeks
                    </span>
                  </div>
                  <Insights data={timelineData!} user={reference.label} />
                  <div className="lower-grid">
                    <Comparison data={timelineData!} user={reference.label} />
                    <Evidence
                      chats={visibleChats}
                      data={data}
                      heading="Conversations"
                      filter={[
                        evidenceUser || (user === "all" ? "All users" : user),
                        period && periodLabel(period, grouping),
                        hiddenCount > 0 &&
                          `${hiddenCount} ${hiddenCount === 1 ? (detail === "themes" ? "theme" : "topic") : detail} hidden`,
                        category &&
                          timelineData!.taxonomy.find((t) => t.id === category)
                            ?.name,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                      filtered={!!(category || period || hiddenCount)}
                      clear={() => {
                        clear();
                        showAll();
                      }}
                      query={query}
                      setQuery={setQuery}
                    />
                  </div>
                </>
              )}
              {view === "explorer" && (
                <Suspense
                  fallback={
                    <div className="chart-empty">Opening the clusters…</div>
                  }
                >
                  <ClusterExplorer
                    key={`${dataset}:${user}`}
                    data={data}
                    user={user}
                  />
                </Suspense>
              )}
              <footer className="workspace-footer">
                {data.source.url ? (
                  <a href={data.source.url} target="_blank" rel="noreferrer">
                    {data.source.name} · {data.source.license}
                    <ArrowUpRight size={12} />
                  </a>
                ) : (
                  <span>{data.source.name} · Saved on this computer</span>
                )}
              </footer>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
