#!/usr/bin/env node

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const installRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const appRoot = join(installRoot, "app");
const nativeRoot = join(installRoot, "linux-native");
const legacyDaemon = join(installRoot, "resources/resources/daemon/daemon.js");
const modernRuntimeV1Path = join(appRoot, "node_modules/@mavis/local-runtime/dist/index.js");
const modernRuntimeV2Path = join(appRoot, "node_modules/@mavis/local-runtime-v2/dist/index.js");
const appPackage = JSON.parse(await readFile(join(appRoot, "package.json"), "utf8"));
const appVersion = String(appPackage.version ?? "unknown");

if (process.argv.includes("--version")) {
  process.stdout.write(`MiniMax Code ${appVersion}\n`);
  process.exit(0);
}

const baseURL = process.env.MINIMAX_CODE_BASE_URL;
if (!baseURL) {
  throw new Error("MINIMAX_CODE_BASE_URL is required; launch MiniMax Code through claude-tap");
}
const modernRuntimePath = (await fileExists(modernRuntimeV2Path))
  ? modernRuntimeV2Path
  : modernRuntimeV1Path;
const hasModernRuntime = await fileExists(modernRuntimePath);
const usesModernRuntimeV2 = modernRuntimePath === modernRuntimeV2Path;
const providerBaseURL = hasModernRuntime ? baseURL : `${baseURL.replace(/\/$/, "")}/v1`;

const dataDir = resolve(
  process.env.MINIMAX_CODE_DATA_DIR ?? join(process.env.HOME ?? process.cwd(), ".minimax-code"),
);
await mkdir(dataDir, { recursive: true });
process.env.MINIMAX_DATA_DIR = dataDir;
process.env.MAVIS_DATA_DIR = dataDir;
process.env.__MAVIS_RUNTIME_MANAGED = "0";
process.env.MAVIS_REGION = "en";
process.env.MAVIS_BUILD_ENV = "prod";
process.env.MAVIS_ELECTRON_LOCALE = "en";
process.env.MAVIS_SQLITE3_MODULE_PATH = nativeRoot;
process.env.MAVIS_BUILTIN_AGENTS_DIR = join(
  appRoot,
  usesModernRuntimeV2 ? "node_modules/@mavis/local-runtime-v2/assets/agents" : "node_modules/@mavis/local-runtime/assets/agents",
);
process.env.MAVIS_BUILTIN_SKILLS_DIR = join(
  appRoot,
  usesModernRuntimeV2 ? "node_modules/@mavis/local-runtime-v2/assets/skills" : "node_modules/@mavis/local-runtime/assets/skills",
);
process.env.LOG_LEVEL ??= "fatal";

const captureConfig = {
  provider: {
    phistory: {
      name: "Phistory capture",
      enabled: true,
      npm: "@ai-sdk/anthropic",
      api: "anthropic-messages",
      options: { apiKey: "sk-phistory-capture", baseURL: providerBaseURL },
      models: {
        "minimax-code-capture": {
          name: "MiniMax Code capture",
          limit: { context: 200000, output: 16384 },
          modalities: { input: ["text", "image"], output: ["text"] },
        },
      },
    },
  },
  defaultModel: "phistory/minimax-code-capture",
  permissionMode: "bypassPermissions",
};
await writeFile(join(dataDir, "config.yaml"), `${JSON.stringify(captureConfig, null, 2)}\n`, "utf8");

async function captureWithModernRuntime() {
  const configUrl = pathToFileURL(join(appRoot, "node_modules/@mavis/config/dist/index.js")).href;
  const runtimeUrl = pathToFileURL(modernRuntimePath).href;
  const [{ getConfig }, { createLocalRuntimeHost }] = await Promise.all([
    import(configUrl),
    import(runtimeUrl),
  ]);
  const config = getConfig();
  const host = await createLocalRuntimeHost({
    dataDir,
    runtimeOwnerKind: "cli",
    runtimeMode: "clean",
    appVersion,
    configGetter: () => config,
    defaultWorkspaceDir: process.cwd(),
    capabilities: { cliEmbedded: true },
  });

  await host.ready;
  await host.apiHost.ensureBuiltinAgents();
  await sendCaptureRequest(
    (request) => host.apiHost.handleRequest(request),
    "http://local-runtime",
    usesModernRuntimeV2,
  );
}

