
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

type CoreState = {
  version?: string;
  mode?: string;
  goal?: string;
  topic?: string;
  last_stable?: string | null;
  next_major?: string | null;
  unresolved?: string[];
  last_cycle_at?: string | null;
  last_focus?: string | null;
  last_observation?: Record<string, unknown> | null;
};

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(supabaseUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

async function fetchText(url: string, headers: Record<string, string> = {}) {
  const res = await fetch(url, {
    headers: {
      "User-Agent": "MindCoreResearcher/0.1 (+read-only research)",
      ...headers,
    },
    redirect: "follow",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return await res.text();
}

function parseStableVersion(html: string): string | null {
  const patterns = [
    /Download Python\s+(\d+\.\d+\.\d+)/i,
    /Latest Python 3 Release\s*-?\s*Python\s+(\d+\.\d+\.\d+)/i,
  ];
  for (const p of patterns) {
    const m = html.match(p);
    if (m) return m[1];
  }
  return null;
}

async function checkStable(cycleId: number) {
  const url = "https://www.python.org/downloads/";
  const html = await fetchText(url);
  const stable = parseStableVersion(html);
  const observed = {
    current_stable: stable,
    checked_at: new Date().toISOString(),
    content_length: html.length,
  };

  const { error } = await db.from("mind_core_evidence").insert({
    cycle_id: cycleId,
    source_url: url,
    source_kind: "official_web",
    source_title: "Python Downloads",
    observed,
  });
  if (error) throw error;

  return { focus: "stable_release", observed };
}

async function checkReleaseBlockers(cycleId: number) {
  const q = encodeURIComponent("repo:python/cpython is:issue is:open label:release-blocker");
  const url = `https://api.github.com/search/issues?q=${q}&sort=updated&order=desc&per_page=10`;
  const text = await fetchText(url, {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  });
  const json = JSON.parse(text);
  const issues = Array.isArray(json.items)
    ? json.items.map((x: any) => ({
        number: x.number,
        title: x.title,
        html_url: x.html_url,
        updated_at: x.updated_at,
        labels: Array.isArray(x.labels)
          ? x.labels.map((l: any) => typeof l === "string" ? l : l?.name).filter(Boolean)
          : [],
      }))
    : [];

  const observed = {
    total_count: json.total_count ?? null,
    issues,
    checked_at: new Date().toISOString(),
  };

  const { error } = await db.from("mind_core_evidence").insert({
    cycle_id: cycleId,
    source_url: url,
    source_kind: "github_api",
    source_title: "Open CPython release-blocker issues",
    observed,
  });
  if (error) throw error;

  return { focus: "release_blockers", observed };
}

function chooseFocus(state: CoreState): "stable_release" | "release_blockers" {
  if (!state.last_focus) return "stable_release";
  return state.last_focus === "stable_release"
    ? "release_blockers"
    : "stable_release";
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") {
    return Response.json({
      ok: false,
      error: "NOESIS_REMOVED",
      replacement: "UnifiedKernel",
      removed_at: "2026-10-01",
      mind_core_route: "POST JSON {mode: 'mind-core'}",
    }, { status: 410 });
  }

  let body: any = {};
  try { body = await req.json(); } catch { body = {}; }

  if (body?.mode !== "mind-core") {
    return Response.json({
      ok: false,
      error: "NOESIS_REMOVED",
      replacement: "UnifiedKernel",
      removed_at: "2026-10-01",
    }, { status: 410 });
  }

  let cycleId: number | null = null;
  try {
    const { data: row, error: stateError } = await db
      .from("mind_core_state")
      .select("state")
      .eq("id", "main")
      .single();
    if (stateError) throw stateError;

    const state = (row?.state ?? {}) as CoreState;
    const focus = chooseFocus(state);

    const { data: cycle, error: cycleError } = await db
      .from("mind_core_cycles")
      .insert({
        status: "running",
        trigger_source: body?.trigger ?? "http",
        focus,
      })
      .select("id")
      .single();
    if (cycleError) throw cycleError;
    cycleId = cycle.id;

    const result = focus === "stable_release"
      ? await checkStable(cycleId)
      : await checkReleaseBlockers(cycleId);

    const nextState: CoreState = {
      ...state,
      last_cycle_at: new Date().toISOString(),
      last_focus: focus,
      last_observation: result.observed,
    };

    if (focus === "stable_release") {
      const v = (result.observed as any).current_stable;
      if (v) nextState.last_stable = v;
    }

    const { error: updateStateError } = await db
      .from("mind_core_state")
      .update({
        state: nextState,
        updated_at: new Date().toISOString(),
      })
      .eq("id", "main");
    if (updateStateError) throw updateStateError;

    const { error: finishError } = await db
      .from("mind_core_cycles")
      .update({
        finished_at: new Date().toISOString(),
        status: "completed",
        summary: result,
      })
      .eq("id", cycleId);
    if (finishError) throw finishError;

    return Response.json({
      ok: true,
      cycle_id: cycleId,
      focus,
      result: result.observed,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (cycleId !== null) {
      await db.from("mind_core_cycles").update({
        finished_at: new Date().toISOString(),
        status: "failed",
        error: message,
      }).eq("id", cycleId);
    }
    console.error("mind-core cycle failed", message);
    return Response.json({ ok: false, error: message }, { status: 500 });
  }
});
