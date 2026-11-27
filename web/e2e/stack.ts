// The browser tests' own backend: a throwaway Postgres in Docker and the real FastAPI server,
// on ports of their own so they never touch the dev database or a running dev server.
// Playwright runs this once before the tests; the function it returns runs once after them.
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import { randomBytes } from "node:crypto";
import path from "node:path";

import { E2E } from "./ports";

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const PYTHON = process.env.PYTHON || "python";
// The same image as backend/docker-compose.yml.
const POSTGRES_IMAGE = "postgres:17@sha256:b8faeff7712663c2773a190181e1246e37e364b887611c04658c28b44e2408fe";
const CONTAINER = "artemis-web-e2e-db";

function docker(args: string[], quiet = false): string {
  return execFileSync("docker", args, { encoding: "utf8", stdio: ["ignore", "pipe", quiet ? "ignore" : "inherit"] });
}

function removeContainer(): void {
  try {
    docker(["rm", "-f", CONTAINER], true);
  } catch {
    // not there: nothing to remove
  }
}

async function waitFor(what: string, ready: () => Promise<boolean> | boolean, seconds: number): Promise<void> {
  const until = Date.now() + seconds * 1000;
  while (Date.now() < until) {
    if (await ready()) return;
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`${what} was not ready after ${seconds}s`);
}

export default async function globalSetup(): Promise<() => Promise<void>> {
  // A fresh password each run; the database lives only as long as the test run.
  const password = randomBytes(18).toString("hex");
  const databaseUrl = `postgresql+psycopg://artemis:${password}@127.0.0.1:${E2E.dbPort}/artemis`;

  removeContainer(); // a container left behind by an interrupted run
  let backend: ChildProcess | undefined;
  const stop = async () => {
    backend?.kill();
    removeContainer();
  };
  try {
    backend = await start(password, databaseUrl);
  } catch (err) {
    await stop(); // nothing is left running when the setup fails
    throw err;
  }
  return stop;
}

async function start(password: string, databaseUrl: string): Promise<ChildProcess> {
  docker([
    "run", "-d", "--rm", "--name", CONTAINER,
    "-e", "POSTGRES_USER=artemis", "-e", "POSTGRES_DB=artemis", "-e", `POSTGRES_PASSWORD=${password}`,
    "-p", `127.0.0.1:${E2E.dbPort}:5432`,
    POSTGRES_IMAGE,
  ], true);
  await waitFor("Postgres", () => {
    try {
      docker(["exec", CONTAINER, "pg_isready", "-U", "artemis", "-d", "artemis", "-h", "127.0.0.1"], true);
      return true;
    } catch {
      return false;
    }
  }, 60);

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    ARTEMIS_DATABASE_URL: databaseUrl,
    ARTEMIS_API_HOST: "127.0.0.1",
    ARTEMIS_API_PORT: String(E2E.apiPort),
    ARTEMIS_API_ORIGINS: E2E.webOrigin,
    // No model server: these tests never pay for an AI review. A request with use_ai on gets a
    // 503 instead (backend/main.py). Set here, so .env can't fill them in.
    LLM_BASE_URL: "",
    LLM_API_KEY: "",
    LLM_MODEL: "",
    OPENROUTER_API_KEY: "",
    // The search model must already be on disk; never download weights during a test.
    HF_HUB_OFFLINE: "1",
    // The suite runs more checks a minute than the clinic's limit of 6; the limit itself is the
    // backend's to test (tests/test_check_limit.py), and the 429 screen is checked with a stub.
    ARTEMIS_VISIT_CHECKS_PER_MINUTE: "1000",
    // The guideline index (Chroma) would otherwise try to send usage data.
    ANONYMIZED_TELEMETRY: "False",
    PYTHONUNBUFFERED: "1",
  };
  execFileSync(PYTHON, ["-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], {
    cwd: REPO_ROOT, env, stdio: ["ignore", "ignore", "inherit"],
  });
  // The made-up patients and the 26 Nov demo day (backend/seed/patients.sql); without them the
  // patient list is empty and the board answers 404.
  execFileSync(PYTHON, ["scripts/patients_backup.py", "load"], {
    cwd: REPO_ROOT, env, stdio: ["ignore", "ignore", "inherit"],
  });

  const backend = spawn(PYTHON, ["-m", "backend"], { cwd: REPO_ROOT, env, stdio: ["ignore", "inherit", "inherit"] });
  let exited = false;
  backend.on("exit", () => (exited = true));
  try {
    // Starting imports the analysis code, which can be slow while the laptop is busy.
    await waitFor("The backend", async () => {
      if (exited) throw new Error("The backend stopped while starting (see its log above)");
      try {
        return (await fetch(`${E2E.apiUrl}/api/health`)).ok;
      } catch {
        return false;
      }
    }, 180);
  } catch (err) {
    backend.kill();
    throw err;
  }
  return backend;
}