async function captureWithLegacyDaemon() {
  const port = await reservePort();
  const childEnv = { ...process.env };
  delete childEnv.MAVIS_DATA_DIR;
  childEnv.MAVIS_SQLITE3_MODULE_PATH = nativeRoot;
  childEnv.OPENCODE_BIN = join(nativeRoot, "node_modules/.bin/opencode");
  childEnv.LOG_LEVEL = childEnv.LOG_LEVEL ?? "fatal";
  const daemon = spawn(
    process.execPath,
    [
      legacyDaemon,
      "--port",
      String(port),
      "--data-dir",
      dataDir,
      "--owner",
      "cli",
      "--skip-pid-port",
      "--disable-git-auto-config",
    ],
    { env: childEnv, stdio: ["ignore", "ignore", "pipe"] },
  );
  let stderr = "";
  daemon.stderr.setEncoding("utf8");
  daemon.stderr.on("data", (chunk) => {
    stderr = `${stderr}${chunk}`.slice(-8000);
  });
  try {
    const origin = `http://127.0.0.1:${port}`;
    await waitForHealth(origin, daemon, () => stderr);
    await sendCaptureRequest((request) => fetch(request), origin, false);
  } finally {
    const exited = new Promise((finish) => {
      if (daemon.exitCode !== null) finish();
      else daemon.once("exit", finish);
    });
    daemon.kill("SIGTERM");
    await Promise.race([
      exited,
      new Promise((finish) => setTimeout(finish, 30_000)),
    ]);
    if (daemon.exitCode === null) {
      daemon.kill("SIGKILL");
      await Promise.race([exited, new Promise((finish) => setTimeout(finish, 3000))]);
    }
  }
}

async function sendCaptureRequest(handleRequest, origin, desktopService) {
  const rootPath = desktopService
    ? "/minimax-desktop/api/v1/agent/mavis/session/root"
    : "/mavis/api/agent/mavis/session/root";
  const rootResponse = await handleRequest(
    new Request(`${origin}${rootPath}`),
  );
  if (!rootResponse.ok) {
    throw new Error(
      `MiniMax Code root session failed: ${rootResponse.status} ${await rootResponse.text()}`,
    );
  }
  const root = await rootResponse.json();
  const sessionId = root?.session?.id ?? root?.session?.sessionId ?? root?.session?.session_id;
  if (!sessionId) {
    throw new Error(`MiniMax Code root session response has no id: ${JSON.stringify(root)}`);
  }

  const messagePath = desktopService
    ? `/minimax-desktop/api/v1/session/${sessionId}/message`
    : `/mavis/api/session/${sessionId}/message`;
  const turnResponse = await handleRequest(
    new Request(`${origin}${messagePath}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ content: "Reply with one short sentence." }),
    }),
  );
  const turnBody = await turnResponse.text();
  if (!turnResponse.ok) {
    throw new Error(`MiniMax Code turn failed: ${turnResponse.status} ${turnBody}`);
  }
}

async function reservePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close(() => reject(new Error("could not reserve a MiniMax Code daemon port")));
        return;
      }
      server.close(() => resolvePort(address.port));
    });
  });
}

async function fileExists(path) {
  try {
    await readFile(path);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function waitForHealth(origin, daemon, stderr) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (daemon.exitCode !== null) {
      throw new Error(`MiniMax Code daemon exited with ${daemon.exitCode}: ${stderr()}`);
    }
    try {
      const response = await fetch(`${origin}/mavis/health`);
      if (response.ok) return;
    } catch {}
    await new Promise((finish) => setTimeout(finish, 200));
  }
  throw new Error(`MiniMax Code daemon did not become ready: ${stderr()}`);
}

if (hasModernRuntime) {
  await captureWithModernRuntime();
} else {
  await captureWithLegacyDaemon();
}
process.exit(0);
