
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

type Json = Record<string, any>;
type Goal = {
  id: number; goal_key: string; kind: string; target: Json;
  rationale: string | null; priority: number; status: string;
  recurrence_minutes: number | null; not_before: string;
  created_from_cycle: number | null; last_run_at: string | null;
  run_count: number; last_result: Json | null; last_error: string | null;
};
type CoreState = {
  version?: string; mode?: string; goal?: string; topic?: string;
  last_stable?: string | null; next_major?: string | null;
  unresolved?: string[]; last_cycle_at?: string | null;
  last_focus?: string | null; last_observation?: Json | null;
  current_goal?: Json | null; frontier_size?: number;
};

const db = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false, autoRefreshToken: false } },
);

const GH_HEADERS = {
  "Accept": "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
};
const INTERNET_MECHANISM = "M0001:real-internet-read";
const CURIOSITY_MECHANISM = "M0002:curiosity-pressure";

function nowIso() { return new Date().toISOString(); }

function isPrivateIPv4(host: string) {
  const p = host.split(".").map(Number);
  if (p.length !== 4 || p.some(x => !Number.isInteger(x) || x < 0 || x > 255)) return false;
  return p[0] === 10 ||
    p[0] === 127 ||
    (p[0] === 169 && p[1] === 254) ||
    (p[0] === 172 && p[1] >= 16 && p[1] <= 31) ||
    (p[0] === 192 && p[1] === 168) ||
    p[0] === 0;
}

function assertSafePublicHttps(raw: string) {
  const u = new URL(raw);
  if (u.protocol !== "https:") throw new Error("internet mechanism permits HTTPS only");
  if (u.username || u.password) throw new Error("credential-bearing URLs are not permitted");
  const h = u.hostname.toLowerCase();
  if (
    h === "localhost" ||
    h.endsWith(".localhost") ||
    h.endsWith(".local") ||
    h.endsWith(".internal") ||
    h === "metadata.google.internal" ||
    isPrivateIPv4(h) ||
    h.includes(":")
  ) throw new Error("local/private network target blocked");
  return u;
}

async function getInternetMechanism() {
  const { data, error } = await db
    .from("mind_core_mechanisms")
    .select("*")
    .eq("mechanism_key", INTERNET_MECHANISM)
    .single();
  if (error) throw error;
  if (!data || !["probation","admitted"].includes(data.status)) {
    throw new Error("real-internet-read mechanism is not active");
  }
  return data;
}

async function logMechanismEvent(
  mechanismId: number, cycleId: number | null, eventType: string,
  request: Json, result: Json, ok: boolean,
) {
  const { error } = await db.from("mind_core_mechanism_events").insert({
    mechanism_id: mechanismId,
    cycle_id: cycleId,
    event_type: eventType,
    request,
    result,
    ok,
  });
  if (error) console.error("mechanism event log failed", error.message);
}

async function internetGet(
  cycleId: number | null,
  rawUrl: string,
  purpose: string,
  headers: Record<string,string> = {},
) {
  const mechanism = await getInternetMechanism();
  let current = assertSafePublicHttps(rawUrl);
  let hops = 0;

  try {
    while (hops <= 5) {
      const res = await fetch(current.toString(), {
        headers: {
          "User-Agent": "MindCoreResearcher/0.3 (+read-only research)",
          ...headers,
        },
        redirect: "manual",
      });

      if ([301,302,303,307,308].includes(res.status)) {
        const location = res.headers.get("location");
        if (!location) throw new Error("redirect without location");
        current = assertSafePublicHttps(new URL(location, current).toString());
        hops += 1;
        continue;
      }

      if (!res.ok) throw new Error(`HTTP ${res.status} for ${current}`);
      const text = await res.text();
      await logMechanismEvent(
        mechanism.id, cycleId, "https_get",
        { url: rawUrl, final_url: current.toString(), purpose },
        { status: res.status, bytes: text.length, redirects: hops },
        true,
      );
      return { text, finalUrl: current.toString(), status: res.status };
    }
    throw new Error("too many redirects");
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    await logMechanismEvent(
      mechanism.id, cycleId, "https_get",
      { url: rawUrl, purpose },
      { error: message },
      false,
    );
    throw e;
  }
}

