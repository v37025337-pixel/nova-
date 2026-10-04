import { Sandbox } from "@vercel/sandbox";
import { authorized } from "../../../lib/auth";
import { CHROMIUM_SYSTEM_DEPS, UC_BIN, UC_SHA256, UC_URL, UC_VERSION } from "../../../lib/uc";

export const runtime = "nodejs";
export const maxDuration = 300;

export async function POST(request: Request) {
  if (!authorized(request)) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const sandbox = await Sandbox.create({
    runtime: "node24",
    timeout: 300_000
  });

  let snapshotted = false;
  try {
    const arch = await sandbox.runCommand("uname", ["-m"]);
    const archText = (await arch.stdout()).trim();
    if (archText !== "x86_64") throw new Error("unsupported sandbox arch: " + archText);

    const installCmd =
      "sudo dnf clean all >/dev/null 2>&1 || true; " +
      "sudo dnf install -y --skip-broken " + CHROMIUM_SYSTEM_DEPS.join(" ") +
      " >/tmp/dnf.log 2>&1; sudo ldconfig";
    const install = await sandbox.runCommand("sh", ["-lc", installCmd]);
    if (install.exitCode !== 0) {
      throw new Error("system dependency installation failed: " + (await install.stderr()).slice(-4000));
    }

    const prep = await sandbox.runCommand("sh", [
      "-lc",
      "sudo mkdir -p /opt/mindcore-browser /opt/uc && sudo chown -R $(id -u):$(id -g) /opt/mindcore-browser /opt/uc"
    ]);
    if (prep.exitCode !== 0) throw new Error("runtime directory setup failed");

    const dl = await sandbox.runCommand("curl", ["-fL", "--retry", "3", "-o", "/tmp/uc.tar.xz", UC_URL]);
    if (dl.exitCode !== 0) throw new Error("Ungoogled Chromium download failed");

    const verify = await sandbox.runCommand("sh", [
      "-lc",
      "echo '" + UC_SHA256 + "  /tmp/uc.tar.xz' | sha256sum -c -"
    ]);
    if (verify.exitCode !== 0) throw new Error("Ungoogled Chromium SHA-256 mismatch");

    const extract = await sandbox.runCommand("tar", ["-xJf", "/tmp/uc.tar.xz", "-C", "/opt/uc"]);
    if (extract.exitCode !== 0) throw new Error("Ungoogled Chromium extraction failed");

    const linkCmd =
      "set -e; " +
      "B=\"$(find /opt/uc -type f \\( -name chrome -o -name chromium \\) -perm -u+x | head -n 1)\"; " +
      "test -n \"$B\"; " +
      "ln -sf \"$B\" " + UC_BIN + "; " +
      "chmod +x \"$B\"; " +
      UC_BIN + " --version";
    const link = await sandbox.runCommand("sh", ["-lc", linkCmd]);
    if (link.exitCode !== 0) {
      throw new Error("browser binary discovery failed: " + (await link.stderr()).slice(-4000));
    }

    const browserVersion = (await link.stdout()).trim().split("\n").at(-1) || "unknown";
    const snapshot = await sandbox.snapshot();
    snapshotted = true;

    return Response.json({
      ok: true,
      snapshotId: snapshot.snapshotId,
      sourceVersion: UC_VERSION,
      sourceUrl: UC_URL,
      sourceSha256: UC_SHA256,
      sandboxArch: archText,
      browserVersion,
      binary: UC_BIN,
      trust: {
        source: "ungoogled-software/ungoogled-chromium-portablelinux",
        releaseUploader: "github-actions[bot]",
        sha256Verified: true
      }
    });
  } catch (error) {
    return Response.json(
      { ok: false, error: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  } finally {
    if (!snapshotted) {
      try { await sandbox.stop(); } catch {}
    }
  }
}
