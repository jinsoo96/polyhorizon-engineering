import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const WIRE_API = "polyhorizon.wire/v0.1";
const exampleRoot = fileURLToPath(new URL("../forge-mutation/", import.meta.url));

async function load(name) {
  return JSON.parse(await readFile(join(exampleRoot, name), "utf8"));
}

class SidecarClient {
  constructor(executable) {
    this.stderr = "";
    this.process = spawn(executable, ["-m", "polyhorizon.cli", "serve"], {
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.process.stderr.setEncoding("utf8");
    this.process.stderr.on("data", (chunk) => {
      this.stderr += chunk;
    });
    this.lines = createInterface({ input: this.process.stdout, crlfDelay: Infinity })[
      Symbol.asyncIterator
    ]();
  }

  async request(requestId, command, payload) {
    const envelope = {
      api_version: WIRE_API,
      request_id: requestId,
      command,
      payload,
    };
    this.process.stdin.write(`${JSON.stringify(envelope)}\n`);
    const next = await this.lines.next();
    if (next.done) {
      throw new Error(`sidecar ended before responding: ${this.stderr.trim()}`);
    }
    const response = JSON.parse(next.value);
    if (response.request_id !== requestId) {
      throw new Error(`response binding mismatch: expected ${requestId}`);
    }
    if (!response.ok) {
      throw new Error(`${response.error.code}: ${response.error.message}`);
    }
    return response.payload;
  }

  async close() {
    this.process.stdin.end();
    const code = await new Promise((resolve, reject) => {
      this.process.once("error", reject);
      this.process.once("exit", resolve);
    });
    if (code !== 0) {
      throw new Error(`sidecar exited with ${code}: ${this.stderr.trim()}`);
    }
  }
}

async function main() {
  const executable = process.argv[2] ?? process.env.PYTHON ?? "python";
  const [charter, candidate, proposal] = await Promise.all([
    load("charter.v1.json"),
    load("charter.v1.1-candidate.json"),
    load("proposal.json"),
  ]);
  const client = new SidecarClient(executable);
  try {
    const capabilities = await client.request("node-capabilities", "capabilities", {});
    const opened = await client.request("node-open", "open", {
      charter,
      candidate,
      proposal,
    });
    const sessionId = opened.state.id;
    const inspected = await client.request("node-inspect", "inspect", {
      session_id: sessionId,
    });
    const aborted = await client.request("node-abort", "abort", {
      session_id: sessionId,
      expected_sequence: opened.state.sequence,
    });
    console.log(
      JSON.stringify({
        wire_api: capabilities.wire_api,
        commands: capabilities.commands,
        open_status: opened.state.status,
        effect_count: opened.effects.length,
        inspect_digest: inspected.state_digest,
        abort_status: aborted.state.status,
      }),
    );
  } finally {
    await client.close();
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