function parseStableVersion(html: string): string | null {
  for (const p of [
    /Download Python\s+(\d+\.\d+\.\d+)/i,
    /Latest Python 3 Release\s*-?\s*Python\s+(\d+\.\d+\.\d+)/i,
  ]) {
    const m = html.match(p);
    if (m) return m[1];
  }
  return null;
}
function stripHtml(s: string) {
  return s.replace(/<script[\s\S]*?<\/script>/gi," ")
    .replace(/<style[\s\S]*?<\/style>/gi," ")
    .replace(/<[^>]+>/g," ").replace(/&nbsp;/g," ")
    .replace(/&amp;/g,"&").replace(/\s+/g," ").trim();
}
function pageTitle(html: string) {
  const m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return m ? stripHtml(m[1]).slice(0,300) : null;
}
async function recordEvidence(cycleId:number, url:string, kind:string, title:string|null, observed:Json) {
  const { data, error } = await db.from("mind_core_evidence").insert({
    cycle_id:cycleId, source_url:url, source_kind:kind, source_title:title, observed
  }).select("id").single();
  if (error) throw error;
  return Number(data.id);
}
async function spawnGoal(args:{
  goal_key:string; kind:string; target?:Json; rationale:string; priority:number;
  created_from_cycle:number; recurrence_minutes?:number|null;
}) {
  const { error } = await db.from("mind_core_goals").upsert({
    goal_key:args.goal_key, kind:args.kind, target:args.target ?? {},
    rationale:args.rationale, priority:Math.max(0,Math.min(1,args.priority)),
    status:"pending", recurrence_minutes:args.recurrence_minutes ?? null,
    not_before:nowIso(), created_from_cycle:args.created_from_cycle, updated_at:nowIso(),
  }, { onConflict:"goal_key", ignoreDuplicates:true });
  if (error) throw error;
}
function isAllowedReference(urlString:string) {
  try {
    const u = assertSafePublicHttps(urlString);
    return [
      "www.python.org","python.org","docs.python.org","peps.python.org","discuss.python.org"
    ].includes(u.hostname);
  } catch { return false; }
}
async function generateGoalsFromIssue(cycleId:number, repo:string, issue:Json) {
  const body = String(issue.body ?? "");
  for (const m of body.matchAll(/https:\/\/github\.com\/python\/cpython\/(issues|pull)\/(\d+)/g)) {
    const kind = m[1] === "pull" ? "inspect_github_pull" : "inspect_github_issue";
    const n = Number(m[2]);
    if (Number.isFinite(n) && n !== issue.number) await spawnGoal({
      goal_key:`${kind}:${n}`, kind, target:{repo,number:n},
      rationale:`Reference discovered inside CPython issue #${issue.number}.`,
      priority:kind === "inspect_github_pull" ? 0.90 : 0.82, created_from_cycle:cycleId,
    });
  }
  for (const m of body.matchAll(/https:\/\/(?:www\.)?(?:python\.org|docs\.python\.org|peps\.python\.org|discuss\.python\.org)\/[^\s)\]>"']+/g)) {
    const url = m[0].replace(/[.,;:]+$/,"");
    if (isAllowedReference(url)) await spawnGoal({
      goal_key:`web:${url}`, kind:"inspect_web_reference", target:{url},
      rationale:`Public reference discovered inside CPython issue #${issue.number}.`,
      priority:url.includes("peps.python.org") ? 0.86 : 0.72, created_from_cycle:cycleId,
    });
  }
  const labels = Array.isArray(issue.labels) ? issue.labels : [];
  if (issue.state === "open" && labels.some((l:any)=>(typeof l==="string"?l:l?.name)==="release-blocker")) {
    await spawnGoal({
      goal_key:`recheck-issue:${repo}#${issue.number}`,
      kind:"inspect_github_issue", target:{repo,number:issue.number},
      rationale:"Open release-blocker remains time-sensitive.",
      priority:0.68, created_from_cycle:cycleId, recurrence_minutes:180,
    });
  }
}


async function getMechanismByKey(key:string) {
  const {data,error}=await db.from("mind_core_mechanisms").select("*").eq("mechanism_key",key).single();
  if(error) throw error;
  return data;
}

