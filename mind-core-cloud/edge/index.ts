
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

type Json = Record<string, any>;
type Goal = {
  id: number;
  goal_key: string;
  kind: string;
  target: Json;
  rationale: string | null;
  priority: number;
  status: string;
  recurrence_minutes: number | null;
  not_before: string;
  created_from_cycle: number | null;
  last_run_at: string | null;
  run_count: number;
  last_result: Json | null;
  last_error: string | null;
};

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
  last_observation?: Json | null;
  current_goal?: Json | null;
  frontier_size?: number;
};

const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const db = createClient(supabaseUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const GH_HEADERS = {
  "Accept": "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
};

async function fetchText(url: string, headers: Record<string, string> = {}) {
  const res = await fetch(url, {
    headers: {
      "User-Agent": "MindCoreResearcher/0.2 (+read-only research)",
      ...headers,
    },
    redirect: "follow",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return await res.text();
}

function nowIso() {
  return new Date().toISOString();
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

function stripHtml(s: string) {
  return s
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function pageTitle(html: string): string | null {
  const m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return m ? stripHtml(m[1]).slice(0, 300) : null;
}

async function recordEvidence(
  cycleId: number,
  sourceUrl: string,
  sourceKind: string,
  sourceTitle: string | null,
  observed: Json,
) {
  const { error } = await db.from("mind_core_evidence").insert({
    cycle_id: cycleId,
    source_url: sourceUrl,
    source_kind: sourceKind,
    source_title: sourceTitle,
    observed,
  });
  if (error) throw error;
}

async function spawnGoal(args: {
  goal_key: string;
  kind: string;
  target?: Json;
  rationale: string;
  priority: number;
  created_from_cycle: number;
  recurrence_minutes?: number | null;
}) {
  const row = {
    goal_key: args.goal_key,
    kind: args.kind,
    target: args.target ?? {},
    rationale: args.rationale,
    priority: Math.max(0, Math.min(1, args.priority)),
    status: "pending",
    recurrence_minutes: args.recurrence_minutes ?? null,
    not_before: nowIso(),
    created_from_cycle: args.created_from_cycle,
    updated_at: nowIso(),
  };

  const { error } = await db
    .from("mind_core_goals")
    .upsert(row, { onConflict: "goal_key", ignoreDuplicates: true });
  if (error) throw error;
}

function isAllowedReference(urlString: string) {
  try {
    const u = new URL(urlString);
    return [
      "www.python.org",
      "python.org",
      "docs.python.org",
      "peps.python.org",
      "discuss.python.org",
    ].includes(u.hostname);
  } catch {
    return false;
  }
}

async function generateGoalsFromIssue(
  cycleId: number,
  repo: string,
  issue: Json,
) {
  const body = String(issue.body ?? "");
  const related = new Map<string, { kind: string; target: Json; priority: number }>();

  for (const m of body.matchAll(/https:\/\/github\.com\/python\/cpython\/(issues|pull)\/(\d+)/g)) {
    const kind = m[1] === "pull" ? "inspect_github_pull" : "inspect_github_issue";
    const n = Number(m[2]);
    if (Number.isFinite(n) && n !== issue.number) {
      related.set(`${kind}:${n}`, {
        kind,
        target: { repo, number: n },
        priority: kind === "inspect_github_pull" ? 0.90 : 0.82,
      });
    }
  }

  for (const m of body.matchAll(/https:\/\/(?:www\.)?(?:python\.org|docs\.python\.org|peps\.python\.org|discuss\.python\.org)\/[^\s)\]>"']+/g)) {
    const url = m[0].replace(/[.,;:]+$/, "");
    if (isAllowedReference(url)) {
      related.set(`web:${url}`, {
        kind: "inspect_web_reference",
        target: { url },
        priority: url.includes("peps.python.org") ? 0.86 : 0.72,
      });
    }
  }

  for (const [key, item] of related) {
    await spawnGoal({
      goal_key: key,
      kind: item.kind,
      target: item.target,
      rationale: `Reference discovered inside CPython issue #${issue.number}; unresolved external dependency.`,
      priority: item.priority,
      created_from_cycle: cycleId,
    });
  }

  if (issue.state === "open" && Array.isArray(issue.labels) &&
      issue.labels.some((l: any) => (typeof l === "string" ? l : l?.name) === "release-blocker")) {
    await spawnGoal({
      goal_key: `recheck-issue:${repo}#${issue.number}`,
      kind: "inspect_github_issue",
      target: { repo, number: issue.number },
      rationale: "Open release-blocker remains time-sensitive; schedule a later state recheck.",
      priority: 0.68,
      created_from_cycle: cycleId,
      recurrence_minutes: 180,
    });
  }
}

async function executeGoal(goal: Goal, cycleId: number) {
  if (goal.kind === "verify_stable_release") {
    const url = "https://www.python.org/downloads/";
    const html = await fetchText(url);
    const observed = {
      current_stable: parseStableVersion(html),
      checked_at: nowIso(),
      content_length: html.length,
    };
    await recordEvidence(cycleId, url, "official_web", "Python Downloads", observed);
    return observed;
  }

  if (goal.kind === "scan_release_blockers") {
    const repo = String(goal.target?.repo ?? "python/cpython");
    const q = encodeURIComponent(`repo:${repo} is:issue is:open label:release-blocker`);
    const url = `https://api.github.com/search/issues?q=${q}&sort=updated&order=desc&per_page=10`;
    const text = await fetchText(url, GH_HEADERS);
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
      repo,
      total_count: json.total_count ?? null,
      issues,
      checked_at: nowIso(),
    };
    await recordEvidence(cycleId, url, "github_api", "Open CPython release-blocker issues", observed);

    for (const issue of issues) {
      await spawnGoal({
        goal_key: `github-issue:${repo}#${issue.number}`,
        kind: "inspect_github_issue",
        target: { repo, number: issue.number },
        rationale: "New unresolved release-blocker discovered by live scan.",
        priority: 0.95,
        created_from_cycle: cycleId,
      });
    }
    return observed;
  }

  if (goal.kind === "inspect_github_issue") {
    const repo = String(goal.target?.repo ?? "python/cpython");
    const number = Number(goal.target?.number);
    if (!Number.isFinite(number)) throw new Error("invalid issue number");
    const url = `https://api.github.com/repos/${repo}/issues/${number}`;
    const text = await fetchText(url, GH_HEADERS);
    const issue = JSON.parse(text);
    const labels = Array.isArray(issue.labels)
      ? issue.labels.map((l: any) => typeof l === "string" ? l : l?.name).filter(Boolean)
      : [];
    const observed = {
      repo,
      number: issue.number,
      title: issue.title,
      state: issue.state,
      state_reason: issue.state_reason ?? null,
      labels,
      milestone: issue.milestone?.title ?? null,
      assignees: Array.isArray(issue.assignees) ? issue.assignees.map((a: any) => a.login) : [],
      comments: issue.comments ?? 0,
      created_at: issue.created_at,
      updated_at: issue.updated_at,
      closed_at: issue.closed_at,
      html_url: issue.html_url,
      body_excerpt: String(issue.body ?? "").slice(0, 6000),
      checked_at: nowIso(),
    };
    await recordEvidence(cycleId, url, "github_api", `CPython issue #${number}`, observed);
    await generateGoalsFromIssue(cycleId, repo, { ...issue, labels });
    return observed;
  }

  if (goal.kind === "inspect_github_pull") {
    const repo = String(goal.target?.repo ?? "python/cpython");
    const number = Number(goal.target?.number);
    if (!Number.isFinite(number)) throw new Error("invalid pull number");
    const url = `https://api.github.com/repos/${repo}/pulls/${number}`;
    const text = await fetchText(url, GH_HEADERS);
    const pr = JSON.parse(text);
    const observed = {
      repo,
      number: pr.number,
      title: pr.title,
      state: pr.state,
      draft: pr.draft ?? false,
      merged: pr.merged ?? false,
      mergeable_state: pr.mergeable_state ?? null,
      html_url: pr.html_url,
      created_at: pr.created_at,
      updated_at: pr.updated_at,
      merged_at: pr.merged_at,
      body_excerpt: String(pr.body ?? "").slice(0, 6000),
      checked_at: nowIso(),
    };
    await recordEvidence(cycleId, url, "github_api", `CPython pull #${number}`, observed);
    return observed;
  }

  if (goal.kind === "inspect_web_reference") {
    const url = String(goal.target?.url ?? "");
    if (!isAllowedReference(url)) throw new Error("reference host not allowed");
    const html = await fetchText(url);
    const observed = {
      url,
      title: pageTitle(html),
      text_excerpt: stripHtml(html).slice(0, 8000),
      content_length: html.length,
      checked_at: nowIso(),
    };
    await recordEvidence(cycleId, url, "public_web_reference", observed.title, observed);
    return observed;
  }

  throw new Error(`unsupported goal kind: ${goal.kind}`);
}

async function chooseGoal(): Promise<Goal | null> {
  const { data, error } = await db
    .from("mind_core_goals")
    .select("*")
    .in("status", ["pending", "completed"])
    .order("priority", { ascending: false })
    .limit(200);
  if (error) throw error;

  const now = Date.now();
  const eligible = (data ?? []).filter((g: Goal) => {
    const nb = Date.parse(g.not_before);
    if (Number.isFinite(nb) && nb > now) return false;
    if (g.status === "pending") return true;
    if (g.status === "completed" && g.recurrence_minutes && g.last_run_at) {
      return Date.parse(g.last_run_at) + g.recurrence_minutes * 60_000 <= now;
    }
    return false;
  });

  if (!eligible.length) return null;
  eligible.sort((a: Goal, b: Goal) => {
    if (b.priority !== a.priority) return b.priority - a.priority;
    return Date.parse(a.created_at ?? a.not_before) - Date.parse(b.created_at ?? b.not_before);
  });
  return eligible[0] as Goal;
}

async function frontierSize() {
  const { data, error } = await db
    .from("mind_core_goals")
    .select("id,status,recurrence_minutes,last_run_at,not_before")
    .in("status", ["pending", "completed"])
    .limit(500);
  if (error) return null;
  const now = Date.now();
  return (data ?? []).filter((g: any) => {
    if (Date.parse(g.not_before) > now) return false;
    if (g.status === "pending") return true;
    return g.status === "completed" && g.recurrence_minutes && g.last_run_at &&
      Date.parse(g.last_run_at) + g.recurrence_minutes * 60_000 <= now;
  }).length;
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
  let selectedGoal: Goal | null = null;

  try {
    selectedGoal = await chooseGoal();
    if (!selectedGoal) {
      return Response.json({
        ok: true,
        idle: true,
        reason: "no eligible self-generated goals",
      });
    }

    const { error: markError } = await db
      .from("mind_core_goals")
      .update({ status: "running", updated_at: nowIso() })
      .eq("id", selectedGoal.id);
    if (markError) throw markError;

    const { data: cycle, error: cycleError } = await db
      .from("mind_core_cycles")
      .insert({
        status: "running",
        trigger_source: body?.trigger ?? "http",
        focus: selectedGoal.kind,
      })
      .select("id")
      .single();
    if (cycleError) throw cycleError;
    cycleId = cycle.id;

    const result = await executeGoal(selectedGoal, cycleId);

    const nextNotBefore = selectedGoal.recurrence_minutes
      ? new Date(Date.now() + selectedGoal.recurrence_minutes * 60_000).toISOString()
      : selectedGoal.not_before;

    const { error: finishGoalError } = await db
      .from("mind_core_goals")
      .update({
        status: "completed",
        last_run_at: nowIso(),
        run_count: (selectedGoal.run_count ?? 0) + 1,
        last_result: result,
        last_error: null,
        not_before: nextNotBefore,
        updated_at: nowIso(),
      })
      .eq("id", selectedGoal.id);
    if (finishGoalError) throw finishGoalError;

    const { data: stateRow } = await db
      .from("mind_core_state")
      .select("state")
      .eq("id", "main")
      .single();

    const state = (stateRow?.state ?? {}) as CoreState;
    const fSize = await frontierSize();
    const nextState: CoreState = {
      ...state,
      version: "0.2-cloud-goal-genesis",
      last_cycle_at: nowIso(),
      last_focus: selectedGoal.kind,
      last_observation: result,
      current_goal: {
        id: selectedGoal.id,
        key: selectedGoal.goal_key,
        kind: selectedGoal.kind,
        rationale: selectedGoal.rationale,
        priority: selectedGoal.priority,
      },
      frontier_size: fSize ?? undefined,
    };
    if (selectedGoal.kind === "verify_stable_release" && result.current_stable) {
      nextState.last_stable = result.current_stable;
    }

    const { error: stateError } = await db
      .from("mind_core_state")
      .update({ state: nextState, updated_at: nowIso() })
      .eq("id", "main");
    if (stateError) throw stateError;

    const summary = {
      goal: {
        id: selectedGoal.id,
        key: selectedGoal.goal_key,
        kind: selectedGoal.kind,
        rationale: selectedGoal.rationale,
        priority: selectedGoal.priority,
      },
      observed: result,
      frontier_size_after: fSize,
    };

    const { error: cycleFinishError } = await db
      .from("mind_core_cycles")
      .update({
        finished_at: nowIso(),
        status: "completed",
        summary,
      })
      .eq("id", cycleId);
    if (cycleFinishError) throw cycleFinishError;

    return Response.json({
      ok: true,
      cycle_id: cycleId,
      selected_goal: summary.goal,
      result,
      frontier_size_after: fSize,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (cycleId !== null) {
      await db.from("mind_core_cycles").update({
        finished_at: nowIso(),
        status: "failed",
        error: message,
      }).eq("id", cycleId);
    }
    if (selectedGoal) {
      const retry = (selectedGoal.run_count ?? 0) < 2;
      await db.from("mind_core_goals").update({
        status: retry ? "pending" : "failed",
        last_error: message,
        not_before: new Date(Date.now() + 60 * 60_000).toISOString(),
        updated_at: nowIso(),
      }).eq("id", selectedGoal.id);
    }
    console.error("mind-core cycle failed", message);
    return Response.json({ ok: false, error: message }, { status: 500 });
  }
});
