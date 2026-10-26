// Start the local services together; reuse an already-running Kura import API.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const python =
  process.env.KURA_PYTHON ||
  (existsSync(path.join(root, ".venv/bin/python"))
    ? path.join(root, ".venv/bin/python")
    : "python3");
const children = [];
let existingApi = false;
try {
  const response = await fetch("http://127.0.0.1:8014/api/status", {
    signal: AbortSignal.timeout(1500),
  });
  existingApi = response.ok && (await response.json()).engine === "codex";
} catch {
  /* Start the local service when it is not running. */
}
if (existingApi)
  console.log("Using the running Kura import service on http://127.0.0.1:8014");
else
  children.push(
    spawn(
      python,
      [
        "-m",
        "uvicorn",
        "kura.cli.server:api",
        "--host",
        "127.0.0.1",
        "--port",
        "8014",
      ],
      { cwd: root, stdio: "inherit" },
    ),
  );
children.push(
  spawn("npm", ["--prefix", "ui", "run", "dev", "--", "--host", "127.0.0.1"], {
    cwd: root,
    stdio: "inherit",
  }),
);
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill("SIGTERM");
  process.exitCode = code;
}
for (const child of children) {
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping) stop(code || 0);
  });
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