function recencyPressure(ts:any) {
  const t=Date.parse(String(ts??""));
  if(!Number.isFinite(t)) return 0.45;
  const hours=Math.max(0,(Date.now()-t)/3600000);
  if(hours<=24) return 1.0;
  if(hours<=72) return 0.8;
  if(hours<=168) return 0.6;
  return 0.4;
}

async function curiosityFromEvidence(sourceEvidenceId:number, cycleId:number, admitOnSuccess=false) {
  const mechanism=await getMechanismByKey(CURIOSITY_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) throw new Error("curiosity mechanism inactive");

  const {data:evidence,error:evidenceError}=await db
    .from("mind_core_evidence")
    .select("id,cycle_id,source_kind,source_title,source_url,observed,fetched_at")
    .eq("id",sourceEvidenceId)
    .single();
  if(evidenceError) throw evidenceError;

  const o=(evidence?.observed??{}) as Json;
  const labels=Array.isArray(o.labels)?o.labels.map((x:any)=>String(x).toLowerCase()):[];
  const critical=labels.some((x:string)=>["release-blocker","critical","security","blocker"].includes(x));
  const unresolved=String(o.state??"").toLowerCase()==="open" || (o.state===undefined && o.closed_at===null);
  const comments=Number(o.comments??0);
  const commentText=Array.isArray(o.comments)
    ? o.comments.map((c:any)=>String(c?.body??"")).join("\n")
    : "";
  const body=String(o.body_excerpt??o.text_excerpt??commentText??"");
  const mismatch=body.match(/have\s+([0-9]+(?:\.[0-9]+){1,3})\s*,\s*need(?:\s+exactly)?\s+([0-9]+(?:\.[0-9]+){1,3})/i);

  let question="";
  let questionKey="";
  let derivedKind="";
  let target:Json={};
  let causalGap=0.35;

  const relatedIssueMatch=body.match(/https:\/\/github\.com\/python\/cpython\/issues\/(\d+)/i);

  if(relatedIssueMatch && Number.isFinite(Number(o.number)) && Number(relatedIssueMatch[1]) !== Number(o.number)) {
    const repo=String(o.repo??"python/cpython");
    const number=Number(o.number);
    const related=Number(relatedIssueMatch[1]);
    question=`How does prior ${repo} issue #${related} explain the workaround or state referenced from issue #${number}, and what causal connection does it have to the current failure?`;
    questionKey=`causal-link:${repo}#${number}->${related}`;
    derivedKind="inspect_github_issue";
    target={repo,number:related,question,origin_issue:number};
    causalGap=0.95;
  } else if(mismatch && Number.isFinite(Number(o.number))) {
    const repo=String(o.repo??"python/cpython");
    const number=Number(o.number);
    question=`What caused the observed dependency mismatch in ${repo} issue #${number} (have ${mismatch[1]}, need ${mismatch[2]}), and do the latest discussion comments identify a fix or resolution path?`;
    questionKey=`mismatch:${repo}#${number}:${mismatch[1]}->${mismatch[2]}`;
    derivedKind="inspect_issue_comments";
    target={repo,number,question};
    causalGap=1.0;
  } else if(unresolved && comments>0 && Number.isFinite(Number(o.number))) {
    const repo=String(o.repo??"python/cpython");
    const number=Number(o.number);
    question=`What do the latest discussion comments on ${repo} issue #${number} reveal about its cause, proposed fix, and current resolution path?`;
    questionKey=`discussion-gap:${repo}#${number}`;
    derivedKind="inspect_issue_comments";
    target={repo,number,question};
    causalGap=0.85;
  } else if(critical && Number.isFinite(Number(o.number))) {
    const repo=String(o.repo??"python/cpython");
    const number=Number(o.number);
    question=`What evidence currently explains why ${repo} issue #${number} remains a critical blocker, and what concrete change would resolve it?`;
    questionKey=`critical-gap:${repo}#${number}`;
    derivedKind="inspect_issue_comments";
    target={repo,number,question};
    causalGap=0.75;
  } else {
    throw new Error("evidence contains no sufficiently strong unresolved curiosity pressure");
  }

  const uncertainty=unresolved?1.0:0.55;
  const impact=critical?1.0:0.55;
  const temporal=recencyPressure(o.updated_at??evidence.fetched_at);
  const novelty=1.0;
  const score=Math.max(0,Math.min(1,
    0.30*uncertainty + 0.25*impact + 0.20*causalGap + 0.15*novelty + 0.10*temporal
  ));

  const {data:existing}=await db.from("mind_core_questions")
    .select("id,derived_goal_id,status").eq("question_key",questionKey).maybeSingle();

  let questionId:number;
  let goalId:number|null=existing?.derived_goal_id??null;

  if(existing?.id) {
    questionId=existing.id;
  } else {
    const {data:qrow,error:qerr}=await db.from("mind_core_questions").insert({
      question_key:questionKey,
      question,
      source_evidence_id:sourceEvidenceId,
      mechanism_id:mechanism.id,
      pressure:{uncertainty,impact,causal_gap:causalGap,novelty,temporal},
      interest_score:score,
      status:"pending",
    }).select("id").single();
    if(qerr) throw qerr;
    questionId=qrow.id;

    const goalKey=`question:${questionId}`;
    const {data:g,error:gerr}=await db.from("mind_core_goals").insert({
      goal_key:goalKey,
      kind:derivedKind,
      target:{...target,question_id:questionId},
      rationale:`Generated by M0002 from evidence #${sourceEvidenceId}: interest=${score.toFixed(3)}`,
      priority:score,
      status:"pending",
      recurrence_minutes:null,
      not_before:nowIso(),
      created_from_cycle:cycleId,
      updated_at:nowIso(),
    }).select("id").single();
    if(gerr) throw gerr;
    goalId=g.id;

    const {error:uq}=await db.from("mind_core_questions").update({
      derived_goal_id:goalId,updated_at:nowIso()
    }).eq("id",questionId);
    if(uq) throw uq;
  }

  const observed={
    source_evidence_id:sourceEvidenceId,
    question_id:questionId,
    question_key:questionKey,
    question,
    interest_score:score,
    pressure:{uncertainty,impact,causal_gap:causalGap,novelty,temporal},
    derived_goal_id:goalId,
    derived_goal_kind:derivedKind,
    generated_at:nowIso(),
  };

  await logMechanismEvent(
    mechanism.id,cycleId,"question_genesis",
    {source_evidence_id:sourceEvidenceId},
    observed,true
  );

  if(admitOnSuccess && !existing?.id) {
    const ev={
      ...(mechanism.evidence??{}),
      independent_self_test:observed,
      admitted_reason:"Generated a novel, source-grounded question and executable research goal from genuine autonomous internet evidence.",
    };
    const {error:me}=await db.from("mind_core_mechanisms").update({
      status:"admitted",evidence:ev,admitted_at:nowIso(),updated_at:nowIso()
    }).eq("mechanism_key",CURIOSITY_MECHANISM);
    if(me) throw me;
  }

  return observed;
}

