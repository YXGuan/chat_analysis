import { useEffect, useRef, useState } from "react";
import { Button, Modal } from "@heroui/react";
import {
  ArrowRight,
  Check,
  FileJson,
  FolderOpen,
  LoaderCircle,
  Upload,
  X,
} from "lucide-react";
import { formatDate } from "./types";

type Preview = {
  id: string;
  files: number;
  total: number;
  readable: number;
  selected: number;
  selected_skipped: number;
  selected_messages: number;
  from: string;
  to: string;
  months: number;
  duplicates: number;
};
type Job = {
  id: string;
  import_id: string;
  dataset_id: string;
  name: string;
  months: number;
  stage: "queued" | "analyzing" | "validating" | "complete" | "failed";
  message: string;
  error: string | null;
  preview: Preview;
};
const PERIODS = [
  { months: 1, name: "1 month" },
  { months: 3, name: "3 months" },
  { months: 6, name: "6 months" },
  { months: 12, name: "1 year" },
  { months: 0, name: "All history" },
];

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new Error(
      "The local import service is unavailable. Run npm run dev from the repository root, then try again.",
    );
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error(
      "Start the local import service with npm run dev from the repository root, then try again.",
    );
  }
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "The import could not finish. Check your export and try again.",
    );
  return body;
}

