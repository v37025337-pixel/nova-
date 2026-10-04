import { Sandbox } from "@vercel/sandbox";
import { authorized } from "../../../lib/auth";
import { safeHttpsUrl } from "../../../lib/safe-url";
import { UC_BIN } from "../../../lib/uc";

export const runtime = "nodejs";
export const maxDuration = 120;

type Body = {
  snapshotId?: string;
  url?: string;
  mode?: "inspect";
};

export async function POST(request: Request) {
  if (!authorized(request)) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  let body: Body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ ok: false, error: "invalid JSON" }, { status: 400 });
  }

  const snapshotId = String(body.snapshotId || "");
  if (!snapshotId.startsWith("snap_")) {
    return Response.json({ ok: false, error: "valid snapshotId required" }, { status: 400 });
  }

  let target: URL;
  try {
    target = safeHttpsUrl(String(body.url || ""));
  } catch (error) {
    return Response.json(
      { ok: false, error: error instanceof Error ? error.message : String(error) },
      { status: 400 }
    );
  }

  const sandbox = await Sandbox.create({
    source: { type: "snapshot", snapshotId },
    timeout: 120_000
  });

  try {
    const versionCmd = await sandbox.runCommand(UC_BIN, ["--version"]);
    const browserVersion = (await versionCmd.stdout()).trim();

    const args = [
      "--headless=new",
      "--no-sandbox",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      "--disable-background-networking",
      "--disable-component-update",
      "--disable-default-apps",
      "--disable-sync",
      "--metrics-recording-only",
      "--no-first-run",
      "--no-default-browser-check",
      "--no-pings",
      "--disable-search-engine-collection",
      "--force-punycode-hostnames",
      "--enable-features=MinimalReferrers,RemoveClientHints,ReducedSystemInfo,ClearDataOnExit",
      "--user-data-dir=/tmp/mindcore-profile",
      "--virtual-time-budget=10000",
      "--dump-dom",
      target.toString()
    ];

    const run = await sandbox.runCommand(UC_BIN, args);
    const html = await run.stdout();
    const stderr = await run.stderr();

    const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const title = titleMatch ? titleMatch[1].replace(/\s+/g, " ").trim() : null;

    return Response.json({
      ok: run.exitCode === 0,
      url: target.toString(),
      browserVersion,
      exitCode: run.exitCode,
      title,
      domBytes: html.length,
      dom: html.slice(0, 200000),
      stderrTail: stderr.slice(-4000),
      profile: "ephemeral",
      credentialsImported: false
    });
  } finally {
    await sandbox.stop();
  }
}