async function answerIssueComments(goal:Goal, cycleId:number) {
  const repo=String(goal.target?.repo??"python/cpython");
  const number=Number(goal.target?.number);
  const questionId=Number(goal.target?.question_id);
  if(!Number.isFinite(number)) throw new Error("invalid issue number");
  const url=`https://api.github.com/repos/${repo}/issues/${number}/comments?per_page=100`;
  const {text}=await internetGet(cycleId,url,`answer generated curiosity question for issue #${number}`,GH_HEADERS);
  const json=JSON.parse(text);
  const comments=Array.isArray(json)?json.map((c:any)=>({
    user:c.user?.login??null,
    created_at:c.created_at,
    updated_at:c.updated_at,
    body:String(c.body??"").slice(0,5000),
    html_url:c.html_url,
  })):[];
  const observed={
    repo,number,
    generated_question:String(goal.target?.question??""),
    comment_count:comments.length,
    comments,
    checked_at:nowIso(),
  };
  const evidenceId=await recordEvidence(cycleId,url,"github_issue_comments",`Comments for issue #${number}`,observed);

  if(Number.isFinite(questionId)) {
    const {error}=await db.from("mind_core_questions").update({
      status:"answered",answer_cycle_id:cycleId,answer:observed,updated_at:nowIso()
    }).eq("id",questionId);
    if(error) throw error;
  }

  try {
    const cm=await getMechanismByKey(CURIOSITY_MECHANISM);
    if(cm?.status==="admitted") await curiosityFromEvidence(evidenceId,cycleId,false);
  } catch(e) {
    console.log("curiosity follow-up skipped", e instanceof Error ? e.message : String(e));
  }
  return observed;
}