export default function ImportHistory({
  onImported,
}: {
  onImported: (id: string, name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [jobId, setJobId] = useState<string | null>(() =>
    localStorage.getItem("kura-import-job"),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("My ChatGPT history");
  const [localPath, setLocalPath] = useState("");
  const [dragging, setDragging] = useState(false);
  const [service, setService] = useState<"checking" | "ready" | "offline">(
    "checking",
  );
  const fileInput = useRef<HTMLInputElement>(null),
    folderInput = useRef<HTMLInputElement>(null);
  const previewRequest = useRef(0);
  const working =
    !!jobId &&
    (!job || ["queued", "analyzing", "validating"].includes(job.stage));

  useEffect(() => {
    if (!open) return;
    let active = true;
    request<{ model: string }>("/api/status")
      .then(() => {
        if (active) setService("ready");
      })
      .catch(() => {
        if (active) setService("offline");
      });
    return () => {
      active = false;
    };
  }, [open]);

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const value = await request<Job>(`/api/jobs/${jobId}`);
        if (!active) return;
        setJob(value);
        setPreview({ ...value.preview, id: value.import_id });
        setName(value.name);
        setError("");
        if (!["complete", "failed"].includes(value.stage))
          timer = setTimeout(poll, 1500);
      } catch (failure) {
        if (active) {
          setError((failure as Error).message);
          timer = setTimeout(poll, 5000);
        }
      }
    }
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [jobId]);

  const receive = (value: Preview) => {
    setPreview(value);
    setJob(null);
    setJobId(null);
    setError("");
    localStorage.removeItem("kura-import-job");
  };
  const upload = async (files: File[]) => {
    if (!files.length || working) return;
    setBusy(true);
    setError("");
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    try {
      receive(
        await request<Preview>("/api/imports", { method: "POST", body: form }),
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const importPath = async () => {
    setBusy(true);
    setError("");
    try {
      receive(
        await request<Preview>("/api/imports/local", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: localPath.trim() }),
        }),
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const changePeriod = async (months: number) => {
    if (!preview || busy || working) return;
    const sequence = ++previewRequest.current;
    setBusy(true);
    setError("");
    try {
      const next = await request<Preview>(
        `/api/imports/${preview.id}?months=${months}`,
      );
      if (sequence === previewRequest.current) {
        setPreview(next);
        setJob(null);
        setJobId(null);
        localStorage.removeItem("kura-import-job");
      }
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      if (sequence === previewRequest.current) setBusy(false);
    }
  };
  const analyze = async () => {
    if (!preview) return;
    setBusy(true);
    setError("");
    try {
      const value = await request<Job>(`/api/imports/${preview.id}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ months: preview.months, name }),
      });
      setJob(value);
      setJobId(value.id);
      localStorage.setItem("kura-import-job", value.id);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const reset = () => {
    setPreview(null);
    setJob(null);
    setJobId(null);
    setError("");
    localStorage.removeItem("kura-import-job");
  };

  return (
    <>
      <Button
        size="sm"
        variant="secondary"
        className="import-trigger"
        aria-label="Import history"
        onPress={() => setOpen(true)}
      >
        <Upload size={14} />
        <span>Import history</span>
        {working && (
          <span
            className="import-active-dot"
            aria-label="Analysis in progress"
          />
        )}
      </Button>
      <Modal.Backdrop isOpen={open} onOpenChange={setOpen}>
        <Modal.Container size="lg" scroll="inside">
          <Modal.Dialog className="history-dialog">
            <Modal.CloseTrigger />
            <Modal.Header>
              <p className="import-eyebrow">
                YOUR CONVERSATIONS, YOUR PERSPECTIVE
              </p>
              <Modal.Heading>Bring your history.</Modal.Heading>
              <p className="import-intro">
                Turn a ChatGPT export into a timeline of what you’ve been
                exploring.
              </p>
            </Modal.Header>
            <Modal.Body>
              <ol className="import-steps" aria-label="Import progress">
                {["Choose export", "Pick a period", "Explore"].map(
                  (label, i) => (
                    <li
                      key={label}
                      className={
                        (preview ? 1 : 0) >= i || job?.stage === "complete"
                          ? "is-current"
                          : ""
                      }
                    >
                      <span>
                        {job?.stage === "complete" || (preview && i === 0) ? (
                          <Check size={12} />
                        ) : (
                          i + 1
                        )}
                      </span>
                      {label}
                    </li>
                  ),
                )}
              </ol>
              {service === "offline" && (
                <div className="import-notice" role="status">
                  <strong>Start the local import service</strong>
                  <p>
                    From the repository root, run <code>npm run dev</code>. Your
                    saved examples remain available.
                  </p>
                </div>
              )}
              {!preview && !working && (
                <>
                  <div
                    className={`import-drop ${dragging ? "is-dragging" : ""}`}
                    onDragOver={(event) => {
                      event.preventDefault();
                      setDragging(true);
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(event) => {
                      event.preventDefault();
                      setDragging(false);
                      void upload(Array.from(event.dataTransfer.files));
                    }}
                  >
                    {busy ? (
                      <LoaderCircle className="import-spinner" size={28} />
                    ) : (
                      <FileJson size={30} />
                    )}
                    <strong>
                      {busy
                        ? "Reading your export…"
                        : "Drop your ChatGPT export here"}
                    </strong>
                    <p>
                      Export ZIP, conversations.json, or all
                      conversations-*.json files.
                    </p>
                    <div className="import-file-actions">
                      <Button
                        variant="secondary"
                        size="sm"
                        isDisabled={busy || service !== "ready"}
                        onPress={() => fileInput.current?.click()}
                      >
                        <Upload size={14} />
                        Choose files
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        isDisabled={busy || service !== "ready"}
                        onPress={() => folderInput.current?.click()}
                      >
                        <FolderOpen size={14} />
                        Choose folder
                      </Button>
                    </div>
                    <input
                      ref={fileInput}
                      type="file"
                      multiple
                      accept=".json,.zip"
                      hidden
                      aria-label="Choose ChatGPT export files"
                      onChange={(event) => {
                        void upload(Array.from(event.target.files || []));
                        event.target.value = "";
                      }}
                    />
                    <input
                      ref={(node) => {
                        folderInput.current = node;
                        if (node) node.webkitdirectory = true;
                      }}
                      type="file"
                      multiple
                      hidden
                      aria-label="Choose ChatGPT export folder"
                      onChange={(event) => {
                        const files = Array.from(
                          event.target.files || [],
                        ).filter((file) =>
                          /^conversations.*\.json$/i.test(file.name),
                        );
                        if (!files.length)
                          setError(
                            "This folder has no conversation JSON files.",
                          );
                        else void upload(files);
                        event.target.value = "";
                      }}
                    />
                  </div>
                  <details className="import-help">
                    <summary>Where do I find my export?</summary>
                    <p>
                      In ChatGPT, open Settings → Data controls → Export data.
                      Download the ZIP from your export email. You can choose
                      that ZIP directly, or select the extracted folder.
                    </p>
                  </details>
                  <details className="import-help">
                    <summary>Use a local export path</summary>
                    <div className="import-path">
                      <label htmlFor="history-path">
                        Export folder, JSON, or ZIP path
                      </label>
                      <input
                        id="history-path"
                        value={localPath}
                        onChange={(event) => setLocalPath(event.target.value)}
                        placeholder="/Users/you/Downloads/chatgpt-export"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        isDisabled={
                          !localPath.trim() || busy || service !== "ready"
                        }
                        onPress={() => void importPath()}
                      >
                        Read export
                      </Button>
                    </div>
                  </details>
                </>
              )}
              {preview && (
                <div className="import-preview">
                  <div className="import-preview-heading">
                    <span>
                      <Check size={15} />
                      Export ready
                    </span>
                    {!working && (
                      <Button size="sm" variant="ghost" onPress={reset}>
                        <X size={12} />
                        Change file
                      </Button>
                    )}
                  </div>
                  <p>
                    {preview.total.toLocaleString()}{" "}
                    {preview.total === 1 ? "conversation" : "conversations"}{" "}
                    found across {preview.files}{" "}
                    {preview.files === 1 ? "file" : "files"}.
                  </p>
                  <label className="import-label">Start with a period</label>
                  <div
                    className="import-periods"
                    role="group"
                    aria-label="History period"
                  >
                    {PERIODS.map((period) => (
                      <Button
                        size="sm"
                        variant="outline"
                        key={period.months}
                        aria-pressed={preview.months === period.months}
                        isDisabled={busy || working}
                        onPress={() => void changePeriod(period.months)}
                      >
                        {period.name}
                      </Button>
                    ))}
                  </div>
                  <div className="import-selection" aria-live="polite">
                    <strong>
                      {preview.selected.toLocaleString()}{" "}
                      {preview.selected === 1
                        ? "conversation"
                        : "conversations"}
                    </strong>
                    <span>
                      {formatDate(preview.from, true)} –{" "}
                      {formatDate(preview.to, true)}
                    </span>
                    <small>
                      {preview.months
                        ? "Latest months in this export, based on conversation creation date."
                        : "All readable conversations in this export."}
                    </small>
                  </div>
                  {preview.selected_skipped > 0 && (
                    <p className="import-fine">
                      {preview.selected_skipped} chats with no readable user
                      text are skipped. Images, audio, and attachments aren’t
                      analyzed.
                    </p>
                  )}
                  <label className="import-label" htmlFor="history-name">
                    Name your history
                  </label>
                  <input
                    className="import-name"
                    id="history-name"
                    value={name}
                    maxLength={100}
                    disabled={working || job?.stage === "complete"}
                    onChange={(event) => setName(event.target.value)}
                  />
                </div>
              )}
              {(working ||
                job?.stage === "complete" ||
                job?.stage === "failed") && (
                <div
                  className={`import-job ${job?.stage === "failed" ? "is-failed" : ""}`}
                  aria-live="polite"
                >
                  {working ? (
                    <LoaderCircle className="import-spinner" size={18} />
                  ) : job?.stage === "complete" ? (
                    <Check size={18} />
                  ) : (
                    <X size={18} />
                  )}
                  <div>
                    <strong>
                      {job?.message || "Reconnecting to your analysis…"}
                    </strong>
                    <p>
                      {job?.error ||
                        (working
                          ? "You can close this dialog. Progress is saved and your history will be here when it’s ready."
                          : "Your history is saved on this computer and ready to explore.")}
                    </p>
                  </div>
                </div>
              )}
              {error && (
                <p className="import-error" role="alert">
                  {error}
                </p>
              )}
              <div className="import-engine">
                <span>Analysis</span>
                <strong>GPT-6 Luna · headless Codex</strong>
                <p>
                  Uses your Codex login. Readable user messages are sent to
                  OpenAI for topic analysis. Your export and results stay in
                  private local storage.
                </p>
              </div>
            </Modal.Body>
            <Modal.Footer>
              <Button slot="close" variant="ghost">
                {working ? "Keep working in the background" : "Close"}
              </Button>
              {job?.stage === "complete" ? (
                <Button
                  onPress={() => {
                    onImported(job.dataset_id, job.name);
                    setOpen(false);
                  }}
                >
                  Open my timeline
                  <ArrowRight size={14} />
                </Button>
              ) : (
                preview &&
                !working && (
                  <Button
                    isDisabled={
                      busy || !preview.selected || service !== "ready"
                    }
                    onPress={() => void analyze()}
                  >
                    {busy ? (
                      <LoaderCircle className="import-spinner" size={14} />
                    ) : (
                      <ArrowRight size={14} />
                    )}
                    {job?.stage === "failed"
                      ? "Retry analysis"
                      : "Analyze my history"}
                  </Button>
                )
              )}
            </Modal.Footer>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </>
  );
}
