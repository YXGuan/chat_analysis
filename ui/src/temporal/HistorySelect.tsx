import { useEffect, useState } from "react";
import { Header, Label, ListBox, Select } from "@heroui/react";
import type { Profile } from "./types";

type HistoryUser = { label: string; total: number };
export type HistoryDataset = { id: string; name: string; chats?: number };
const SAMPLES = ["personal", "research"];
const displayName = (name: string) =>
  name
    .replace(/^Sample · /, "")
    .replace(/^./, (letter) => letter.toUpperCase());
const historyKey = (dataset: string, user: string) => `${dataset}:${user}`;

export default function HistorySelect({
  datasets,
  dataset,
  user,
  data,
  onChange,
}: {
  datasets: HistoryDataset[];
  dataset: string;
  user: string;
  data: Profile | null;
  onChange: (dataset: string, user: string) => void;
}) {
  const [sampleUsers, setSampleUsers] = useState<Record<string, HistoryUser[]>>(
    {},
  );
  useEffect(() => {
    const controller = new AbortController();
    for (const id of SAMPLES) {
      fetch(`${import.meta.env.BASE_URL}data/${id}.json`, {
        signal: controller.signal,
      })
        .then((response) => {
          if (!response.ok) throw new Error("History unavailable");
          return response.json();
        })
        .then((profile: Profile) =>
          setSampleUsers((current) => ({
            ...current,
            [id]: profile.users.map(({ label, total }) => ({ label, total })),
          })),
        )
        .catch(() => {});
    }
    return () => controller.abort();
  }, []);

  const samples = datasets.filter((item) => SAMPLES.includes(item.id));
  const imported = datasets.filter((item) => !SAMPLES.includes(item.id));
  const name = displayName(
    datasets.find((item) => item.id === dataset)?.name || "Choose a history",
  );
  const usersFor = (id: string) =>
    id === dataset && data ? data.users : sampleUsers[id] || [];
  const currentUsers = usersFor(dataset);
  const subtitle =
    SAMPLES.includes(dataset) && currentUsers.length > 1
      ? user === "all"
        ? "All conversations"
        : user
      : null;
  const sampleGroups = samples.map((sample) => {
    const users = usersFor(sample.id);
    return {
      ...sample,
      users: users.length
        ? users
        : [
            {
              label: sample.id === dataset ? user : "User 1",
              total: undefined,
            },
          ],
    };
  });

  return (
    <Select
      aria-label="Choose a history"
      className="history-select"
      value={historyKey(dataset, user)}
      onChange={(key) => {
        if (!key) return;
        const value = String(key),
          divider = value.indexOf(":");
        onChange(value.slice(0, divider), value.slice(divider + 1));
      }}
    >
      <Select.Trigger>
        <Select.Value>
          {() => (
            <span className="history-selected-value">
              <span>{name}</span>
              {subtitle && (
                <span className="history-selected-user">{subtitle}</span>
              )}
            </span>
          )}
        </Select.Value>
        <Select.Indicator />
      </Select.Trigger>
      <Select.Popover className="history-popover" placement="bottom end">
        <ListBox aria-label="Conversation histories">
          {imported.length > 0 && (
            <ListBox.Section id="your-histories">
              <Header>Your histories</Header>
              {imported.map((history) => {
                const total =
                  history.chats ??
                  (history.id === dataset && data?.users[0]?.label === "You"
                    ? data.users[0].total
                    : undefined);
                return (
                  <ListBox.Item
                    key={history.id}
                    id={historyKey(history.id, "You")}
                    textValue={history.name}
                    className="history-option"
                  >
                    <Label>{history.name}</Label>
                    {total !== undefined && (
                      <span className="history-option-count">
                        {total} chats
                      </span>
                    )}
                    <ListBox.ItemIndicator />
                  </ListBox.Item>
                );
              })}
            </ListBox.Section>
          )}
          {sampleGroups.map((sample) => (
            <ListBox.Section key={sample.id} id={sample.id}>
              <Header>
                {displayName(sample.name)}
                <span className="history-sample-label">Sample</span>
              </Header>
              {sample.users.map((history) => (
                <ListBox.Item
                  key={history.label}
                  id={historyKey(sample.id, history.label)}
                  textValue={`${displayName(sample.name)} · ${history.label}`}
                  className="history-option"
                >
                  <Label>{history.label}</Label>
                  {history.total !== undefined && (
                    <span className="history-option-count">
                      {history.total} chats
                    </span>
                  )}
                  <ListBox.ItemIndicator />
                </ListBox.Item>
              ))}
              {sample.users.length > 1 && (
                <ListBox.Item
                  id={historyKey(sample.id, "all")}
                  textValue={`${displayName(sample.name)} · All conversations`}
                  className="history-option history-option-all"
                >
                  <Label>All conversations</Label>
                  <span className="history-option-count">
                    {sample.users.reduce(
                      (total, history) => total + (history.total || 0),
                      0,
                    )}{" "}
                    chats
                  </span>
                  <ListBox.ItemIndicator />
                </ListBox.Item>
              )}
            </ListBox.Section>
          ))}
        </ListBox>
      </Select.Popover>
    </Select>
  );
}