async function executeGoal(goal:Goal, cycleId:number) {
  if (goal.kind === "curiosity_evaluate") {
    const evidenceId=Number(goal.target?.evidence_id);
    if(!Number.isFinite(evidenceId)) throw new Error("invalid curiosity evidence id");
    return await curiosityFromEvidence(evidenceId,cycleId,false);
  }

  if (goal.kind === "curiosity_self_test") {
    const evidenceId=Number(goal.target?.evidence_id);
    if(!Number.isFinite(evidenceId)) throw new Error("invalid curiosity self-test evidence id");
    return await curiosityFromEvidence(evidenceId,cycleId,true);
  }

  if (goal.kind === "inspect_issue_comments") {
    return await answerIssueComments(goal,cycleId);
  }

  if (goal.kind === "mechanism_self_test") {
    const url = String(goal.target?.url ?? "");
    const expected = String(goal.target?.expected_contains ?? "");
    const { text, finalUrl, status } = await internetGet(cycleId, url, "mechanism #1 independent self-test");
    const passed = expected ? stripHtml(text).includes(expected) : text.length > 100;
    const observed = {
      mechanism_key: String(goal.target?.mechanism_key ?? INTERNET_MECHANISM),
      url, final_url:finalUrl, http_status:status, bytes:text.length,
      expected_contains:expected, passed, checked_at:nowIso(),
    };
    await recordEvidence(cycleId,url,"mechanism_self_test",pageTitle(text),observed);
    if (!passed) throw new Error("real internet mechanism self-test failed");

    const { data: mech, error } = await db.from("mind_core_mechanisms")
      .select("evidence").eq("mechanism_key",INTERNET_MECHANISM).single();
    if (error) throw error;
    const evidence = {
      ...(mech?.evidence ?? {}),
      independent_self_test: observed,
      admitted_reason: "Real HTTPS response from public IANA site with expected content and provenance.",
    };
    const { error:updateError } = await db.from("mind_core_mechanisms").update({
      status:"admitted", evidence, admitted_at:nowIso(), updated_at:nowIso()
    }).eq("mechanism_key",INTERNET_MECHANISM);
    if (updateError) throw updateError;
    return observed;
  }

  if (goal.kind === "verify_stable_release") {
    const url="https://www.python.org/downloads/";
    const { text } = await internetGet(cycleId,url,"verify current stable Python release");
    const observed={current_stable:parseStableVersion(text),checked_at:nowIso(),content_length:text.length};
    await recordEvidence(cycleId,url,"official_web","Python Downloads",observed);
    return observed;
  }

  if (goal.kind === "scan_release_blockers") {
    const repo=String(goal.target?.repo ?? "python/cpython");
    const q=encodeURIComponent(`repo:${repo} is:issue is:open label:release-blocker`);
    const url=`https://api.github.com/search/issues?q=${q}&sort=updated&order=desc&per_page=10`;
    const { text } = await internetGet(cycleId,url,"scan open CPython release blockers",GH_HEADERS);
    const json=JSON.parse(text);
    const issues=Array.isArray(json.items)?json.items.map((x:any)=>({
      number:x.number,title:x.title,html_url:x.html_url,updated_at:x.updated_at,
      labels:Array.isArray(x.labels)?x.labels.map((l:any)=>typeof l==="string"?l:l?.name).filter(Boolean):[],
    })):[];
    const observed={repo,total_count:json.total_count??null,issues,checked_at:nowIso()};
    await recordEvidence(cycleId,url,"github_api","Open CPython release-blocker issues",observed);
    for (const issue of issues) await spawnGoal({
      goal_key:`github-issue:${repo}#${issue.number}`, kind:"inspect_github_issue",
      target:{repo,number:issue.number}, rationale:"Unresolved release-blocker discovered by live internet scan.",
      priority:0.95, created_from_cycle:cycleId,
    });
    return observed;
  }

  if (goal.kind === "inspect_github_issue") {
    const repo=String(goal.target?.repo ?? "python/cpython");
    const number=Number(goal.target?.number);
    if(!Number.isFinite(number)) throw new Error("invalid issue number");
    const url=`https://api.github.com/repos/${repo}/issues/${number}`;
    const { text } = await internetGet(cycleId,url,`inspect GitHub issue #${number}`,GH_HEADERS);
    const issue=JSON.parse(text);
    const labels=Array.isArray(issue.labels)?issue.labels.map((l:any)=>typeof l==="string"?l:l?.name).filter(Boolean):[];
    const observed={
      repo,number:issue.number,title:issue.title,state:issue.state,state_reason:issue.state_reason??null,
      labels,milestone:issue.milestone?.title??null,
      assignees:Array.isArray(issue.assignees)?issue.assignees.map((a:any)=>a.login):[],
      comments:issue.comments??0,created_at:issue.created_at,updated_at:issue.updated_at,
      closed_at:issue.closed_at,html_url:issue.html_url,body_excerpt:String(issue.body??"").slice(0,6000),
      checked_at:nowIso(),
    };
    const evidenceId=await recordEvidence(cycleId,url,"github_api",`CPython issue #${number}`,observed);
    await generateGoalsFromIssue(cycleId,repo,{...issue,labels});

    const questionId=Number(goal.target?.question_id);
    if(Number.isFinite(questionId)) {
      const {error:qerr}=await db.from("mind_core_questions").update({
        status:"answered",answer_cycle_id:cycleId,answer:observed,updated_at:nowIso()
      }).eq("id",questionId);
      if(qerr) throw qerr;
    }

    try {
      const cm=await getMechanismByKey(CURIOSITY_MECHANISM);
      if(cm?.status==="admitted") await curiosityFromEvidence(evidenceId,cycleId,false);
    } catch(e) {
      console.log("curiosity follow-up skipped", e instanceof Error ? e.message : String(e));
    }
    return observed;
  }

  if (goal.kind === "inspect_github_pull") {
    const repo=String(goal.target?.repo ?? "python/cpython");
    const number=Number(goal.target?.number);
    if(!Number.isFinite(number)) throw new Error("invalid pull number");
    const url=`https://api.github.com/repos/${repo}/pulls/${number}`;
    const { text } = await internetGet(cycleId,url,`inspect GitHub pull #${number}`,GH_HEADERS);
    const pr=JSON.parse(text);
    const observed={
      repo,number:pr.number,title:pr.title,state:pr.state,draft:pr.draft??false,
      merged:pr.merged??false,mergeable_state:pr.mergeable_state??null,html_url:pr.html_url,
      created_at:pr.created_at,updated_at:pr.updated_at,merged_at:pr.merged_at,
      body_excerpt:String(pr.body??"").slice(0,6000),checked_at:nowIso(),
    };
    await recordEvidence(cycleId,url,"github_api",`CPython pull #${number}`,observed);
    return observed;
  }

  if (goal.kind === "inspect_web_reference") {
    const url=String(goal.target?.url??"");
    if(!isAllowedReference(url)) throw new Error("reference host not allowed");
    const { text, finalUrl }=await internetGet(cycleId,url,"inspect discovered public web reference");
    const observed={url,final_url:finalUrl,title:pageTitle(text),text_excerpt:stripHtml(text).slice(0,8000),content_length:text.length,checked_at:nowIso()};
    await recordEvidence(cycleId,url,"public_web_reference",observed.title,observed);
    return observed;
  }

  throw new Error(`unsupported goal kind: ${goal.kind}`);
}

async function chooseGoal():Promise<Goal|null>{
  const {data,error}=await db.from("mind_core_goals").select("*")
    .in("status",["pending","completed"]).order("priority",{ascending:false}).limit(200);
  if(error) throw error;
  const now=Date.now();
  const eligible=(data??[]).filter((g:Goal)=>{
    if(Date.parse(g.not_before)>now) return false;
    if(g.status==="pending") return true;
    return g.status==="completed" && !!g.recurrence_minutes && !!g.last_run_at &&
      Date.parse(g.last_run_at)+g.recurrence_minutes*60_000<=now;
  });
  if(!eligible.length) return null;
  eligible.sort((a:Goal,b:Goal)=>b.priority-a.priority);
  return eligible[0] as Goal;
}
async function frontierSize(){
  const {data}=await db.from("mind_core_goals").select("status,recurrence_minutes,last_run_at,not_before")
    .in("status",["pending","completed"]).limit(500);
  const now=Date.now();
  return (data??[]).filter((g:any)=>{
    if(Date.parse(g.not_before)>now) return false;
    if(g.status==="pending") return true;
    return g.status==="completed" && g.recurrence_minutes && g.last_run_at &&
      Date.parse(g.last_run_at)+g.recurrence_minutes*60_000<=now;
  }).length;
}

Deno.serve(async(req:Request)=>{
  if(req.method!=="POST") return Response.json({
    ok:false,error:"NOESIS_REMOVED",replacement:"UnifiedKernel",removed_at:"2026-10-01",
    mind_core_route:"POST JSON {mode: 'mind-core'}"
  },{status:410});
  let body:any={}; try{body=await req.json();}catch{}
  if(body?.mode!=="mind-core") return Response.json({
    ok:false,error:"NOESIS_REMOVED",replacement:"UnifiedKernel",removed_at:"2026-10-01"
  },{status:410});

  let cycleId:number|null=null; let goal:Goal|null=null;
  try{
    goal=await chooseGoal();
    if(!goal) return Response.json({ok:true,idle:true,reason:"no eligible self-generated goals"});
    const {error:mark}=await db.from("mind_core_goals").update({status:"running",updated_at:nowIso()}).eq("id",goal.id);
    if(mark) throw mark;

    const {data:cycle,error:ce}=await db.from("mind_core_cycles").insert({
      status:"running",trigger_source:body?.trigger??"http",focus:goal.kind
    }).select("id").single();
    if(ce) throw ce; cycleId=cycle.id;

    const result=await executeGoal(goal,cycleId);
    const nextNotBefore=goal.recurrence_minutes
      ? new Date(Date.now()+goal.recurrence_minutes*60_000).toISOString()
      : goal.not_before;
    const {error:fg}=await db.from("mind_core_goals").update({
      status:"completed",last_run_at:nowIso(),run_count:(goal.run_count??0)+1,
      last_result:result,last_error:null,not_before:nextNotBefore,updated_at:nowIso()
    }).eq("id",goal.id);
    if(fg) throw fg;

    const {data:stateRow}=await db.from("mind_core_state").select("state").eq("id","main").single();
    const state=(stateRow?.state??{}) as CoreState;
    const fSize=await frontierSize();
    const nextState:CoreState={
      ...state,version:"0.4.2-cloud-autonomous-curiosity-loop",last_cycle_at:nowIso(),
      last_focus:goal.kind,last_observation:result,
      current_goal:{id:goal.id,key:goal.goal_key,kind:goal.kind,rationale:goal.rationale,priority:goal.priority},
      frontier_size:fSize
    };
    if(goal.kind==="verify_stable_release" && result.current_stable) nextState.last_stable=result.current_stable;
    const {error:se}=await db.from("mind_core_state").update({state:nextState,updated_at:nowIso()}).eq("id","main");
    if(se) throw se;

    const summary={goal:{id:goal.id,key:goal.goal_key,kind:goal.kind,priority:goal.priority,rationale:goal.rationale},observed:result,frontier_size_after:fSize};
    const {error:cf}=await db.from("mind_core_cycles").update({
      finished_at:nowIso(),status:"completed",summary
    }).eq("id",cycleId);
    if(cf) throw cf;

    return Response.json({ok:true,cycle_id:cycleId,selected_goal:summary.goal,result,frontier_size_after:fSize});
  }catch(error){
    const message=error instanceof Error?error.message:String(error);
    if(cycleId!==null) await db.from("mind_core_cycles").update({
      finished_at:nowIso(),status:"failed",error:message
    }).eq("id",cycleId);
    if(goal) await db.from("mind_core_goals").update({
      status:(goal.run_count??0)<2?"pending":"failed",last_error:message,
      not_before:new Date(Date.now()+60*60_000).toISOString(),updated_at:nowIso()
    }).eq("id",goal.id);
    console.error("mind-core cycle failed",message);
    return Response.json({ok:false,error:message},{status:500});
  }
});
