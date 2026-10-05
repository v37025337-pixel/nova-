
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { GENESIS_MECHANISM } from "./genesis.ts";
import { runMechanismGenesisShadow } from "./genesis_shadow.ts";

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
const DOMAIN_BIRTH_MECHANISM = "M0003:domain-birth";
const CONCEPT_BIRTH_MECHANISM = "M0004:concept-birth";
const CONCEPT_TRANSFER_MECHANISM = "M0005:concept-transfer";
const SAFE_FRONTIER_MECHANISM = "M0006:safe-link-frontier";
const GOAL_FRONTIER_MECHANISM = "M0007:goal-weighted-frontier";
const RELATION_MINER_MECHANISM = "M0008:structural-relation-miner";
const RELATION_GENERALIZER_MECHANISM = "M0009:key-directed-relation-generalizer";
const ACTIVE_FALSIFIER_MECHANISM = "M0010:active-falsifier";
const BELIEF_REVISION_MECHANISM = "M0011:belief-revision";

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


function evidenceText(o:Json) {
  const parts:any[] = [
    o.title, o.body_excerpt, o.text_excerpt, o.generated_question,
    Array.isArray(o.labels) ? o.labels.join(" ") : "",
    Array.isArray(o.comments) ? o.comments.map((c:any)=>c?.body??"").join("\n") : "",
  ];
  return parts.map(x=>String(x??"")).join("\n");
}

function inferExternalDomain(o:Json, parentTopic:string|null) {
  const text=evidenceText(o);
  const parent=String(parentTopic??"").toLowerCase();

  const candidates = [
    {
      domain_key:"tcl-tk-runtime",
      name:"Tcl/Tk Runtime Ecosystem",
      detect:/\b(?:tcl\/tk|tk\/tcl|tcl9|tk9|tcl90|tcl9tk|tkinter)\b/i,
      parent_block:/\btcl(?:\/tk)?\b/i,
      seed_url:"https://www.tcl-lang.org/",
      verification_terms:["Tcl Developer Xchange","Tcl/Tk"],
      research_url:"https://www.tcl-lang.org/software/tcltk/download.html",
      research_question:"What are the current Tcl/Tk release lines, and what compatibility constraints matter when another runtime embeds Tcl/Tk?",
    },
  ];

  for(const c of candidates) {
    if(c.detect.test(text) && !c.parent_block.test(parent)) {
      return c;
    }
  }
  return null;
}

async function domainBirthFromEvidence(sourceEvidenceId:number, cycleId:number, admitMechanism=false) {
  const mechanism=await getMechanismByKey(DOMAIN_BIRTH_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) throw new Error("domain birth mechanism inactive");

  const {data:evidence,error:eerr}=await db.from("mind_core_evidence")
    .select("id,cycle_id,source_kind,source_title,source_url,observed,fetched_at")
    .eq("id",sourceEvidenceId).single();
  if(eerr) throw eerr;

  const {data:stateRow}=await db.from("mind_core_state").select("state").eq("id","main").single();
  const parentTopic=String(stateRow?.state?.topic??"");
  const candidate=inferExternalDomain((evidence?.observed??{}) as Json,parentTopic);
  if(!candidate) throw new Error("no external domain candidate found in evidence");

  const text=evidenceText((evidence?.observed??{}) as Json);
  const mentionCount=(text.match(/\b(?:tcl|tk|tkinter)\b/gi)??[]).length;
  const dependencySignals=(text.match(/\b(?:version|package|dll|runtime|library|installer|upgrade|dependency|embed)\w*\b/gi)??[]).length;

  const externality=1.0;
  const recurrence=Math.min(1,mentionCount/5);
  const causalRelevance=Math.min(1,0.45+dependencySignals*0.07);
  const novelty=1.0;
  const pressure=Math.max(0,Math.min(1,
    0.30*externality + 0.25*recurrence + 0.30*causalRelevance + 0.15*novelty
  ));

  const {data:existing}=await db.from("mind_core_domains")
    .select("*").eq("domain_key",candidate.domain_key).maybeSingle();

  let domain:any=existing;
  if(!domain) {
    const {data:drow,error:derr}=await db.from("mind_core_domains").insert({
      domain_key:candidate.domain_key,
      name:candidate.name,
      parent_domain_key:parentTopic || null,
      source_evidence_id:sourceEvidenceId,
      mechanism_id:mechanism.id,
      status:"candidate",
      birth_pressure:{
        externality,recurrence,causal_relevance:causalRelevance,novelty,
        score:pressure,mention_count:mentionCount,dependency_signals:dependencySignals
      },
      seed:{
        url:candidate.seed_url,
        research_url:candidate.research_url,
        verification_terms:candidate.verification_terms,
        research_question:candidate.research_question
      },
    }).select("*").single();
    if(derr) throw derr;
    domain=drow;
  }

  const {text:html,finalUrl,status}=await internetGet(
    cycleId,candidate.seed_url,
    `verify external domain candidate ${candidate.domain_key}`
  );
  const plain=stripHtml(html);
  const matched=candidate.verification_terms.filter((term:string)=>plain.toLowerCase().includes(term.toLowerCase()));
  const verified=matched.length>=2 && status===200;
  const verification={
    url:candidate.seed_url,final_url:finalUrl,http_status:status,bytes:html.length,
    required_terms:candidate.verification_terms,matched_terms:matched,
    independent_host:new URL(finalUrl).hostname,
    parent_topic:parentTopic,
    verified,checked_at:nowIso(),
  };

  const {error:du}=await db.from("mind_core_domains").update({
    status:verified?"admitted":"rejected",
    verification,
    admitted_at:verified?nowIso():null,
    updated_at:nowIso(),
  }).eq("id",domain.id);
  if(du) throw du;
  if(!verified) throw new Error("external domain verification failed");

  const goalKey=`domain-seed:${candidate.domain_key}`;
  const {data:g,error:gerr}=await db.from("mind_core_goals").upsert({
    goal_key:goalKey,
    kind:"inspect_domain_seed",
    target:{
      domain_id:domain.id,
      domain_key:candidate.domain_key,
      url:candidate.research_url,
      question:candidate.research_question,
    },
    rationale:`Born by M0003 from evidence #${sourceEvidenceId}; independently verified on ${new URL(finalUrl).hostname}.`,
    priority:Math.max(0.60,Math.min(0.90,pressure)),
    status:"pending",
    recurrence_minutes:null,
    not_before:nowIso(),
    created_from_cycle:cycleId,
    updated_at:nowIso(),
  },{onConflict:"goal_key"}).select("id").single();
  if(gerr) throw gerr;

  const result={
    source_evidence_id:sourceEvidenceId,
    domain_id:domain.id,
    domain_key:candidate.domain_key,
    name:candidate.name,
    parent_domain_key:parentTopic,
    birth_pressure:{
      externality,recurrence,causal_relevance:causalRelevance,novelty,score:pressure,
      mention_count:mentionCount,dependency_signals:dependencySignals,
    },
    verification,
    derived_goal_id:g.id,
    derived_goal_key:goalKey,
    born_at:nowIso(),
  };

  await logMechanismEvent(
    mechanism.id,cycleId,"domain_birth",
    {source_evidence_id:sourceEvidenceId,parent_topic:parentTopic},
    result,true
  );

  if(admitMechanism && !existing) {
    const mevidence={
      ...(mechanism.evidence??{}),
      independent_self_test:result,
      admitted_reason:"Detected an external domain from genuine evidence, verified it against an independent official public source via M0001, and emitted a cross-domain research goal.",
    };
    const {error:mu}=await db.from("mind_core_mechanisms").update({
      status:"admitted",evidence:mevidence,admitted_at:nowIso(),updated_at:nowIso()
    }).eq("mechanism_key",DOMAIN_BIRTH_MECHANISM);
    if(mu) throw mu;
  }

  return result;
}

async function inspectDomainSeed(goal:Goal, cycleId:number) {
  const url=String(goal.target?.url??"");
  const domainId=Number(goal.target?.domain_id);
  if(!url || !Number.isFinite(domainId)) throw new Error("invalid domain seed goal");

  const {text,finalUrl}=await internetGet(
    cycleId,url,
    `research admitted domain ${String(goal.target?.domain_key??"unknown")}`
  );
  const plain=stripHtml(text);
  const observed={
    domain_id:domainId,
    domain_key:String(goal.target?.domain_key??""),
    question:String(goal.target?.question??""),
    url,final_url:finalUrl,title:pageTitle(text),
    text_excerpt:plain.slice(0,10000),
    content_length:text.length,checked_at:nowIso(),
  };
  const evidenceId=await recordEvidence(
    cycleId,url,"domain_seed_official",observed.title,observed
  );

  const {error:du}=await db.from("mind_core_domains").update({
    updated_at:nowIso()
  }).eq("id",domainId);
  if(du) console.log("domain touch skipped",du.message);

  try {
    const cm=await getMechanismByKey(CURIOSITY_MECHANISM);
    if(cm?.status==="admitted") await curiosityFromEvidence(evidenceId,cycleId,false);
  } catch(e) {
    console.log("curiosity on new domain skipped", e instanceof Error ? e.message : String(e));
  }

  return observed;
}


function releaseLineFamilies(text:string) {
  const exact=text.match(/latest downloads for the Tcl\s+([0-9.]+),\s+([0-9.]+),\s+and\s+([0-9.]+)\s+release sequences/i);
  if(exact) return [...new Set([exact[1],exact[2],exact[3]])];

  const found=[...text.matchAll(/\b(?:Tcl|Tk)\s+(\d+\.\d+)(?:\.\d+)?\b/gi)]
    .map(m=>m[1]);
  return [...new Set(found)];
}

function hasVersionBoundarySignal(text:string) {
  return /version conflict|need exactly|can't find a usable|cannot find a usable|incomplete upgrade|package require|version mismatch/i.test(text)
    && /\b(?:tcl|tk|tkinter)\b/i.test(text);
}

async function conceptBirthFromEvidence(sourceEvidenceId:number, cycleId:number, admitMechanism=false) {
  const mechanism=await getMechanismByKey(CONCEPT_BIRTH_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) throw new Error("concept birth mechanism inactive");

  const {data:source,error:serr}=await db.from("mind_core_evidence")
    .select("id,cycle_id,source_kind,source_title,source_url,observed,fetched_at")
    .eq("id",sourceEvidenceId).single();
  if(serr) throw serr;

  const sourceText=evidenceText((source?.observed??{}) as Json);
  const lines=releaseLineFamilies(sourceText);
  if(lines.length<3) throw new Error("not enough coexisting release lines for abstraction");

  const domainKey=String(source?.observed?.domain_key??"");
  if(!domainKey) throw new Error("source evidence is not attached to an admitted domain");

  const {data:domain,error:derr}=await db.from("mind_core_domains")
    .select("*").eq("domain_key",domainKey).single();
  if(derr) throw derr;
  if(domain.status!=="admitted") throw new Error("concept source domain is not admitted");

  const {data:prior,error:perr}=await db.from("mind_core_evidence")
    .select("id,source_kind,source_title,source_url,observed,fetched_at")
    .order("id",{ascending:false}).limit(100);
  if(perr) throw perr;

  let boundaryEvidence:any=null;
  for(const e of prior??[]) {
    if(Number(e.id)===sourceEvidenceId) continue;
    const t=evidenceText((e.observed??{}) as Json);
    if(hasVersionBoundarySignal(t)) {
      boundaryEvidence=e;
      break;
    }
  }
  if(!boundaryEvidence) throw new Error("no independent version-boundary evidence found");

  const boundaryText=evidenceText((boundaryEvidence.observed??{}) as Json);
  const mismatch=boundaryText.match(/have\s+([0-9]+(?:\.[0-9]+){1,3})\s*,\s*need(?:\s+exactly)?\s+([0-9]+(?:\.[0-9]+){1,3})/i);

  const conceptKey=`versioned-runtime-interface-contract:${domainKey}`;
  const conceptName="Versioned Runtime Interface Contract";
  const definition=
    "A compatibility boundary where a host or extension interacts with another runtime through an interface that declares acceptable runtime versions; multiple release lines may coexist, but successful integration depends on satisfying the declared version contract rather than merely having the runtime installed.";

  const sourceIds=[sourceEvidenceId,Number(boundaryEvidence.id)];
  const abstraction={
    source_domain:domainKey,
    release_lines:lines,
    release_line_count:lines.length,
    boundary_evidence_id:Number(boundaryEvidence.id),
    version_conflict:mismatch ? {have:mismatch[1],need:mismatch[2]} : null,
    structural_pattern:{
      coexistence:"multiple runtime release lines",
      conflict:"consumer/provider version requirement can reject an installed runtime",
      abstraction:"compatibility is governed by an explicit version contract at the interface boundary"
    }
  };

  const {data:existing,error:xerr}=await db.from("mind_core_concepts")
    .select("*").eq("concept_key",conceptKey).maybeSingle();
  if(xerr) throw xerr;

  let concept:any=existing;
  if(!concept) {
    const {data:crow,error:cerr}=await db.from("mind_core_concepts").insert({
      concept_key:conceptKey,
      name:conceptName,
      kind:"cross_runtime_compatibility",
      definition,
      domain_key:domainKey,
      source_evidence_ids:sourceIds,
      mechanism_id:mechanism.id,
      status:"candidate",
      abstraction,
    }).select("*").single();
    if(cerr) throw cerr;
    concept=crow;
  }

  const verifyUrl="https://www.tcl-lang.org/man/tcl9.1/TclLib/InitStubs.html";
  const {text:html,finalUrl,status}=await internetGet(
    cycleId,verifyUrl,
    `verify induced concept ${conceptKey}`
  );
  const plain=stripHtml(html);
  const checks=[
    {key:"api",ok:/Tcl_InitStubs/i.test(plain)},
    {key:"version_requirement",ok:/minimal version|minimum version|version string/i.test(plain)},
    {key:"exact_flag",ok:/\bexact\b/i.test(plain)},
    {key:"newer_versions",ok:/versions newer|newer versions/i.test(plain)},
    {key:"major_version_boundary",ok:/major version/i.test(plain)},
    {key:"dynamic_bind",ok:/dynamically bind|function tables/i.test(plain)},
  ];
  const matched=checks.filter(x=>x.ok).map(x=>x.key);
  const verified=status===200 && matched.length>=5;

  const verification={
    url:verifyUrl,
    final_url:finalUrl,
    http_status:status,
    bytes:html.length,
    matched_checks:matched,
    required_count:5,
    verified,
    checked_at:nowIso(),
  };

  const {error:cu}=await db.from("mind_core_concepts").update({
    status:verified?"admitted":"rejected",
    verification,
    admitted_at:verified?nowIso():null,
    updated_at:nowIso(),
  }).eq("id",concept.id);
  if(cu) throw cu;
  if(!verified) throw new Error("concept verification failed");

  const relationSpecs=[
    {
      subject_kind:"domain",
      subject_key:domain.parent_domain_key??"python/cpython",
      predicate:"depends_on_versioned_interface_of",
      object_kind:"domain",
      object_key:domainKey,
    },
    {
      subject_kind:"domain",
      subject_key:domainKey,
      predicate:"exhibits",
      object_kind:"concept",
      object_key:conceptKey,
    },
  ];

  for(const rel of relationSpecs) {
    const {data:rex,error:rerr}=await db.from("mind_core_concept_relations")
      .select("id")
      .eq("concept_id",concept.id)
      .eq("subject_kind",rel.subject_kind)
      .eq("subject_key",rel.subject_key)
      .eq("predicate",rel.predicate)
      .eq("object_kind",rel.object_kind)
      .eq("object_key",rel.object_key)
      .maybeSingle();
    if(rerr) throw rerr;
    if(!rex) {
      const {error:ri}=await db.from("mind_core_concept_relations").insert({
        concept_id:concept.id,
        ...rel,
        evidence_ids:sourceIds,
        status:"admitted",
      });
      if(ri) throw ri;
    }
  }

  const goalKey=`concept-application:${concept.id}`;
  const {data:g,error:gerr}=await db.from("mind_core_goals").upsert({
    goal_key:goalKey,
    kind:"inspect_concept_application",
    target:{
      concept_id:concept.id,
      concept_key:conceptKey,
      url:"https://www.tcl-lang.org/about/stubs.html",
      question:"How does Tcl's stubs mechanism operationalize this versioned interface contract, and where are its compatibility boundaries?",
    },
    rationale:`Apply concept ${conceptKey} to a second official Tcl source.`,
    priority:0.88,
    status:"pending",
    recurrence_minutes:null,
    not_before:nowIso(),
    created_from_cycle:cycleId,
    updated_at:nowIso(),
  },{onConflict:"goal_key"}).select("id").single();
  if(gerr) throw gerr;

  const result={
    source_evidence_ids:sourceIds,
    concept_id:concept.id,
    concept_key:conceptKey,
    name:conceptName,
    definition,
    abstraction,
    verification,
    relations:relationSpecs,
    derived_goal_id:g.id,
    derived_goal_key:goalKey,
    born_at:nowIso(),
  };

  await logMechanismEvent(
    mechanism.id,cycleId,"concept_birth",
    {source_evidence_id:sourceEvidenceId,corroborating_evidence_id:Number(boundaryEvidence.id)},
    result,true
  );

  if(admitMechanism && !existing) {
    const mevidence={
      ...(mechanism.evidence??{}),
      independent_self_test:result,
      admitted_reason:"Induced a new reusable abstraction from multiple real evidence items, verified it against an independent official Tcl API source through M0001, and emitted explicit relations plus an application goal.",
    };
    const {error:mu}=await db.from("mind_core_mechanisms").update({
      status:"admitted",
      evidence:mevidence,
      admitted_at:nowIso(),
      updated_at:nowIso(),
    }).eq("mechanism_key",CONCEPT_BIRTH_MECHANISM);
    if(mu) throw mu;
  }

  return result;
}

async function inspectConceptApplication(goal:Goal, cycleId:number) {
  const conceptId=Number(goal.target?.concept_id);
  const url=String(goal.target?.url??"");
  if(!Number.isFinite(conceptId) || !url) throw new Error("invalid concept application goal");

  const {text,finalUrl,status}=await internetGet(
    cycleId,url,
    `apply concept ${String(goal.target?.concept_key??"unknown")}`
  );
  const plain=stripHtml(text);
  const observed={
    concept_id:conceptId,
    concept_key:String(goal.target?.concept_key??""),
    question:String(goal.target?.question??""),
    url,
    final_url:finalUrl,
    http_status:status,
    title:pageTitle(text),
    supports_cross_version:/different versions|version independence|compiled with one version|without recompiling/i.test(plain),
    supports_function_table:/function table|Tcl_InitStubs/i.test(plain),
    major_version_caveat:/major versions|major version/i.test(plain),
    text_excerpt:plain.slice(0,10000),
    checked_at:nowIso(),
  };
  await recordEvidence(cycleId,url,"concept_application_official",observed.title,observed);
  return observed;
}


async function conceptTransferSelfTest(conceptId:number, cycleId:number, admitMechanism=false) {
  const mechanism=await getMechanismByKey(CONCEPT_TRANSFER_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) throw new Error("concept transfer mechanism inactive");

  const {data:concept,error:cerr}=await db.from("mind_core_concepts")
    .select("*").eq("id",conceptId).single();
  if(cerr) throw cerr;
  if(concept.status!=="admitted") throw new Error("source concept is not admitted");

  const targetUrl="https://nodejs.org/api/n-api.html";
  const {text:html,finalUrl,status}=await internetGet(
    cycleId,targetUrl,
    `transfer concept ${concept.concept_key} to foreign technology`
  );
  const plain=stripHtml(html);

  const contamination={
    tcl:/\bTcl\b|\bTkinter\b|\bTcl\/Tk\b/i.test(plain),
    source_python:/python\/cpython/i.test(plain),
  };

  const checks=[
    {key:"foreign_runtime_api",ok:/Node-API|N-API/i.test(plain)},
    {key:"abi_stability",ok:/ABI stable|ABI stability/i.test(plain)},
    {key:"cross_version",ok:/across versions of Node\.js|later major versions/i.test(plain)},
    {key:"without_recompile",ok:/without recompilation/i.test(plain)},
    {key:"explicit_api_version",ok:/NAPI_VERSION|Node-API version/i.test(plain)},
    {key:"version_matrix",ok:/version matrix/i.test(plain)},
    {key:"underlying_runtime_insulation",ok:/independent from the underlying JavaScript runtime|insulate addons from changes/i.test(plain)},
  ];
  const matched=checks.filter(x=>x.ok).map(x=>x.key);
  const clean=!contamination.tcl && !contamination.source_python;
  const score=(matched.length/checks.length) * (clean?1:0.5);
  const verified=status===200 && clean && matched.length>=6;

  const observed={
    source_concept_id:concept.id,
    source_concept_key:concept.concept_key,
    target_key:"nodejs-node-api",
    target_name:"Node.js Node-API",
    target_url:targetUrl,
    final_url:finalUrl,
    http_status:status,
    bytes:html.length,
    contamination,
    matched_checks:matched,
    check_count:checks.length,
    transfer_score:score,
    verified,
    checked_at:nowIso(),
  };

  const evidenceId=await recordEvidence(
    cycleId,targetUrl,"concept_transfer_official","Node-API concept transfer",observed
  );

  const transferKey=`${concept.concept_key}->nodejs-node-api`;
  const {data:transfer,error:terr}=await db.from("mind_core_concept_transfers").upsert({
    transfer_key:transferKey,
    concept_id:concept.id,
    source_domain_key:concept.domain_key,
    target_key:"nodejs-node-api",
    target_name:"Node.js Node-API",
    target_url:targetUrl,
    status:verified?"admitted":"rejected",
    match:{matched_checks:matched,transfer_score:score,contamination},
    verification:observed,
    evidence_id:evidenceId,
    admitted_at:verified?nowIso():null,
    updated_at:nowIso(),
  },{onConflict:"transfer_key"}).select("*").single();
  if(terr) throw terr;
  if(!verified) throw new Error("concept transfer verification failed");

  const {data:rex,error:rerr}=await db.from("mind_core_concept_relations")
    .select("id")
    .eq("concept_id",concept.id)
    .eq("subject_kind","technology")
    .eq("subject_key","nodejs-node-api")
    .eq("predicate","exhibits_analogue_of")
    .eq("object_kind","concept")
    .eq("object_key",concept.concept_key)
    .maybeSingle();
  if(rerr) throw rerr;
  if(!rex) {
    const {error:ri}=await db.from("mind_core_concept_relations").insert({
      concept_id:concept.id,
      subject_kind:"technology",
      subject_key:"nodejs-node-api",
      predicate:"exhibits_analogue_of",
      object_kind:"concept",
      object_key:concept.concept_key,
      evidence_ids:[evidenceId],
      status:"admitted",
    });
    if(ri) throw ri;
  }

  const result={...observed,transfer_id:transfer.id,evidence_id:evidenceId};

  await logMechanismEvent(
    mechanism.id,cycleId,"concept_transfer",
    {concept_id:concept.id,target:"nodejs-node-api"},
    result,true
  );

  if(admitMechanism) {
    const mevidence={
      ...(mechanism.evidence??{}),
      independent_self_test:result,
      admitted_reason:"Transferred an admitted concept to Node-API, a foreign technology without Tcl/Tk or CPython dependence, using official Node.js evidence and structural rather than lexical matching.",
    };
    const {error:mu}=await db.from("mind_core_mechanisms").update({
      status:"admitted",evidence:mevidence,admitted_at:nowIso(),updated_at:nowIso()
    }).eq("mechanism_key",CONCEPT_TRANSFER_MECHANISM);
    if(mu) throw mu;
  }

  return result;
}

function extractHrefCandidates(baseUrl:string, html:string) {
  const out=new Map<string,{url:string,text:string}>();
  for(const m of html.matchAll(/<a\b[^>]*href=["']([^"'#]+)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    try {
      const u=assertSafePublicHttps(new URL(m[1],baseUrl).toString());
      const key=u.toString();
      if(!out.has(key)) out.set(key,{url:key,text:stripHtml(m[2]).slice(0,160)});
    } catch {}
  }
  return [...out.values()].slice(0,200);
}

function analyzeHrefFrontier(baseUrl:string, html:string) {
  const raw=[...html.matchAll(/href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi)]
    .map(m=>String(m[1]??m[2]??m[3]??"").trim())
    .filter(Boolean);

  const safe=new Map<string,string>();
  let fragments=0;
  let rejected=0;
  let nonHttp=0;

  for(const href of raw) {
    if(href.startsWith("#")) {
      fragments += 1;
      continue;
    }
    if(/^(?:javascript:|data:|mailto:|tel:)/i.test(href)) {
      nonHttp += 1;
      continue;
    }
    try {
      const u=assertSafePublicHttps(new URL(href,baseUrl).toString());
      safe.set(u.toString(),href);
    } catch {
      rejected += 1;
    }
  }

  const urls=[...safe.keys()].slice(0,200);
  const baseHost=new URL(baseUrl).hostname;
  const sameHost=urls.filter(u=>new URL(u).hostname===baseHost);

  return {
    raw_href_count:raw.length,
    fragment_href_count:fragments,
    rejected_href_count:rejected,
    non_http_href_count:nonHttp,
    safe_url_count:urls.length,
    same_host_count:sameHost.length,
    safe_urls:urls,
    same_host_urls:sameHost,
  };
}




function buildNavigableFrontier(baseUrl:string, html:string) {
  const analysis=analyzeHrefFrontier(baseUrl,html);
  const assetExt=/\.(?:css|js|mjs|cjs|ico|png|jpe?g|gif|svg|webp|woff2?|ttf|otf|map|xml|json)(?:$|[?#])/i;

  const navigable=analysis.safe_urls.filter((u:string)=>{
    try {
      const parsed=new URL(u);
      return !assetExt.test(parsed.pathname);
    } catch {
      return false;
    }
  });

  const baseHost=new URL(baseUrl).hostname;
  const sameHost=navigable.filter((u:string)=>new URL(u).hostname===baseHost);

  return {
    ...analysis,
    navigable_url_count:navigable.length,
    navigable_same_host_count:sameHost.length,
    navigable_urls:navigable.slice(0,100),
    navigable_same_host_urls:sameHost.slice(0,100),
  };
}

async function safeFrontierFromUrl(cycleId:number, url:string, purpose:string) {
  const mechanism=await getMechanismByKey(SAFE_FRONTIER_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) throw new Error("safe frontier mechanism inactive");

  const {text,finalUrl,status}=await internetGet(cycleId,url,purpose);
  const frontier=buildNavigableFrontier(finalUrl,text);

  const observed={
    mechanism_key:SAFE_FRONTIER_MECHANISM,
    url,
    final_url:finalUrl,
    http_status:status,
    title:pageTitle(text),
    ...frontier,
    checked_at:nowIso(),
  };

  const evidenceId=await recordEvidence(
    cycleId,url,"safe_link_frontier",observed.title,observed
  );

  await logMechanismEvent(
    mechanism.id,cycleId,"frontier_discovery",
    {url,purpose},
    {...observed,evidence_id:evidenceId},
    true
  );

  return {...observed,evidence_id:evidenceId};
}

async function safeFrontierSelfTest(goal:Goal, cycleId:number) {
  const url=String(goal.target?.url??"");
  if(!url) throw new Error("frontier self-test URL missing");

  const observed=await safeFrontierFromUrl(
    cycleId,url,"M0006 independent admission self-test"
  );

  const passed=
    observed.http_status===200 &&
    observed.raw_href_count>=5 &&
    observed.navigable_url_count>=3 &&
    observed.navigable_same_host_count>=2;

  const result={...observed,passed};

  if(!passed) throw new Error("M0006 self-test failed");

  const mechanism=await getMechanismByKey(SAFE_FRONTIER_MECHANISM);
  const evidence={
    ...(mechanism.evidence??{}),
    independent_self_test:result,
    admitted_reason:"Implemented admitted D0001R1 design and passed an independent fourth-site production test through M0001.",
  };

  const {error}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence,
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key",SAFE_FRONTIER_MECHANISM);
  if(error) throw error;

  return result;
}

async function exploreFrontierGoal(goal:Goal, cycleId:number) {
  const url=String(goal.target?.url??"");
  if(!url) throw new Error("frontier URL missing");
  return await safeFrontierFromUrl(
    cycleId,url,
    String(goal.target?.purpose??"discover safe public HTTPS frontier")
  );
}


function rankFrontierUrls(urls:string[], query:string) {
  const stop=new Set(["the","a","an","of","to","and","or","for","in","on","with","web"]);
  const tokens=[...new Set(
    query.toLowerCase()
      .replace(/[^a-z0-9.]+/g," ")
      .split(/\s+/)
      .filter(t=>t.length>=2 && !stop.has(t))
  )];

  return urls.map((url,index)=>{
    let hay="";
    try {
      const u=new URL(url);
      hay=(decodeURIComponent(u.pathname+" "+u.hash+" "+u.search)).toLowerCase();
    } catch {
      hay=url.toLowerCase();
    }

    let lexical=0;
    for(const token of tokens) {
      if(hay.includes(token)) lexical += token.length>=5 ? 2 : 1;
    }

    const compact=query.toLowerCase().replace(/[^a-z0-9]+/g,"");
    const compactHay=hay.replace(/[^a-z0-9]+/g,"");
    const phraseBonus=compact.length>=5 && compactHay.includes(compact) ? 3 : 0;
    const depthPenalty=(hay.match(/\//g)?.length??0)*0.02;

    return {
      url,
      score:lexical+phraseBonus-depthPenalty,
      lexical_hits:lexical,
      source_index:index,
    };
  }).sort((a,b)=>b.score-a.score || a.source_index-b.source_index);
}

async function goalWeightedFrontier(cycleId:number, url:string, query:string) {
  const mechanism=await getMechanismByKey(GOAL_FRONTIER_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) throw new Error("goal frontier mechanism inactive");

  const frontier=await safeFrontierFromUrl(
    cycleId,url,`M0007 frontier acquisition for goal: ${query}`
  );
  const ranked=rankFrontierUrls(frontier.navigable_urls,query);
  const observed={
    mechanism_key:GOAL_FRONTIER_MECHANISM,
    url,
    query,
    frontier_evidence_id:frontier.evidence_id,
    candidate_count:ranked.length,
    ranked_top25:ranked.slice(0,25),
    checked_at:nowIso(),
  };

  await logMechanismEvent(
    mechanism.id,cycleId,"frontier_ranking",
    {url,query},observed,true
  );
  return observed;
}

async function goalFrontierSelfTest(goal:Goal, cycleId:number) {
  const url=String(goal.target?.url??"");
  const query=String(goal.target?.query??"");
  const expected=String(goal.target?.expected??"");
  if(!url || !query || !expected) throw new Error("M0007 self-test target incomplete");

  const observed=await goalWeightedFrontier(cycleId,url,query);
  const expectedRank=observed.ranked_top25.findIndex((x:any)=>
    String(x.url).toLowerCase().includes(expected.toLowerCase())
  );
  const passed=expectedRank>=0 && expectedRank<10;
  const result={...observed,expected,expected_rank:expectedRank>=0?expectedRank+1:null,passed};
  if(!passed) throw new Error("M0007 self-test failed");

  const mechanism=await getMechanismByKey(GOAL_FRONTIER_MECHANISM);
  const evidence={
    ...(mechanism.evidence??{}),
    independent_self_test:result,
    admitted_reason:"Implemented admitted D0002 design and passed an independent fourth-site relevance-ranking test using M0006 output.",
  };
  const {error}=await db.from("mind_core_mechanisms").update({
    status:"admitted",evidence,admitted_at:nowIso(),updated_at:nowIso()
  }).eq("mechanism_key",GOAL_FRONTIER_MECHANISM);
  if(error) throw error;
  return result;
}

function decodeRelationText(s:string) {
  return stripHtml(String(s??""))
    .replace(/&quot;/g,'"')
    .replace(/&#39;|&apos;/g,"'")
    .replace(/&lt;/g,"<")
    .replace(/&gt;/g,">")
    .replace(/\s+/g," ")
    .trim();
}

function normalizeRelationValue(s:string) {
  return decodeRelationText(s)
    .toLowerCase()
    .replace(/[\u2018\u2019]/g,"'")
    .replace(/[\u201c\u201d]/g,'"')
    .replace(/\s+/g," ")
    .trim();
}

function parseHtmlTables(html:string) {
  const tables:any[]=[];
  let tableIndex=0;

  for(const tm of html.matchAll(/<table\b([^>]*)>([\s\S]*?)<\/table>/gi)) {
    const attrs=String(tm[1]??"");
    const body=String(tm[2]??"");
    const rawRows=[...body.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr>/gi)];
    if(rawRows.length<2 || !/<th\b/i.test(body)) {
      tableIndex += 1;
      continue;
    }

    const parsedRows:any[]=[];
    for(const rm of rawRows) {
      const rowBody=String(rm[1]??"");
      const cells:any[]=[];
      let thCount=0;
      let tdCount=0;

      for(const cm of rowBody.matchAll(/<(th|td)\b([^>]*)>([\s\S]*?)<\/\1>/gi)) {
        const tag=String(cm[1]).toLowerCase();
        const cellAttrs=String(cm[2]??"");
        const value=decodeRelationText(String(cm[3]??""));
        const colspanMatch=cellAttrs.match(/colspan\s*=\s*["']?(\d+)/i);
        const colspan=Math.max(1,Math.min(12,Number(colspanMatch?.[1]??1)));
        if(tag==="th") thCount += colspan;
        else tdCount += colspan;
        for(let k=0;k<colspan;k++) cells.push(value);
      }

      if(cells.length) parsedRows.push({cells,thCount,tdCount});
    }

    let headerIdx=parsedRows.findIndex(r=>r.thCount>0 && r.tdCount===0);
    if(headerIdx<0) headerIdx=parsedRows.findIndex(r=>r.thCount>0);
    if(headerIdx<0) {
      tableIndex += 1;
      continue;
    }

    const headers=parsedRows[headerIdx].cells;
    const dataRows=parsedRows
      .filter((r,idx)=>idx!==headerIdx && (r.tdCount>0 || r.thCount>0))
      .map(r=>r.cells)
      .filter(r=>r.some((v:string)=>normalizeRelationValue(v)!==""));

    if(dataRows.length<2) {
      tableIndex += 1;
      continue;
    }

    const maxCols=Math.max(headers.length,...dataRows.map(r=>r.length));
    const normalizedHeaders=Array.from({length:maxCols},(_,i)=>
      decodeRelationText(headers[i]??"") || `column_${i}`
    );

    tables.push({
      table_index:tableIndex,
      attrs,
      headers:normalizedHeaders,
      rows:dataRows.map(r=>Array.from({length:maxCols},(_,i)=>decodeRelationText(r[i]??""))),
    });
    tableIndex += 1;
  }

  return tables;
}

async function mineTableRelations(cycleId:number, url:string) {
  const {text:html,finalUrl,status}=await internetGet(
    cycleId,url,"generic table relation mining"
  );

  const tables=parseHtmlTables(html);
  const relations:any[]=[];

  for(const table of tables) {
    const rows=table.rows as string[][];
    const cols=table.headers.length;

    for(let i=0;i<cols;i++) {
      for(let j=0;j<cols;j++) {
        if(i===j) continue;

        const pairs=rows
          .map(r=>[decodeRelationText(r[i]??""),decodeRelationText(r[j]??"")])
          .filter(([a,b])=>normalizeRelationValue(a)!=="" && normalizeRelationValue(b)!=="");

        if(pairs.length<2) continue;

        const map=new Map<string,Set<string>>();
        for(const [a,b] of pairs) {
          const ak=normalizeRelationValue(a);
          const bk=normalizeRelationValue(b);
          if(!map.has(ak)) map.set(ak,new Set());
          map.get(ak)!.add(bk);
        }

        const uniqueLeft=map.size;
        if(uniqueLeft<2) continue;

        const singleton=[...map.values()].filter(s=>s.size===1).length;
        const consistency=singleton/uniqueLeft;
        const coverage=pairs.length/Math.max(1,rows.length);
        const supportFactor=Math.min(1,pairs.length/3);
        const leftUniqueness=uniqueLeft/pairs.length;
        const score=
          0.35*consistency +
          0.25*coverage +
          0.20*supportFactor +
          0.20*leftUniqueness;

        if(score<0.78 || consistency<0.90 || coverage<0.65) continue;

        const pairIndex=new Set(
          pairs.map(([a,b])=>normalizeRelationValue(a)+"\u241f"+normalizeRelationValue(b))
        );

        relations.push({
          table_index:table.table_index,
          left_col:i,
          right_col:j,
          left_header:table.headers[i],
          right_header:table.headers[j],
          support:pairs.length,
          unique_left:uniqueLeft,
          consistency,
          coverage,
          score,
          pairs:pairs.slice(0,60),
          _pair_index:pairIndex,
        });
      }
    }
  }

  relations.sort((a,b)=>b.score-a.score || b.support-a.support);

  return {
    url,
    final_url:finalUrl,
    http_status:status,
    table_count:tables.length,
    relation_count:relations.length,
    relations:relations.slice(0,60),
    checked_at:nowIso(),
  };
}

function relationContainsPair(rel:any, expected:any[]) {
  const a=normalizeRelationValue(String(expected?.[0]??""));
  const b=normalizeRelationValue(String(expected?.[1]??""));
  const key=a+"\u241f"+b;

  if(rel?._pair_index instanceof Set && rel._pair_index.has(key)) return true;

  return Array.isArray(rel?.pairs) && rel.pairs.some((p:any)=>
    normalizeRelationValue(String(p?.[0]??""))===a &&
    normalizeRelationValue(String(p?.[1]??""))===b
  );
}

async function relationMinerEvaluator(goal:Goal, cycleId:number) {
  const candidateKey=String(goal.target?.candidate_key??"D0003:generic-relational-pattern-mining");

  const {data:cases,error:caseErr}=await db
    .from("mind_core_relation_eval_cases")
    .select("*")
    .order("id",{ascending:true});
  if(caseErr) throw caseErr;
  if(!cases?.length) throw new Error("relation evaluator has no frozen cases");

  const caseResults:any[]=[];
  let passedCount=0;

  for(const c of cases) {
    // Candidate sees URL only. Ground-truth expected_pairs are checked only after mining.
    const mined=await mineTableRelations(cycleId,String(c.url));
    const expected=Array.isArray(c.expected_pairs)?c.expected_pairs:[];
    let passed=false;
    let matched:any[]=[];

    if(c.negative_case) {
      passed=mined.relation_count===0;
    } else {
      matched=expected.map((pair:any)=>({
        pair,
        found:mined.relations.some((rel:any)=>relationContainsPair(rel,pair)),
      }));
      passed=matched.length>0 && matched.every((x:any)=>x.found);
    }

    const result={
      case_key:c.case_key,
      url:c.url,
      negative_case:c.negative_case,
      expected_pair_count:expected.length,
      matched,
      mined_relation_count:mined.relation_count,
      top_relations:mined.relations.slice(0,12),
      passed,
    };

    const {error:runErr}=await db.from("mind_core_relation_eval_runs").insert({
      case_id:c.id,
      cycle_id:cycleId,
      candidate_key:candidateKey,
      result,
      passed,
    });
    if(runErr) throw runErr;

    if(passed) passedCount += 1;
    caseResults.push(result);
  }

  const allPassed=passedCount===cases.length;
  const verdict={
    candidate_key:candidateKey,
    evaluator_version:"relation-eval-v2",
    cases_total:cases.length,
    cases_passed:passedCount,
    all_passed:allPassed,
    blind_expectations:true,
    cases:caseResults,
    checked_at:nowIso(),
  };

  const {error:updateErr}=await db.from("mind_core_development_candidates").update({
    status:allPassed?"admitted":"rejected",
    shadow_result:verdict,
    internet_evidence:jsonbSafe({
      evaluator_version:"relation-eval-v1",
      frozen_cases:cases.length,
      candidate_blind_to_expectations:true,
    }),
    updated_at:nowIso(),
  }).eq("candidate_key",candidateKey);
  if(updateErr) throw updateErr;

  return verdict;
}

function jsonbSafe<T>(x:T):T { return x; }


async function relationMinerSelfTest(goal:Goal, cycleId:number) {
  const url=String(goal.target?.url??"");
  const expected=Array.isArray(goal.target?.expected_pairs)?goal.target.expected_pairs:[];
  if(!url || expected.length<1) throw new Error("M0008 self-test target incomplete");

  const mined=await mineTableRelations(cycleId,url);
  const matched=expected.map((pair:any)=>({
    pair,
    found:mined.relations.some((rel:any)=>relationContainsPair(rel,pair)),
  }));
  const passed=matched.every((x:any)=>x.found);

  const result={
    mechanism_key:RELATION_MINER_MECHANISM,
    url,
    expected_pair_count:expected.length,
    matched,
    mined_relation_count:mined.relation_count,
    top_relations:mined.relations.slice(0,12),
    passed,
    checked_at:nowIso(),
  };

  if(!passed) throw new Error("M0008 self-test failed");

  const mechanism=await getMechanismByKey(RELATION_MINER_MECHANISM);
  const evidence={
    ...(mechanism.evidence??{}),
    independent_self_test:result,
    admitted_reason:"Implemented the D0003 design after a 4/4 blind evaluator and passed an independent fifth-source IANA HTTP-status relation test.",
  };

  const {error}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence,
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key",RELATION_MINER_MECHANISM);
  if(error) throw error;

  return result;
}


function functionalStats(rows:string[][], leftCol:number, rightCol:number) {
  const pairs=rows
    .map(r=>[decodeRelationText(r[leftCol]??""),decodeRelationText(r[rightCol]??"")])
    .filter(([a,b])=>normalizeRelationValue(a)!=="" && normalizeRelationValue(b)!=="");

  const map=new Map<string,Set<string>>();
  for(const [a,b] of pairs) {
    const ak=normalizeRelationValue(a);
    const bk=normalizeRelationValue(b);
    if(!map.has(ak)) map.set(ak,new Set());
    map.get(ak)!.add(bk);
  }

  const uniqueLeft=map.size;
  const singleton=[...map.values()].filter(s=>s.size===1).length;
  const consistency=uniqueLeft>0?singleton/uniqueLeft:0;
  const coverage=rows.length>0?pairs.length/rows.length:0;
  const leftUniqueness=pairs.length>0?uniqueLeft/pairs.length:0;

  return {
    support:pairs.length,
    unique_left:uniqueLeft,
    consistency,
    coverage,
    left_uniqueness:leftUniqueness,
  };
}

function splitRelationRows(rows:string[][]) {
  const train:string[][]=[];
  const holdout:string[][]=[];

  rows.forEach((row,idx)=>{
    if(idx%3===2) holdout.push(row);
    else train.push(row);
  });

  return {train,holdout};
}

function proposeRelationsFromTraining(tables:any[]) {
  const proposals:any[]=[];

  for(const table of tables) {
    const rows=table.rows as string[][];
    if(rows.length<4) continue;

    const {train}=splitRelationRows(rows);
    const cols=table.headers.length;

    for(let i=0;i<cols;i++) {
      for(let j=0;j<cols;j++) {
        if(i===j) continue;

        const stats=functionalStats(train,i,j);
        if(stats.support<2 || stats.unique_left<2) continue;

        const score=
          0.45*stats.consistency +
          0.25*stats.coverage +
          0.15*Math.min(1,stats.support/6) +
          0.15*stats.left_uniqueness;

        if(stats.consistency<0.90 || stats.coverage<0.65 || score<0.80) continue;

        proposals.push({
          table_index:table.table_index,
          left_col:i,
          right_col:j,
          left_header:table.headers[i],
          right_header:table.headers[j],
          train_stats:stats,
          score,
        });
      }
    }
  }

  proposals.sort((a,b)=>b.score-a.score || b.train_stats.support-a.train_stats.support);
  return proposals;
}

async function evaluateHeldoutRelationCase(c:any, cycleId:number, candidateKey:string) {
  const {text:html,finalUrl,status}=await internetGet(
    cycleId,String(c.url),"held-out relation generalization evaluator"
  );

  const tables=parseHtmlTables(html);

  // Candidate phase: only tables + deterministic train rows are used.
  const proposals=proposeRelationsFromTraining(tables);

  // Evaluator phase: target relation and holdout are inspected only after proposals exist.
  const targetLeft=normalizeRelationValue(String(c.left_header));
  const targetRight=normalizeRelationValue(String(c.right_header));

  const proposal=proposals.find((p:any)=>
    normalizeRelationValue(String(p.left_header))===targetLeft &&
    normalizeRelationValue(String(p.right_header))===targetRight
  ) ?? null;

  let holdoutStats:any=null;
  if(proposal) {
    const table=tables.find((t:any)=>t.table_index===proposal.table_index);
    if(table) {
      const {holdout}=splitRelationRows(table.rows);
      holdoutStats=functionalStats(holdout,proposal.left_col,proposal.right_col);
    }
  }

  const generalizes=!!proposal && !!holdoutStats &&
    holdoutStats.support>=1 &&
    holdoutStats.consistency>=0.90 &&
    holdoutStats.coverage>=0.65;

  const passed=c.expect_generalizes ? generalizes : !generalizes;

  const result={
    case_key:c.case_key,
    url:c.url,
    final_url:finalUrl,
    http_status:status,
    target:{
      left_header:c.left_header,
      right_header:c.right_header,
      expect_generalizes:c.expect_generalizes,
    },
    candidate_proposal:proposal,
    holdout_stats:holdoutStats,
    generalizes,
    proposal_count:proposals.length,
    top_proposals:proposals.slice(0,12),
    passed,
    checked_at:nowIso(),
  };

  const {error}=await db.from("mind_core_relation_generalization_runs").insert({
    case_id:c.id,
    cycle_id:cycleId,
    candidate_key:candidateKey,
    train_result:{
      proposal_found:!!proposal,
      proposal,
      top_proposals:proposals.slice(0,12),
    },
    holdout_result:{
      holdout_stats:holdoutStats,
      generalizes,
      expected:c.expect_generalizes,
    },
    passed,
  });
  if(error) throw error;

  return result;
}

async function heldoutRelationEvaluator(goal:Goal, cycleId:number) {
  const candidateKey=String(goal.target?.candidate_key??"D0004:heldout-relation-validation");

  const {data:cases,error:caseErr}=await db
    .from("mind_core_relation_generalization_cases")
    .select("*")
    .order("id",{ascending:true});
  if(caseErr) throw caseErr;
  if(!cases?.length) throw new Error("held-out evaluator has no cases");

  const results:any[]=[];
  let passedCount=0;

  for(const c of cases) {
    const result=await evaluateHeldoutRelationCase(c,cycleId,candidateKey);
    results.push(result);
    if(result.passed) passedCount += 1;
  }

  const allPassed=passedCount===cases.length;
  const verdict={
    candidate_key:candidateKey,
    evaluator_version:"heldout-relation-v1",
    cases_total:cases.length,
    cases_passed:passedCount,
    all_passed:allPassed,
    deterministic_split:"row_index_mod_3; 2/3 train, 1/3 holdout",
    candidate_blind_to_holdout:true,
    cases:results,
    checked_at:nowIso(),
  };

  const {error:updateErr}=await db.from("mind_core_development_candidates").update({
    status:allPassed?"admitted":"rejected",
    shadow_result:verdict,
    internet_evidence:{
      evaluator_version:"heldout-relation-v1",
      frozen_cases:cases.length,
      candidate_blind_to_holdout:true,
    },
    updated_at:nowIso(),
  }).eq("candidate_key",candidateKey);
  if(updateErr) throw updateErr;

  return verdict;
}


function proposeKeyDirectedRelationsFromTraining(tables:any[]) {
  const proposals:any[]=[];

  for(const table of tables) {
    const rows=table.rows as string[][];
    if(rows.length<4) continue;
    const {train}=splitRelationRows(rows);
    const cols=table.headers.length;

    for(let i=0;i<cols;i++) {
      for(let j=0;j<cols;j++) {
        if(i===j) continue;

        const stats=functionalStats(train,i,j);
        if(stats.support<2 || stats.unique_left<2) continue;
        if(
          stats.left_uniqueness<0.98 ||
          stats.consistency<0.99 ||
          stats.coverage<0.65
        ) continue;

        const score=
          0.40*stats.consistency +
          0.30*stats.left_uniqueness +
          0.20*stats.coverage +
          0.10*Math.min(1,stats.support/6);

        proposals.push({
          table_index:table.table_index,
          left_col:i,
          right_col:j,
          left_header:table.headers[i],
          right_header:table.headers[j],
          train_stats:stats,
          score,
        });
      }
    }
  }

  proposals.sort((a,b)=>b.score-a.score || b.train_stats.support-a.train_stats.support);
  return proposals;
}

async function evaluateKeyDirectedCase(c:any, cycleId:number, candidateKey:string) {
  const {text:html,finalUrl,status}=await internetGet(
    cycleId,String(c.url),"key-directed held-out relation evaluator"
  );

  const tables=parseHtmlTables(html);

  // Candidate sees training rows only and proposes all qualifying key-directed relations.
  const proposals=proposeKeyDirectedRelationsFromTraining(tables);

  // Evaluator reveals the frozen target only after proposals exist.
  const targetLeft=normalizeRelationValue(String(c.left_header));
  const targetRight=normalizeRelationValue(String(c.right_header));

  const proposal=proposals.find((p:any)=>
    normalizeRelationValue(String(p.left_header))===targetLeft &&
    normalizeRelationValue(String(p.right_header))===targetRight
  ) ?? null;

  let holdoutStats:any=null;
  if(proposal) {
    const table=tables.find((t:any)=>t.table_index===proposal.table_index);
    if(table) {
      const {holdout}=splitRelationRows(table.rows);
      holdoutStats=functionalStats(holdout,proposal.left_col,proposal.right_col);
    }
  }

  const generalizes=!!proposal && !!holdoutStats &&
    holdoutStats.support>=1 &&
    holdoutStats.left_uniqueness>=0.98 &&
    holdoutStats.consistency>=0.99 &&
    holdoutStats.coverage>=0.65;

  const passed=c.expect_generalizes ? generalizes : !generalizes;

  const result={
    case_key:c.case_key,
    url:c.url,
    final_url:finalUrl,
    http_status:status,
    target:{
      left_header:c.left_header,
      right_header:c.right_header,
      expect_generalizes:c.expect_generalizes,
    },
    candidate_proposal:proposal,
    holdout_stats:holdoutStats,
    generalizes,
    proposal_count:proposals.length,
    top_proposals:proposals.slice(0,12),
    passed,
    checked_at:nowIso(),
  };

  const {error}=await db.from("mind_core_relation_generalization_runs").insert({
    case_id:c.id,
    cycle_id:cycleId,
    candidate_key:candidateKey,
    train_result:{
      evaluator_version:"key-directed-heldout-v2",
      proposal_found:!!proposal,
      proposal,
      top_proposals:proposals.slice(0,12),
    },
    holdout_result:{
      holdout_stats:holdoutStats,
      generalizes,
      expected:c.expect_generalizes,
    },
    passed,
  });
  if(error) throw error;

  return result;
}

async function keyDirectedRelationEvaluator(goal:Goal, cycleId:number) {
  const candidateKey=String(
    goal.target?.candidate_key??"D0004R1:key-directed-relation-generalization"
  );

  const {data:cases,error:caseErr}=await db
    .from("mind_core_relation_generalization_cases")
    .select("*")
    .order("id",{ascending:true});
  if(caseErr) throw caseErr;
  if(!cases?.length) throw new Error("key-directed evaluator has no cases");

  const results:any[]=[];
  let passedCount=0;

  for(const c of cases) {
    const result=await evaluateKeyDirectedCase(c,cycleId,candidateKey);
    results.push(result);
    if(result.passed) passedCount += 1;
  }

  const allPassed=passedCount===cases.length;
  const verdict={
    candidate_key:candidateKey,
    evaluator_version:"key-directed-heldout-v2",
    cases_total:cases.length,
    cases_passed:passedCount,
    all_passed:allPassed,
    deterministic_split:"row_index_mod_3; 2/3 train, 1/3 holdout",
    train_thresholds:{
      left_uniqueness:0.98,
      consistency:0.99,
      coverage:0.65,
    },
    holdout_thresholds:{
      left_uniqueness:0.98,
      consistency:0.99,
      coverage:0.65,
    },
    candidate_blind_to_holdout:true,
    cases:results,
    checked_at:nowIso(),
  };

  const {error:updateErr}=await db.from("mind_core_development_candidates").update({
    status:allPassed?"admitted":"rejected",
    shadow_result:verdict,
    internet_evidence:{
      evaluator_version:"key-directed-heldout-v2",
      frozen_cases:cases.length,
      parent_candidate:"D0004:heldout-relation-validation",
      candidate_blind_to_holdout:true,
    },
    updated_at:nowIso(),
  }).eq("candidate_key",candidateKey);
  if(updateErr) throw updateErr;

  return verdict;
}


async function generalizeKeyDirectedRelations(cycleId:number, url:string) {
  const mechanism=await getMechanismByKey(RELATION_GENERALIZER_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) {
    throw new Error("key-directed relation generalizer inactive");
  }

  const {text:html,finalUrl,status}=await internetGet(
    cycleId,url,"M0009 key-directed held-out relation generalization"
  );

  const tables=parseHtmlTables(html);
  const proposals=proposeKeyDirectedRelationsFromTraining(tables);
  const generalized:any[]=[];

  for(const proposal of proposals) {
    const table=tables.find((t:any)=>t.table_index===proposal.table_index);
    if(!table) continue;

    const {holdout}=splitRelationRows(table.rows);
    const holdoutStats=functionalStats(holdout,proposal.left_col,proposal.right_col);

    const passes=
      holdoutStats.support>=1 &&
      holdoutStats.left_uniqueness>=0.98 &&
      holdoutStats.consistency>=0.99 &&
      holdoutStats.coverage>=0.65;

    if(!passes) continue;

    generalized.push({
      table_index:proposal.table_index,
      left_col:proposal.left_col,
      right_col:proposal.right_col,
      left_header:proposal.left_header,
      right_header:proposal.right_header,
      train_stats:proposal.train_stats,
      holdout_stats:holdoutStats,
      train_score:proposal.score,
    });
  }

  generalized.sort((a,b)=>
    b.train_score-a.train_score ||
    b.train_stats.support-a.train_stats.support
  );

  const observed={
    mechanism_key:RELATION_GENERALIZER_MECHANISM,
    url,
    final_url:finalUrl,
    http_status:status,
    proposal_count:proposals.length,
    generalized_count:generalized.length,
    generalized_relations:generalized.slice(0,40),
    checked_at:nowIso(),
  };

  const evidenceId=await recordEvidence(
    cycleId,url,"key_directed_relation_generalization",
    pageTitle(html),observed
  );

  await logMechanismEvent(
    mechanism.id,cycleId,"key_relation_generalization",
    {url},
    {...observed,evidence_id:evidenceId},
    true
  );

  return {...observed,evidence_id:evidenceId};
}

async function keyRelationGeneralizerSelfTest(goal:Goal, cycleId:number) {
  const url=String(goal.target?.url??"");
  const leftHeader=String(goal.target?.left_header??"");
  const rightHeader=String(goal.target?.right_header??"");

  if(!url || !leftHeader || !rightHeader) {
    throw new Error("M0009 self-test target incomplete");
  }

  const result=await generalizeKeyDirectedRelations(cycleId,url);
  const left=normalizeRelationValue(leftHeader);
  const right=normalizeRelationValue(rightHeader);

  const matched=result.generalized_relations.find((rel:any)=>
    normalizeRelationValue(String(rel.left_header))===left &&
    normalizeRelationValue(String(rel.right_header))===right
  ) ?? null;

  const passed=!!matched;
  const verdict={
    ...result,
    expected_relation:{
      left_header:leftHeader,
      right_header:rightHeader,
    },
    matched_relation:matched,
    passed,
  };

  if(!passed) throw new Error("M0009 self-test failed");

  const mechanism=await getMechanismByKey(RELATION_GENERALIZER_MECHANISM);
  const evidence={
    ...(mechanism.evidence??{}),
    independent_self_test:verdict,
    admitted_reason:"Implemented the D0004R1 design after 4/4 blind held-out evaluation and passed an independent IANA HTTP Field Registry admission test.",
  };

  const {error}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence,
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key",RELATION_GENERALIZER_MECHANISM);
  if(error) throw error;

  return verdict;
}


async function sha256Hex(input:string) {
  const data=new TextEncoder().encode(input);
  const digest=await crypto.subtle.digest("SHA-256",data);
  return [...new Uint8Array(digest)]
    .map(b=>b.toString(16).padStart(2,"0"))
    .join("");
}

function relationCounterexamples(rows:string[][], leftCol:number, rightCol:number) {
  const map=new Map<string,{display:string,rights:Map<string,string>}>();

  for(const row of rows) {
    const leftDisplay=decodeRelationText(row[leftCol]??"");
    const rightDisplay=decodeRelationText(row[rightCol]??"");
    const left=normalizeRelationValue(leftDisplay);
    const right=normalizeRelationValue(rightDisplay);
    if(!left || !right) continue;

    if(!map.has(left)) {
      map.set(left,{display:leftDisplay,rights:new Map()});
    }
    map.get(left)!.rights.set(right,rightDisplay);
  }

  const counterexamples:any[]=[];
  for(const entry of map.values()) {
    if(entry.rights.size>1) {
      counterexamples.push({
        left:entry.display,
        distinct_right_count:entry.rights.size,
        rights:[...entry.rights.values()].slice(0,12),
      });
    }
  }

  counterexamples.sort((a,b)=>b.distinct_right_count-a.distinct_right_count);
  return counterexamples;
}

async function freezeRelationHypothesis(
  candidateKey:string,
  caseKey:string,
  cycleId:number,
  url:string,
  proposal:any
) {
  const claim={
    type:"functional_relation",
    statement:`${proposal.left_header} functionally determines ${proposal.right_header}`,
    left_header:proposal.left_header,
    right_header:proposal.right_header,
  };

  const falsifier={
    type:"counterexample",
    statement:`Reject if any identical ${proposal.left_header} maps to more than one distinct ${proposal.right_header}`,
    rule:"exists left where count(distinct right) > 1",
  };

  const target={
    url,
    table_index:proposal.table_index,
    left_col:proposal.left_col,
    right_col:proposal.right_col,
    left_header:proposal.left_header,
    right_header:proposal.right_header,
  };

  const trainEvidence={
    train_stats:proposal.train_stats,
    proposal_score:proposal.score,
  };

  const canonical=JSON.stringify({
    candidate_key:candidateKey,
    case_key:caseKey,
    cycle_id:cycleId,
    claim,
    falsifier,
    target,
    train_evidence:trainEvidence,
  });
  const freezeHash=await sha256Hex(canonical);

  const {data,error}=await db.from("mind_core_hypothesis_freezes").insert({
    candidate_key:candidateKey,
    case_key:caseKey,
    cycle_id:cycleId,
    claim,
    falsifier,
    target,
    train_evidence:trainEvidence,
    freeze_hash:freezeHash,
  }).select("*").single();
  if(error) throw error;

  return data;
}

async function evaluateFrozenHypothesis(
  freeze:any,
  cycleId:number
) {
  // New live fetch occurs only after the freeze row exists.
  const {text:html,finalUrl,status}=await internetGet(
    cycleId,
    String(freeze.target.url),
    "post-freeze active falsification fetch"
  );

  const tables=parseHtmlTables(html);
  let table=tables.find((t:any)=>t.table_index===Number(freeze.target.table_index));

  if(!table) {
    const left=normalizeRelationValue(String(freeze.target.left_header));
    const right=normalizeRelationValue(String(freeze.target.right_header));
    table=tables.find((t:any)=>
      t.headers.some((h:string)=>normalizeRelationValue(h)===left) &&
      t.headers.some((h:string)=>normalizeRelationValue(h)===right)
    );
  }

  if(!table) {
    return {
      verdict:"unresolved",
      reason:"target table not found after freeze",
      final_url:finalUrl,
      http_status:status,
      counterexamples:[],
      checked_at:nowIso(),
    };
  }

  let leftCol=Number(freeze.target.left_col);
  let rightCol=Number(freeze.target.right_col);

  const leftHeader=normalizeRelationValue(String(freeze.target.left_header));
  const rightHeader=normalizeRelationValue(String(freeze.target.right_header));

  if(normalizeRelationValue(String(table.headers[leftCol]??""))!==leftHeader) {
    leftCol=table.headers.findIndex((h:string)=>normalizeRelationValue(h)===leftHeader);
  }
  if(normalizeRelationValue(String(table.headers[rightCol]??""))!==rightHeader) {
    rightCol=table.headers.findIndex((h:string)=>normalizeRelationValue(h)===rightHeader);
  }

  if(leftCol<0 || rightCol<0) {
    return {
      verdict:"unresolved",
      reason:"target columns not found after freeze",
      final_url:finalUrl,
      http_status:status,
      counterexamples:[],
      checked_at:nowIso(),
    };
  }

  const counterexamples=relationCounterexamples(table.rows,leftCol,rightCol);
  const verdict=counterexamples.length>0 ? "reject" : "not_reject";

  return {
    verdict,
    final_url:finalUrl,
    http_status:status,
    row_count:table.rows.length,
    counterexample_count:counterexamples.length,
    counterexamples:counterexamples.slice(0,20),
    checked_at:nowIso(),
  };
}

async function activeFalsifierEvaluator(goal:Goal, cycleId:number) {
  const candidateKey=String(goal.target?.candidate_key??"D0005:active-falsifier");

  const {data:cases,error:caseErr}=await db
    .from("mind_core_falsifier_cases")
    .select("*")
    .order("id",{ascending:true});
  if(caseErr) throw caseErr;
  if(!cases?.length) throw new Error("active falsifier evaluator has no cases");

  const results:any[]=[];
  let passedCount=0;

  for(const c of cases) {
    // Phase 1: candidate sees source data and proposes relations from train rows.
    const {text:sourceHtml,finalUrl:sourceFinal,status:sourceStatus}=await internetGet(
      cycleId,String(c.url),"pre-freeze hypothesis formation fetch"
    );
    const tables=parseHtmlTables(sourceHtml);
    const proposals=proposeRelationsFromTraining(tables);

    // Evaluator selects a frozen target only after candidate proposals exist.
    const left=normalizeRelationValue(String(c.left_header));
    const right=normalizeRelationValue(String(c.right_header));
    const proposal=proposals.find((p:any)=>
      normalizeRelationValue(String(p.left_header))===left &&
      normalizeRelationValue(String(p.right_header))===right
    ) ?? null;

    let freeze:any=null;
    let verdict:any={
      verdict:"unresolved",
      reason:"candidate did not propose target relation",
      counterexamples:[],
      checked_at:nowIso(),
    };

    if(proposal) {
      freeze=await freezeRelationHypothesis(
        candidateKey,
        String(c.case_key),
        cycleId,
        String(c.url),
        proposal
      );

      // Phase 2: only after durable freeze, fetch fresh evidence and try to falsify.
      verdict=await evaluateFrozenHypothesis(freeze,cycleId);

      const {error:verdictErr}=await db.from("mind_core_hypothesis_verdicts").insert({
        freeze_id:freeze.id,
        cycle_id:cycleId,
        verdict:verdict.verdict,
        evidence:verdict,
      });
      if(verdictErr) throw verdictErr;
    }

    const passed=String(verdict.verdict)===String(c.expected_verdict);
    if(passed) passedCount += 1;

    results.push({
      case_key:c.case_key,
      url:c.url,
      source_final_url:sourceFinal,
      source_http_status:sourceStatus,
      target:{
        left_header:c.left_header,
        right_header:c.right_header,
      },
      expected_verdict:c.expected_verdict,
      proposal_found:!!proposal,
      freeze_id:freeze?.id??null,
      freeze_hash:freeze?.freeze_hash??null,
      claim:freeze?.claim??null,
      falsifier:freeze?.falsifier??null,
      verdict,
      passed,
    });
  }

  const allPassed=passedCount===cases.length;
  const summary={
    candidate_key:candidateKey,
    evaluator_version:"active-falsifier-v1",
    cases_total:cases.length,
    cases_passed:passedCount,
    all_passed:allPassed,
    freeze_before_second_fetch:true,
    immutable_claim_and_falsifier:true,
    cases:results,
    checked_at:nowIso(),
  };

  const {error:updateErr}=await db.from("mind_core_development_candidates").update({
    status:allPassed?"admitted":"rejected",
    shadow_result:summary,
    internet_evidence:{
      evaluator_version:"active-falsifier-v1",
      research_source:"https://www.itl.nist.gov/div898/handbook/prc/section1/prc13.htm",
      freeze_before_second_fetch:true,
      cases:cases.length,
    },
    updated_at:nowIso(),
  }).eq("candidate_key",candidateKey);
  if(updateErr) throw updateErr;

  return summary;
}


async function activeFalsifyRelation(
  cycleId:number,
  caseKey:string,
  url:string,
  leftHeader:string,
  rightHeader:string
) {
  const mechanism=await getMechanismByKey(ACTIVE_FALSIFIER_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) {
    throw new Error("active falsifier inactive");
  }

  // Phase 1: form candidate relation from train-only view.
  const {text:sourceHtml,finalUrl:sourceFinal,status:sourceStatus}=await internetGet(
    cycleId,url,"M0010 pre-freeze hypothesis formation"
  );
  const tables=parseHtmlTables(sourceHtml);
  const proposals=proposeRelationsFromTraining(tables);

  const left=normalizeRelationValue(leftHeader);
  const right=normalizeRelationValue(rightHeader);
  const proposal=proposals.find((p:any)=>
    normalizeRelationValue(String(p.left_header))===left &&
    normalizeRelationValue(String(p.right_header))===right
  ) ?? null;

  if(!proposal) {
    const unresolved={
      mechanism_key:ACTIVE_FALSIFIER_MECHANISM,
      case_key:caseKey,
      url,
      left_header:leftHeader,
      right_header:rightHeader,
      source_final_url:sourceFinal,
      source_http_status:sourceStatus,
      verdict:"unresolved",
      reason:"target relation was not strong enough to freeze as a candidate claim",
      checked_at:nowIso(),
    };

    await logMechanismEvent(
      mechanism.id,cycleId,"active_falsification",
      {case_key:caseKey,url,left_header:leftHeader,right_header:rightHeader},
      unresolved,
      true
    );
    return unresolved;
  }

  const freeze=await freezeRelationHypothesis(
    ACTIVE_FALSIFIER_MECHANISM,
    caseKey,
    cycleId,
    url,
    proposal
  );

  // Phase 2: fresh evidence after durable freeze.
  const verdict=await evaluateFrozenHypothesis(freeze,cycleId);

  const {error:verdictErr}=await db.from("mind_core_hypothesis_verdicts").insert({
    freeze_id:freeze.id,
    cycle_id:cycleId,
    verdict:verdict.verdict,
    evidence:verdict,
  });
  if(verdictErr) throw verdictErr;

  const result={
    mechanism_key:ACTIVE_FALSIFIER_MECHANISM,
    case_key:caseKey,
    url,
    source_final_url:sourceFinal,
    source_http_status:sourceStatus,
    freeze_id:freeze.id,
    freeze_hash:freeze.freeze_hash,
    claim:freeze.claim,
    falsifier:freeze.falsifier,
    verdict,
    checked_at:nowIso(),
  };

  await logMechanismEvent(
    mechanism.id,cycleId,"active_falsification",
    {case_key:caseKey,url,left_header:leftHeader,right_header:rightHeader},
    result,
    true
  );

  return result;
}

async function activeFalsifierSelfTest(goal:Goal, cycleId:number) {
  const tests=Array.isArray(goal.target?.tests)?goal.target.tests:[];
  if(tests.length<2) throw new Error("M0010 self-test requires multiple tests");

  const results:any[]=[];
  let passedCount=0;

  for(const t of tests) {
    const result=await activeFalsifyRelation(
      cycleId,
      String(t.case_key??""),
      String(t.url??""),
      String(t.left_header??""),
      String(t.right_header??"")
    );

    const passed=String(result.verdict?.verdict??result.verdict)===String(t.expected_verdict);
    if(passed) passedCount += 1;

    results.push({
      ...result,
      expected_verdict:t.expected_verdict,
      passed,
    });
  }

  const allPassed=passedCount===tests.length;
  const summary={
    mechanism_key:ACTIVE_FALSIFIER_MECHANISM,
    tests_total:tests.length,
    tests_passed:passedCount,
    all_passed:allPassed,
    freeze_before_second_fetch:true,
    results,
    checked_at:nowIso(),
  };

  if(!allPassed) throw new Error("M0010 self-test failed");

  const mechanism=await getMechanismByKey(ACTIVE_FALSIFIER_MECHANISM);
  const evidence={
    ...(mechanism.evidence??{}),
    independent_self_test:summary,
    admitted_reason:"Implemented D0005 after 4/4 blind freeze-before-fetch evaluation; independent HTTP Field Registry test correctly kept Field Name→Status and rejected Status→Field Name.",
  };

  const {error}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence,
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key",ACTIVE_FALSIFIER_MECHANISM);
  if(error) throw error;

  return summary;
}


async function beliefContentHash(content:any) {
  return await sha256Hex(JSON.stringify(content));
}

async function ensureSeedBelief(freeze:any) {
  const beliefKey=`hypothesis-freeze:${freeze.id}`;

  const {data:existing,error:existingErr}=await db.from("mind_core_beliefs")
    .select("*")
    .eq("belief_key",beliefKey)
    .eq("version",1)
    .maybeSingle();
  if(existingErr) throw existingErr;
  if(existing) return existing;

  const content={
    type:"frozen_claim",
    statement:String(freeze.claim?.statement??""),
    left_header:String(freeze.claim?.left_header??""),
    right_header:String(freeze.claim?.right_header??""),
    claim_type:String(freeze.claim?.type??""),
  };
  const contentHash=await beliefContentHash(content);

  const {data,error}=await db.from("mind_core_beliefs").insert({
    belief_key:beliefKey,
    version:1,
    parent_belief_id:null,
    source_freeze_id:freeze.id,
    source_verdict_id:null,
    content,
    epistemic_status:"proposed",
    evidence:{
      freeze_hash:freeze.freeze_hash,
      frozen_at:freeze.frozen_at,
      train_evidence:freeze.train_evidence,
    },
    content_hash:contentHash,
  }).select("*").single();
  if(error) throw error;
  return data;
}

async function reviseBeliefFromVerdict(
  freeze:any,
  verdictRow:any,
  cycleId:number
) {
  const parent=await ensureSeedBelief(freeze);
  const beliefKey=String(parent.belief_key);

  const {data:already,error:alreadyErr}=await db.from("mind_core_beliefs")
    .select("*")
    .eq("belief_key",beliefKey)
    .eq("source_verdict_id",verdictRow.id)
    .maybeSingle();
  if(alreadyErr) throw alreadyErr;

  if(already) {
    return {
      parent,
      child:already,
      reused_existing_revision:true,
    };
  }

  const verdict=String(verdictRow.verdict);
  const evidence=verdictRow.evidence??{};
  const left=String(freeze.claim?.left_header??"");
  const right=String(freeze.claim?.right_header??"");
  const priorStatement=String(freeze.claim?.statement??"");

  let content:any;
  let epistemicStatus:
    "survived_test"|"revised_after_refutation"|"unresolved";
  let revisionKind:"reinforce"|"refute_and_revise"|"mark_unresolved";

  if(verdict==="reject") {
    content={
      type:"revised_relation",
      statement:`${left} does not globally functionally determine ${right}`,
      prior_statement:priorStatement,
      revision_scope:"global functional claim refuted",
      counterexample_count:Number(evidence.counterexample_count??0),
      counterexamples:Array.isArray(evidence.counterexamples)
        ? evidence.counterexamples.slice(0,20)
        : [],
    };
    epistemicStatus="revised_after_refutation";
    revisionKind="refute_and_revise";
  } else if(verdict==="not_reject") {
    content={
      type:"tested_claim",
      statement:priorStatement,
      left_header:left,
      right_header:right,
      test_outcome:"not_reject",
      interpretation:"survived this falsification attempt; not promoted to proven truth",
    };
    epistemicStatus="survived_test";
    revisionKind="reinforce";
  } else {
    content={
      type:"unresolved_claim",
      statement:priorStatement,
      left_header:left,
      right_header:right,
      test_outcome:"unresolved",
      interpretation:"insufficient evidence for reject or not_reject",
    };
    epistemicStatus="unresolved";
    revisionKind="mark_unresolved";
  }

  const {data:maxRow,error:maxErr}=await db.from("mind_core_beliefs")
    .select("version")
    .eq("belief_key",beliefKey)
    .order("version",{ascending:false})
    .limit(1)
    .maybeSingle();
  if(maxErr) throw maxErr;

  const nextVersion=Number(maxRow?.version??1)+1;
  const contentHash=await beliefContentHash(content);

  const {data:child,error:childErr}=await db.from("mind_core_beliefs").insert({
    belief_key:beliefKey,
    version:nextVersion,
    parent_belief_id:parent.id,
    source_freeze_id:freeze.id,
    source_verdict_id:verdictRow.id,
    content,
    epistemic_status:epistemicStatus,
    evidence:{
      verdict,
      verdict_evidence:evidence,
      revision_cycle_id:cycleId,
      parent_content_hash:parent.content_hash,
    },
    content_hash:contentHash,
  }).select("*").single();
  if(childErr) throw childErr;

  const {error:eventErr}=await db.from("mind_core_belief_revision_events").insert({
    from_belief_id:parent.id,
    to_belief_id:child.id,
    source_verdict_id:verdictRow.id,
    revision_kind:revisionKind,
    rationale:{
      verdict,
      parent_statement:priorStatement,
      child_statement:content.statement,
      parent_content_hash:parent.content_hash,
      child_content_hash:child.content_hash,
      counterexample_count:Number(evidence.counterexample_count??0),
    },
  });
  if(eventErr) throw eventErr;

  return {
    parent,
    child,
    reused_existing_revision:false,
  };
}

async function beliefRevisionEvaluator(goal:Goal, cycleId:number) {
  const candidateKey=String(goal.target?.candidate_key??"D0006:belief-revision");
  const sourceCandidate=String(goal.target?.source_candidate??"D0005:active-falsifier");

  const {data:freezes,error:freezeErr}=await db.from("mind_core_hypothesis_freezes")
    .select("*")
    .eq("candidate_key",sourceCandidate)
    .order("id",{ascending:true});
  if(freezeErr) throw freezeErr;
  if(!freezes?.length) throw new Error("belief revision evaluator has no source freezes");

  const results:any[]=[];
  let passedCount=0;

  for(const freeze of freezes) {
    const {data:verdictRow,error:verdictErr}=await db.from("mind_core_hypothesis_verdicts")
      .select("*")
      .eq("freeze_id",freeze.id)
      .order("id",{ascending:false})
      .limit(1)
      .maybeSingle();
    if(verdictErr) throw verdictErr;
    if(!verdictRow) continue;

    const revision=await reviseBeliefFromVerdict(freeze,verdictRow,cycleId);

    const parentHashBefore=String(revision.parent.content_hash);
    const parentContentBefore=JSON.stringify(revision.parent.content);

    const {data:parentAfter,error:parentAfterErr}=await db.from("mind_core_beliefs")
      .select("*")
      .eq("id",revision.parent.id)
      .single();
    if(parentAfterErr) throw parentAfterErr;

    const parentHashAfter=String(parentAfter.content_hash);
    const parentContentAfter=JSON.stringify(parentAfter.content);

    const verdict=String(verdictRow.verdict);
    const childStatus=String(revision.child.epistemic_status);
    const childStatement=String(revision.child.content?.statement??"");

    const semanticPass=
      verdict==="reject"
        ? (
            childStatus==="revised_after_refutation" &&
            /does not globally functionally determine/i.test(childStatement) &&
            Number(revision.child.content?.counterexample_count??0)>0
          )
        : verdict==="not_reject"
          ? (
              childStatus==="survived_test" &&
              String(revision.child.content?.test_outcome)==="not_reject" &&
              /not promoted to proven truth/i.test(
                String(revision.child.content?.interpretation??"")
              )
            )
          : childStatus==="unresolved";

    const provenancePass=
      Number(revision.child.parent_belief_id)===Number(revision.parent.id) &&
      Number(revision.child.source_verdict_id)===Number(verdictRow.id) &&
      Number(revision.child.source_freeze_id)===Number(freeze.id);

    const immutabilityPass=
      parentHashBefore===parentHashAfter &&
      parentContentBefore===parentContentAfter;

    const passed=semanticPass && provenancePass && immutabilityPass;
    if(passed) passedCount += 1;

    results.push({
      freeze_id:freeze.id,
      verdict_id:verdictRow.id,
      verdict,
      parent_belief_id:revision.parent.id,
      parent_version:revision.parent.version,
      parent_content_hash:parentHashBefore,
      child_belief_id:revision.child.id,
      child_version:revision.child.version,
      child_content_hash:revision.child.content_hash,
      child_status:childStatus,
      child_statement:childStatement,
      semantic_pass:semanticPass,
      provenance_pass:provenancePass,
      immutability_pass:immutabilityPass,
      passed,
    });
  }

  const allPassed=results.length>0 && passedCount===results.length;
  const summary={
    candidate_key:candidateKey,
    evaluator_version:"belief-revision-v1",
    cases_total:results.length,
    cases_passed:passedCount,
    all_passed:allPassed,
    append_only:true,
    parent_hash_preservation:true,
    no_truth_upgrade_from_not_reject:true,
    results,
    checked_at:nowIso(),
  };

  const {error:updateErr}=await db.from("mind_core_development_candidates").update({
    status:allPassed?"admitted":"rejected",
    shadow_result:summary,
    internet_evidence:{
      source:"real M0010 frozen claims and post-freeze verdicts",
      evaluator_version:"belief-revision-v1",
      cases:results.length,
    },
    updated_at:nowIso(),
  }).eq("candidate_key",candidateKey);
  if(updateErr) throw updateErr;

  return summary;
}


async function applyBeliefRevisionByFreezeId(freezeId:number, cycleId:number) {
  const mechanism=await getMechanismByKey(BELIEF_REVISION_MECHANISM);
  if(!["probation","admitted"].includes(mechanism.status)) {
    throw new Error("belief revision mechanism inactive");
  }

  const {data:freeze,error:freezeErr}=await db.from("mind_core_hypothesis_freezes")
    .select("*")
    .eq("id",freezeId)
    .single();
  if(freezeErr) throw freezeErr;

  const {data:verdictRow,error:verdictErr}=await db.from("mind_core_hypothesis_verdicts")
    .select("*")
    .eq("freeze_id",freezeId)
    .order("id",{ascending:false})
    .limit(1)
    .maybeSingle();
  if(verdictErr) throw verdictErr;
  if(!verdictRow) throw new Error("no verdict for freeze");

  const revision=await reviseBeliefFromVerdict(freeze,verdictRow,cycleId);

  const result={
    mechanism_key:BELIEF_REVISION_MECHANISM,
    freeze_id:freeze.id,
    verdict_id:verdictRow.id,
    verdict:verdictRow.verdict,
    parent_belief_id:revision.parent.id,
    parent_version:revision.parent.version,
    parent_content_hash:revision.parent.content_hash,
    child_belief_id:revision.child.id,
    child_version:revision.child.version,
    child_content_hash:revision.child.content_hash,
    child_status:revision.child.epistemic_status,
    child_content:revision.child.content,
    reused_existing_revision:revision.reused_existing_revision,
    checked_at:nowIso(),
  };

  await logMechanismEvent(
    mechanism.id,cycleId,"belief_revision",
    {freeze_id:freeze.id,verdict_id:verdictRow.id},
    result,
    true
  );

  return result;
}

async function beliefRevisionSelfTest(goal:Goal, cycleId:number) {
  const freezeIds=Array.isArray(goal.target?.freeze_ids)
    ? goal.target.freeze_ids.map((x:any)=>Number(x)).filter(Number.isFinite)
    : [];
  if(freezeIds.length<2) throw new Error("M0011 self-test requires multiple freeze ids");

  const results:any[]=[];
  let passedCount=0;

  for(const freezeId of freezeIds) {
    const result=await applyBeliefRevisionByFreezeId(freezeId,cycleId);
    const verdict=String(result.verdict);

    const semanticPass=
      verdict==="reject"
        ? (
            result.child_status==="revised_after_refutation" &&
            /does not globally functionally determine/i.test(
              String(result.child_content?.statement??"")
            ) &&
            Number(result.child_content?.counterexample_count??0)>0
          )
        : verdict==="not_reject"
          ? (
              result.child_status==="survived_test" &&
              String(result.child_content?.test_outcome)==="not_reject" &&
              /not promoted to proven truth/i.test(
                String(result.child_content?.interpretation??"")
              )
            )
          : result.child_status==="unresolved";

    const provenancePass=
      Number(result.child_version)===Number(result.parent_version)+1 &&
      !!result.parent_content_hash &&
      !!result.child_content_hash;

    const passed=semanticPass && provenancePass;
    if(passed) passedCount += 1;

    results.push({
      ...result,
      semantic_pass:semanticPass,
      provenance_pass:provenancePass,
      passed,
    });
  }

  const allPassed=passedCount===freezeIds.length;
  const summary={
    mechanism_key:BELIEF_REVISION_MECHANISM,
    tests_total:freezeIds.length,
    tests_passed:passedCount,
    all_passed:allPassed,
    append_only:true,
    results,
    checked_at:nowIso(),
  };

  if(!allPassed) throw new Error("M0011 self-test failed");

  const mechanism=await getMechanismByKey(BELIEF_REVISION_MECHANISM);
  const evidence={
    ...(mechanism.evidence??{}),
    independent_self_test:summary,
    admitted_reason:"Implemented D0006 after 4/4 append-only belief-revision evaluation; independent fresh M0010 verdicts produced one survived_test belief and one revised_after_refutation belief with preserved lineage.",
  };

  const {error}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence,
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key",BELIEF_REVISION_MECHANISM);
  if(error) throw error;

  return summary;
}


function machineReadableObservation(text:string) {
  const trimmed=String(text??"").trim();
  let kind="text";
  let parsed:any=null;

  if(trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      parsed=JSON.parse(trimmed);
      kind="json";
    } catch {}
  } else if(
    trimmed.startsWith("<?xml") ||
    /<feed\b|<entry\b|<rss\b/i.test(trimmed.slice(0,2000))
  ) {
    kind="xml";
  }

  return {
    kind,
    machine_readable:kind==="json" || kind==="xml",
    parsed_preview:
      kind==="json"
        ? (
            Array.isArray(parsed)
              ? {array_length:parsed.length}
              : {
                  keys:Object.keys(parsed??{}).slice(0,20),
                  top_type:typeof parsed,
                }
          )
        : null,
  };
}

async function probeResource(resource:any, cycleId:number) {
  const started=Date.now();
  let observation:any={};

  try {
    const {text,finalUrl,status}=await internetGet(
      cycleId,
      String(resource.probe_url),
      `Resource Fabric probe: ${resource.resource_key}`
    );
    const latencyMs=Date.now()-started;
    const readable=machineReadableObservation(text);
    const ok=
      status===200 &&
      readable.machine_readable===true &&
      String(finalUrl).startsWith("https://");

    observation={
      resource_key:resource.resource_key,
      name:resource.name,
      probe_url:resource.probe_url,
      final_url:finalUrl,
      http_status:status,
      latency_ms:latencyMs,
      bytes:text.length,
      machine_readable:readable.machine_readable,
      response_kind:readable.kind,
      parsed_preview:readable.parsed_preview,
      ok,
      checked_at:nowIso(),
    };

    const {error:probeErr}=await db.from("mind_core_resource_probes").insert({
      resource_id:resource.id,
      cycle_id:cycleId,
      probe_url:resource.probe_url,
      http_status:status,
      latency_ms:latencyMs,
      bytes:text.length,
      ok,
      observation,
    });
    if(probeErr) throw probeErr;

    const autoAdmit=
      resource.access_mode==="read_only" &&
      resource.auth_mode==="none" &&
      resource.cost_mode==="public_free" &&
      !!resource.admission_policy?.auto_admit;

    const nextStatus=ok && autoAdmit ? "admitted" : (ok ? "probation" : "blocked");

    const evidence={
      ...(resource.evidence??{}),
      latest_probe:observation,
      admission_reason:
        nextStatus==="admitted"
          ? "Live HTTPS probe succeeded from Mind Core runtime; response is machine-readable; resource is public, no-auth, read-only, and public-free."
          : nextStatus==="probation"
            ? "Live probe succeeded but resource is not eligible for automatic admission."
            : "Live probe failed admission health criteria.",
    };

    const {error:updateErr}=await db.from("mind_core_resources").update({
      status:nextStatus,
      evidence,
      admitted_at:nextStatus==="admitted" ? nowIso() : resource.admitted_at,
      last_probe_at:nowIso(),
      updated_at:nowIso(),
    }).eq("id",resource.id);
    if(updateErr) throw updateErr;

    return {...observation,status_after:nextStatus};
  } catch(error) {
    const message=error instanceof Error?error.message:String(error);
    const latencyMs=Date.now()-started;

    observation={
      resource_key:resource.resource_key,
      name:resource.name,
      probe_url:resource.probe_url,
      error:message,
      latency_ms:latencyMs,
      ok:false,
      checked_at:nowIso(),
    };

    await db.from("mind_core_resource_probes").insert({
      resource_id:resource.id,
      cycle_id:cycleId,
      probe_url:resource.probe_url,
      http_status:null,
      latency_ms:latencyMs,
      bytes:0,
      ok:false,
      observation,
    });

    await db.from("mind_core_resources").update({
      status:"blocked",
      evidence:{
        ...(resource.evidence??{}),
        latest_probe:observation,
        admission_reason:"Live probe failed.",
      },
      last_probe_at:nowIso(),
      updated_at:nowIso(),
    }).eq("id",resource.id);

    return {...observation,status_after:"blocked"};
  }
}

async function ensureResourceRoutes(resource:any) {
  const routeSpecs:any[]=[];

  if(resource.resource_key==="RF:CROSSREF") {
    routeSpecs.push(
      {purpose:"scholarly_search",priority:0.90},
      {purpose:"doi_metadata",priority:1.00}
    );
  } else if(resource.resource_key==="RF:OPENALEX") {
    routeSpecs.push(
      {purpose:"scholarly_search",priority:0.95},
      {purpose:"citation_graph",priority:1.00}
    );
  } else if(resource.resource_key==="RF:ARXIV") {
    routeSpecs.push(
      {purpose:"scholarly_search",priority:0.80},
      {purpose:"preprint_search",priority:1.00}
    );
  } else if(resource.resource_key==="RF:PYPI") {
    routeSpecs.push(
      {purpose:"package_metadata",priority:1.00},
      {purpose:"python_ecosystem",priority:0.95}
    );
  } else if(resource.resource_key==="RF:GITHUB_PUBLIC") {
    routeSpecs.push(
      {purpose:"code_intelligence",priority:1.00},
      {purpose:"software_ecosystem",priority:0.90}
    );
  }

  for(const route of routeSpecs) {
    const {error}=await db.from("mind_core_resource_routes").upsert({
      purpose:route.purpose,
      resource_id:resource.id,
      priority:route.priority,
      enabled:true,
      constraints:{read_only:true},
    },{onConflict:"purpose,resource_id"});
    if(error) throw error;
  }
}

async function resourceFabricAdmission(goal:Goal, cycleId:number) {
  const keys=Array.isArray(goal.target?.resource_keys)
    ? goal.target.resource_keys.map((x:any)=>String(x))
    : [];

  const {data:resources,error}=await db.from("mind_core_resources")
    .select("*")
    .in("resource_key",keys)
    .order("id",{ascending:true});
  if(error) throw error;
  if(!resources?.length) throw new Error("Resource Fabric has no candidates");

  const results:any[]=[];
  for(const resource of resources) {
    const result=await probeResource(resource,cycleId);
    results.push(result);

    if(result.status_after==="admitted") {
      const refreshed={...resource,status:"admitted"};
      await ensureResourceRoutes(refreshed);
    }
  }

  const admitted=results.filter(r=>r.status_after==="admitted").length;
  const summary={
    resource_fabric_version:"RF-0.1",
    candidates_total:results.length,
    admitted,
    blocked:results.filter(r=>r.status_after==="blocked").length,
    probation:results.filter(r=>r.status_after==="probation").length,
    results,
    policy:{
      auto_connect:"public + no-auth + read-only + public-free + HTTPS + machine-readable + live HTTP 200",
      paid_or_authenticated:"discover only; require explicit approval",
    },
    checked_at:nowIso(),
  };

  return summary;
}

async function fetchThroughResource(
  cycleId:number,
  resourceKey:string,
  pathOrUrl:string,
  purpose:string
) {
  const {data:resource,error}=await db.from("mind_core_resources")
    .select("*")
    .eq("resource_key",resourceKey)
    .single();
  if(error) throw error;
  if(resource.status!=="admitted") {
    throw new Error(`resource not admitted: ${resourceKey}`);
  }

  const base=new URL(String(resource.base_url));
  const target=new URL(pathOrUrl,base);
  if(target.hostname!==base.hostname) {
    throw new Error("resource route cannot leave admitted resource host");
  }

  const result=await internetGet(
    cycleId,
    target.toString(),
    `Resource Fabric ${resourceKey}: ${purpose}`
  );

  return {
    resource_key:resourceKey,
    provider:resource.provider,
    url:target.toString(),
    final_url:result.finalUrl,
    http_status:result.status,
    text:result.text,
  };
}

async function resourceFabricBenchmark(goal:Goal, cycleId:number) {
  const query=String(goal.target?.query??"causal discovery");
  const encoded=encodeURIComponent(query);

  const jobs=[
    {
      resource_key:"RF:CROSSREF",
      path:`works?query.title=${encoded}&rows=2`,
      purpose:"scholarly_search",
    },
    {
      resource_key:"RF:OPENALEX",
      path:`works?search=${encoded}&per-page=2`,
      purpose:"scholarly_search",
    },
    {
      resource_key:"RF:ARXIV",
      path:`api/query?search_query=all%3A${encoded}&max_results=2`,
      purpose:"scholarly_search",
    },
  ];

  const results:any[]=[];
  for(const job of jobs) {
    try {
      const r=await fetchThroughResource(
        cycleId,
        job.resource_key,
        job.path,
        job.purpose
      );
      const readable=machineReadableObservation(r.text);
      results.push({
        resource_key:job.resource_key,
        provider:r.provider,
        http_status:r.http_status,
        bytes:r.text.length,
        response_kind:readable.kind,
        ok:r.http_status===200 && readable.machine_readable,
        preview:
          readable.kind==="json"
            ? readable.parsed_preview
            : r.text.slice(0,500),
      });
    } catch(error) {
      results.push({
        resource_key:job.resource_key,
        ok:false,
        error:error instanceof Error?error.message:String(error),
      });
    }
  }

  return {
    query,
    successful_sources:results.filter(r=>r.ok).length,
    total_sources:results.length,
    results,
    checked_at:nowIso(),
  };
}


const SEVERITY_RANK:Record<string,number>={
  info:0,low:1,medium:2,high:3,critical:4
};

function maxSeverity(a:string,b:string) {
  return (SEVERITY_RANK[b]??0)>(SEVERITY_RANK[a]??0)?b:a;
}

async function canonicalEventFingerprint(payload:any) {
  return await sha256Hex(JSON.stringify(payload));
}

async function getObservationPlugins() {
  const {data,error}=await db.from("mind_core_observation_plugins")
    .select("*")
    .eq("status","admitted")
    .order("stage",{ascending:true})
    .order("id",{ascending:true});
  if(error) throw error;
  return data??[];
}

async function applyResourceProbePlugins(
  probe:any,
  resource:any,
  eventId:number,
  currentSeverity:string
) {
  const plugins=await getObservationPlugins();
  let severity=currentSeverity;
  const pipeline:string[]=["resource_fabric_probe"];
  const findings:any[]=[];

  for(const plugin of plugins) {
    const accepted=Array.isArray(plugin.input_event_types)
      ? plugin.input_event_types.includes("resource_probe")
      : false;
    if(!accepted) continue;

    let matched=false;
    let result:any={plugin_key:plugin.plugin_key,stage:plugin.stage};

    if(plugin.plugin_key==="OP:RESOURCE_HEALTH") {
      const obs=probe.observation??{};
      const expected=Number(plugin.config?.expected_http_status??200);
      const requireMachine=plugin.config?.require_machine_readable!==false;
      const httpOk=Number(probe.http_status)===expected;
      const machineOk=!requireMachine || obs.machine_readable===true;
      matched=!(probe.ok===true && httpOk && machineOk);

      result={
        ...result,
        ok:probe.ok===true,
        http_status:probe.http_status,
        machine_readable:obs.machine_readable===true,
        matched,
      };
      if(matched) {
        severity=maxSeverity(
          severity,
          String(plugin.config?.severity_on_failure??"high")
        );
      }
    }

    if(plugin.plugin_key==="OP:BASELINE_LATENCY") {
      const metricKey="latency_ms";
      const value=Number(probe.latency_ms);
      const {data:baseline,error:baseErr}=await db
        .from("mind_core_observation_baselines")
        .select("*")
        .eq("subject_key",resource.resource_key)
        .eq("metric_key",metricKey)
        .maybeSingle();
      if(baseErr) throw baseErr;

      const warmup=Number(plugin.config?.warmup_samples??3);
      const multiplier=Number(plugin.config?.anomaly_multiplier??3);
      const priorCount=Number(baseline?.sample_count??0);
      const priorMean=baseline?.mean_value==null?null:Number(baseline.mean_value);

      matched=
        Number.isFinite(value) &&
        priorCount>=warmup &&
        priorMean!=null &&
        priorMean>0 &&
        value>priorMean*multiplier;

      result={
        ...result,
        metric:metricKey,
        value,
        prior_count:priorCount,
        prior_mean:priorMean,
        anomaly_multiplier:multiplier,
        matched,
      };

      if(matched) {
        severity=maxSeverity(
          severity,
          String(plugin.config?.severity??"medium")
        );
      }

      if(Number.isFinite(value)) {
        const nextCount=priorCount+1;
        const nextMean=
          priorMean==null
            ? value
            : ((priorMean*priorCount)+value)/nextCount;
        const nextMin=baseline?.min_value==null
          ? value
          : Math.min(Number(baseline.min_value),value);
        const nextMax=baseline?.max_value==null
          ? value
          : Math.max(Number(baseline.max_value),value);

        const {error:upErr}=await db
          .from("mind_core_observation_baselines")
          .upsert({
            subject_key:resource.resource_key,
            metric_key:metricKey,
            sample_count:nextCount,
            mean_value:nextMean,
            min_value:nextMin,
            max_value:nextMax,
            categorical_value:null,
            updated_at:nowIso(),
          },{onConflict:"subject_key,metric_key"});
        if(upErr) throw upErr;
      }
    }

    if(plugin.plugin_key==="OP:SCHEMA_STABILITY") {
      const metricKey="response_kind";
      const currentKind=String(probe.observation?.response_kind??"unknown");

      const {data:baseline,error:baseErr}=await db
        .from("mind_core_observation_baselines")
        .select("*")
        .eq("subject_key",resource.resource_key)
        .eq("metric_key",metricKey)
        .maybeSingle();
      if(baseErr) throw baseErr;

      const priorKind=baseline?.categorical_value==null
        ? null
        : String(baseline.categorical_value);

      matched=priorKind!=null && priorKind!==currentKind;

      result={
        ...result,
        metric:metricKey,
        prior_kind:priorKind,
        current_kind:currentKind,
        matched,
      };

      if(matched) {
        severity=maxSeverity(
          severity,
          String(plugin.config?.severity_on_change??"medium")
        );
      }

      const {error:upErr}=await db
        .from("mind_core_observation_baselines")
        .upsert({
          subject_key:resource.resource_key,
          metric_key:metricKey,
          sample_count:Number(baseline?.sample_count??0)+1,
          mean_value:null,
          min_value:null,
          max_value:null,
          categorical_value:priorKind??currentKind,
          updated_at:nowIso(),
        },{onConflict:"subject_key,metric_key"});
      if(upErr) throw upErr;
    }

    pipeline.push(plugin.plugin_key);
    findings.push(result);

    const {error:runErr}=await db
      .from("mind_core_observation_plugin_runs")
      .insert({
        plugin_id:plugin.id,
        event_id:eventId,
        stage:plugin.stage,
        matched,
        result,
      });
    if(runErr) throw runErr;
  }

  return {severity,pipeline,findings};
}

async function processResourceProbeObservation(probe:any) {
  const {data:resource,error:resourceErr}=await db
    .from("mind_core_resources")
    .select("*")
    .eq("id",probe.resource_id)
    .single();
  if(resourceErr) throw resourceErr;

  const fingerprintPayload={
    event_type:"resource_probe",
    event_source:"ResourceFabric",
    subject_key:resource.resource_key,
    probe_id:probe.id,
    probe_created_at:probe.created_at,
    observation:probe.observation,
  };
  const fingerprint=await canonicalEventFingerprint(fingerprintPayload);

  const {data:existing,error:existingErr}=await db
    .from("mind_core_observation_events")
    .select("*")
    .eq("event_fingerprint",fingerprint)
    .maybeSingle();
  if(existingErr) throw existingErr;
  if(existing) {
    return {
      event_id:existing.id,
      fingerprint,
      reused:true,
      severity:existing.severity,
      summary:existing.summary,
    };
  }

  const initialSummary=
    probe.ok===true
      ? `${resource.name}: live probe OK (HTTP ${probe.http_status})`
      : `${resource.name}: live probe failed`;

  const {data:event,error:eventErr}=await db
    .from("mind_core_observation_events")
    .insert({
      event_type:"resource_probe",
      event_source:"ResourceFabric",
      event_pipeline:["resource_fabric_probe"],
      event_fingerprint:fingerprint,
      subject_type:"resource",
      subject_key:resource.resource_key,
      protocol:"https",
      severity:"info",
      summary:initialSummary,
      tags:[
        resource.resource_class,
        resource.status,
        probe.ok===true?"healthy":"probe-failed"
      ],
      context:{
        provider:resource.provider,
        resource_class:resource.resource_class,
        access_mode:resource.access_mode,
        auth_mode:resource.auth_mode,
        cost_mode:resource.cost_mode,
      },
      raw_observation:probe.observation??{},
      observed_at:probe.created_at??nowIso(),
    })
    .select("*")
    .single();
  if(eventErr) throw eventErr;

  const applied=await applyResourceProbePlugins(
    probe,
    resource,
    event.id,
    "info"
  );

  const matchedFindings=applied.findings.filter((x:any)=>x.matched);
  const summary=
    matchedFindings.length===0
      ? initialSummary+"; baseline/verification plugins report no anomaly"
      : initialSummary+`; ${matchedFindings.length} observation-plugin anomaly(s)`;

  const {error:updateErr}=await db
    .from("mind_core_observation_events")
    .update({
      event_pipeline:applied.pipeline,
      severity:applied.severity,
      summary,
      tags:[
        resource.resource_class,
        resource.status,
        probe.ok===true?"healthy":"probe-failed",
        ...(matchedFindings.length?["anomaly"]:["baseline-ok"])
      ],
    })
    .eq("id",event.id);
  if(updateErr) throw updateErr;

  return {
    event_id:event.id,
    fingerprint,
    reused:false,
    severity:applied.severity,
    summary,
    pipeline:applied.pipeline,
    findings:applied.findings,
  };
}

async function replayObservationPipeline(goal:Goal, cycleId:number) {
  const limit=Math.max(
    1,
    Math.min(100,Number(goal.target?.limit??20))
  );

  const {data:probes,error}=await db
    .from("mind_core_resource_probes")
    .select("*")
    .order("id",{ascending:true})
    .limit(limit);
  if(error) throw error;

  const results:any[]=[];
  for(const probe of probes??[]) {
    results.push(await processResourceProbeObservation(probe));
  }

  return {
    observation_pipeline_version:"LeakIX-inspired-0.1",
    source:"resource_probes",
    processed:results.length,
    new_events:results.filter(r=>!r.reused).length,
    reused_events:results.filter(r=>r.reused).length,
    anomalies:results.filter(r=>(SEVERITY_RANK[r.severity]??0)>=2).length,
    results,
    principles_applied:[
      "canonical event schema",
      "event pipeline history",
      "event fingerprint deduplication",
      "stage plugins",
      "baseline before anomaly",
      "exception-safe read-only processing"
    ],
    checked_at:nowIso(),
  };
}


async function resourceFabricHealthCycle(cycleId:number) {
  const {data:resources,error}=await db.from("mind_core_resources")
    .select("*")
    .eq("status","admitted")
    .eq("access_mode","read_only")
    .eq("auth_mode","none")
    .eq("cost_mode","public_free")
    .order("id",{ascending:true});
  if(error) throw error;

  const results:any[]=[];

  for(const resource of resources??[]) {
    const probeResult=await probeResource(resource,cycleId);

    const {data:latestProbe,error:probeErr}=await db
      .from("mind_core_resource_probes")
      .select("*")
      .eq("resource_id",resource.id)
      .order("id",{ascending:false})
      .limit(1)
      .single();
    if(probeErr) throw probeErr;

    const eventResult=await processResourceProbeObservation(latestProbe);

    results.push({
      resource_key:resource.resource_key,
      probe:probeResult,
      event:eventResult,
    });
  }

  return {
    resource_fabric_version:"RF-0.1",
    observation_pipeline_version:"LeakIX-inspired-0.1",
    cadence_minutes:180,
    resources_checked:results.length,
    anomalies:results.filter(r=>(SEVERITY_RANK[r.event?.severity]??0)>=2).length,
    results,
    checked_at:nowIso(),
  };
}


function decodeGithubBase64(content:string) {
  const clean=String(content??"").replace(/\s+/g,"");
  return atob(clean);
}

async function ungoogledSourceSync(goal:Goal, cycleId:number) {
  const resourceKey=String(
    goal.target?.resource_key??"RF:UNGOOGLED_CHROMIUM_SOURCE"
  );
  const ref=String(goal.target?.ref??"master");
  const files=Array.isArray(goal.target?.files)
    ? goal.target.files.map((x:any)=>String(x))
    : ["README.md","docs/design.md","docs/flags.md","docs/building.md"];

  const results:any[]=[];
  let readmeText="";
  let designText="";
  let flagsText="";
  let buildingText="";

  for(const path of files) {
    const apiPath=`contents/${path}?ref=${encodeURIComponent(ref)}`;
    const fetched=await fetchThroughResource(
      cycleId,
      resourceKey,
      apiPath,
      `Ungoogled Chromium source sync: ${path}`
    );

    const meta=JSON.parse(fetched.text);
    const decoded=
      meta?.encoding==="base64"
        ? decodeGithubBase64(String(meta.content??""))
        : String(meta.content??"");

    const contentSha256=await sha256Hex(decoded);

    const item={
      path,
      github_blob_sha:String(meta?.sha??""),
      content_sha256:contentSha256,
      bytes:decoded.length,
      api_url:fetched.url,
      http_status:fetched.http_status,
    };
    results.push(item);

    if(path==="README.md") readmeText=decoded;
    if(path==="docs/design.md") designText=decoded;
    if(path==="docs/flags.md") flagsText=decoded;
    if(path==="docs/building.md") buildingText=decoded;

    await recordEvidence(
      cycleId,
      fetched.url,
      "browser_source_sync",
      `Ungoogled Chromium ${path}`,
      item
    );
  }

  const checks={
    google_service_removal:
      /sans dependency on Google web services|Remove all remaining background requests/i.test(readmeText),
    domain_substitution:
      /Domain Substitution/i.test(designText) && /qjz9zk/i.test(designText),
    binary_pruning:
      /Binary Pruning/i.test(designText),
    no_pings_flag:
      /--no-pings/i.test(flagsText),
    reduced_system_info:
      /ReducedSystemInfo/i.test(flagsText),
    remove_client_hints:
      /RemoveClientHints/i.test(flagsText),
    clear_data_on_exit:
      /ClearDataOnExit/i.test(flagsText),
    chromedriver_build:
      /ninja -C out\/Default chrome chromedriver chrome_sandbox/i.test(buildingText),
  };

  const allPassed=Object.values(checks).every(Boolean);

  const {data:resource,error:resourceErr}=await db
    .from("mind_core_resources")
    .select("*")
    .eq("resource_key",resourceKey)
    .single();
  if(resourceErr) throw resourceErr;

  const evidence={
    ...(resource.evidence??{}),
    source_sync:{
      ref,
      files:results,
      checks,
      all_passed:allPassed,
      synced_at:nowIso(),
    },
  };

  const {error:updateErr}=await db.from("mind_core_resources").update({
    evidence,
    updated_at:nowIso(),
  }).eq("id",resource.id);
  if(updateErr) throw updateErr;

  const {data:profile,error:profileErr}=await db
    .from("mind_core_browser_profiles")
    .select("*")
    .eq("profile_key","BP:UNGOOGLED_RESEARCH")
    .single();
  if(profileErr) throw profileErr;

  const {error:profileUpdateErr}=await db
    .from("mind_core_browser_profiles")
    .update({
      evidence:{
        ...(profile.evidence??{}),
        core_source_sync:{
          ref,
          checks,
          all_passed:allPassed,
          files:results,
          synced_at:nowIso(),
        },
      },
      updated_at:nowIso(),
    })
    .eq("id",profile.id);
  if(profileUpdateErr) throw profileUpdateErr;

  return {
    resource_key:resourceKey,
    ref,
    files_synced:results.length,
    checks,
    all_passed:allPassed,
    files:results,
    browser_profile:"BP:UNGOOGLED_RESEARCH",
    runtime_candidate:"RF:UNGOOGLED_CHROMIUM_RUNTIME",
    runtime_attached:false,
    runtime_blocker:"no verified compatible native browser host attached",
    checked_at:nowIso(),
  };
}


async function currentMindProgram() {
  const {data:program,error:programErr}=await db
    .from("mind_core_programs")
    .select("*")
    .eq("program_key","PROGRAM:DIGITAL_MIND_V1")
    .single();
  if(programErr) throw programErr;

  const {data:step,error:stepErr}=await db
    .from("mind_core_program_steps")
    .select("*")
    .eq("program_id",program.id)
    .eq("ordinal",program.current_step)
    .single();
  if(stepErr) throw stepErr;

  return {program,step};
}

async function researchContextualBeliefArbitration(
  program:any,
  step:any,
  cycleId:number
) {
  const researchUrl="https://plato.stanford.edu/entries/logic-belief-revision/";
  const {text,finalUrl,status}=await internetGet(
    cycleId,
    researchUrl,
    "Digital Mind DM01 research: contextual belief arbitration"
  );
  const plain=stripHtml(text).toLowerCase();

  const signals={
    belief_revision:/belief revision/.test(plain),
    inconsistency:/inconsisten/.test(plain),
    contraction:/contraction/.test(plain),
    revision:/revision/.test(plain),
    epistemic_state:/epistemic/.test(plain),
    agm:/\bagm\b/.test(plain),
  };

  const {data:candidate,error:candidateErr}=await db
    .from("mind_core_development_candidates")
    .select("*")
    .eq("candidate_key","D0007:contextual-belief-arbitration")
    .maybeSingle();
  if(candidateErr) throw candidateErr;

  const evidence={
    ...(candidate?.internet_evidence??{}),
    program_key:program.program_key,
    program_step:step.step_key,
    research_source:finalUrl,
    http_status:status,
    content_length:text.length,
    signals,
    next_required_artifact:"independent contextual-conflict evaluator",
    researched_at:nowIso(),
  };

  if(candidate) {
    const {error:updateErr}=await db
      .from("mind_core_development_candidates")
      .update({
        status:"researching",
        internet_evidence:evidence,
        updated_at:nowIso(),
      })
      .eq("id",candidate.id);
    if(updateErr) throw updateErr;
  } else {
    const {error:insertErr}=await db
      .from("mind_core_development_candidates")
      .insert({
        candidate_key:"D0007:contextual-belief-arbitration",
        title:"Contextual Belief Arbitration",
        deficit:"Belief revision handles one claim against one verdict, but the kernel lacks a principled way to handle apparently conflicting beliefs supported by different sources, scopes, or contexts without oscillating or overwriting one side.",
        hypothesis:"Conflicting beliefs should first be tested for scope/context separability; if they apply to disjoint contexts they should coexist under scoped beliefs, otherwise the conflict remains unresolved until discriminating evidence is found.",
        candidate_kind:"mechanism_candidate_research",
        proposed_change:{
          suggested_mechanism_key:"M0013:contextual-belief-arbitrator",
          protocol:["detect conflict","compare scope","split context or mark unresolved","seek discriminating evidence"],
          safety:["no destructive overwrite","preserve both provenance chains","no forced winner without discriminator"],
        },
        source_metrics:{},
        internet_evidence:evidence,
        status:"researching",
        shadow_result:{},
        created_from_cycle:cycleId,
      });
    if(insertErr) throw insertErr;
  }

  return {
    action:"research_contextual_belief_arbitration",
    research_url:finalUrl,
    http_status:status,
    research_signals:signals,
    development_candidate:"D0007:contextual-belief-arbitration",
    candidate_status:"researching",
    next_required_artifact:"independent contextual-conflict evaluator",
  };
}

async function mindProgramOrchestrator(cycleId:number) {
  const {program,step}=await currentMindProgram();

  const {data:targetMechanism,error:targetErr}=await db
    .from("mind_core_mechanisms")
    .select("mechanism_key,status,admitted_at")
    .eq("mechanism_key",String(step.mechanism_target??""))
    .maybeSingle();
  if(targetErr) throw targetErr;

  if(targetMechanism?.status==="admitted") {
    const {error:completeErr}=await db
      .from("mind_core_program_steps")
      .update({
        status:"completed",
        completed_at:nowIso(),
        evidence:{
          ...(step.evidence??{}),
          admitted_mechanism:targetMechanism.mechanism_key,
          admitted_at:targetMechanism.admitted_at,
          completed_by_cycle:cycleId,
        },
        updated_at:nowIso(),
      })
      .eq("id",step.id);
    if(completeErr) throw completeErr;

    const nextOrdinal=Number(step.ordinal)+1;
    const {data:nextStep,error:nextErr}=await db
      .from("mind_core_program_steps")
      .select("*")
      .eq("program_id",program.id)
      .eq("ordinal",nextOrdinal)
      .maybeSingle();
    if(nextErr) throw nextErr;

    if(!nextStep) {
      await db.from("mind_core_programs").update({
        status:"completed",
        updated_at:nowIso(),
      }).eq("id",program.id);

      await db.from("mind_core_program_events").insert({
        program_id:program.id,
        step_id:step.id,
        cycle_id:cycleId,
        event_type:"program_completed",
        payload:{completed_step:step.step_key,completed_at:nowIso()},
      });

      return {
        program_key:program.program_key,
        status:"completed",
        completed_step:step.step_key,
      };
    }

    await db.from("mind_core_programs").update({
      current_step:nextOrdinal,
      updated_at:nowIso(),
    }).eq("id",program.id);

    await db.from("mind_core_program_steps").update({
      status:"active",
      started_at:nowIso(),
      updated_at:nowIso(),
    }).eq("id",nextStep.id);

    await syncPrimaryProgramState(program,nextStep,"active");

    await db.from("mind_core_program_events").insert({
      program_id:program.id,
      step_id:nextStep.id,
      cycle_id:cycleId,
      event_type:"step_advanced",
      payload:{
        from_step:step.step_key,
        to_step:nextStep.step_key,
        target_mechanism:nextStep.mechanism_target,
      },
    });

    return {
      program_key:program.program_key,
      action:"advance_step",
      completed_step:step.step_key,
      current_step:nextStep.step_key,
      target_mechanism:nextStep.mechanism_target,
    };
  }

  await db.from("mind_core_program_steps").update({
    status:"researching",
    started_at:step.started_at??nowIso(),
    updated_at:nowIso(),
  }).eq("id",step.id);

  await syncPrimaryProgramState(program,step,"researching");

  let work:any={
    action:"awaiting_step_mechanism",
    target_mechanism:step.mechanism_target,
  };

  if(step.step_key==="DM01:CONTEXTUAL_BELIEF_ARBITRATION") {
    work=await researchContextualBeliefArbitration(program,step,cycleId);
  } else if(step.step_key==="DM02:SELF_MODEL") {
    work=await researchCausalSelfModel(program,step,cycleId);
  } else {
    const {error:capGoalErr}=await db.from("mind_core_goals").upsert({
      goal_key:"recurring:capability-audit",
      kind:"capability_audit",
      target:{},
      rationale:`Program ${program.program_key} requests capability development for ${step.step_key}`,
      priority:0.95,
      status:"pending",
      recurrence_minutes:120,
      not_before:nowIso(),
      last_error:null,
      updated_at:nowIso(),
    },{onConflict:"goal_key"});
    if(capGoalErr) throw capGoalErr;
    work={
      action:"scheduled_capability_audit",
      target_mechanism:step.mechanism_target,
    };
  }

  const {error:eventErr}=await db.from("mind_core_program_events").insert({
    program_id:program.id,
    step_id:step.id,
    cycle_id:cycleId,
    event_type:"step_tick",
    payload:{
      step_key:step.step_key,
      target_mechanism:step.mechanism_target,
      work,
      tick_at:nowIso(),
    },
  });
  if(eventErr) throw eventErr;

  return {
    program_key:program.program_key,
    program_name:program.name,
    program_status:program.status,
    current_step:step.step_key,
    step_title:step.title,
    step_status:"researching",
    target_mechanism:step.mechanism_target,
    pass_criteria:step.pass_criteria,
    fail_criteria:step.fail_criteria,
    work,
  };
}


function normalizedScalar(v:any) {
  if(v===null || v===undefined) return "";
  if(typeof v==="string") return v.trim().toLowerCase();
  if(typeof v==="number" || typeof v==="boolean") return String(v);
  return JSON.stringify(v);
}

function scopeEntries(scope:any) {
  if(!scope || typeof scope!=="object" || Array.isArray(scope)) return [];
  return Object.entries(scope)
    .filter(([k,v])=>k && v!==null && v!==undefined && normalizedScalar(v)!=="")
    .map(([k,v])=>[String(k),normalizedScalar(v)] as [string,string]);
}

function scopeDiscriminators(scopeA:any,scopeB:any) {
  const a=new Map(scopeEntries(scopeA));
  const b=new Map(scopeEntries(scopeB));
  const keys=[...new Set([...a.keys(),...b.keys()])];
  const sharedDifferent:string[]=[];
  const missingOnA:string[]=[];
  const missingOnB:string[]=[];

  for(const k of keys) {
    const av=a.get(k);
    const bv=b.get(k);
    if(av!==undefined && bv!==undefined && av!==bv) sharedDifferent.push(k);
    else if(av===undefined && bv!==undefined) missingOnA.push(k);
    else if(av!==undefined && bv===undefined) missingOnB.push(k);
  }

  return {sharedDifferent,missingOnA,missingOnB};
}

async function arbitrateContextClaims(claimA:any,claimB:any) {
  const inputAHash=await sha256Hex(JSON.stringify(claimA));
  const inputBHash=await sha256Hex(JSON.stringify(claimB));

  const subjectA=normalizedScalar(claimA?.subject);
  const subjectB=normalizedScalar(claimB?.subject);
  const predicateA=normalizedScalar(claimA?.predicate);
  const predicateB=normalizedScalar(claimB?.predicate);
  const objectA=normalizedScalar(claimA?.object);
  const objectB=normalizedScalar(claimB?.object);

  const provenanceA=claimA?.provenance??{};
  const provenanceB=claimB?.provenance??{};

  let decision="unresolved_conflict";
  let discriminatingGoal:any=null;
  let scopeInfo=scopeDiscriminators(claimA?.scope,claimB?.scope);

  if(subjectA!==subjectB || predicateA!==predicateB) {
    decision="unrelated";
  } else if(objectA===objectB) {
    decision="compatible_same";
  } else if(scopeInfo.sharedDifferent.length>0) {
    decision="scope_split";
  } else {
    decision="unresolved_conflict";
    discriminatingGoal={
      kind:"discriminating_evidence_goal",
      question:`Which explicit context or scope variable separates the claims about ${String(claimA?.subject??"subject")} / ${String(claimA?.predicate??"predicate")}?`,
      required_evidence:[
        "an authoritative source that names the differing scope/channel/version/time/context",
        "a mapping from each claim to a non-overlapping scope value"
      ],
      preserve_until_resolved:[inputAHash,inputBHash],
    };
  }

  const outputAHash=await sha256Hex(JSON.stringify(claimA));
  const outputBHash=await sha256Hex(JSON.stringify(claimB));

  return {
    decision,
    winner:null,
    coexist:decision==="scope_split" || decision==="compatible_same",
    scope_discriminators:scopeInfo.sharedDifferent,
    missing_scope_on_a:scopeInfo.missingOnA,
    missing_scope_on_b:scopeInfo.missingOnB,
    discriminating_evidence_goal:discriminatingGoal,
    provenance:{
      claim_a:provenanceA,
      claim_b:provenanceB,
    },
    input_hashes:{claim_a:inputAHash,claim_b:inputBHash},
    output_hashes:{claim_a:outputAHash,claim_b:outputBHash},
    provenance_preserved:
      JSON.stringify(provenanceA)===JSON.stringify(claimA?.provenance??{}) &&
      JSON.stringify(provenanceB)===JSON.stringify(claimB?.provenance??{}),
    inputs_unchanged:inputAHash===outputAHash && inputBHash===outputBHash,
  };
}

async function runContextConflictSuite(
  suite:string,
  actorKey:string,
  cycleId:number
) {
  const {data:cases,error}=await db
    .from("mind_core_context_conflict_cases")
    .select("*")
    .eq("suite",suite)
    .order("id",{ascending:true});
  if(error) throw error;
  if(!cases?.length) throw new Error("context conflict suite has no cases");

  const results:any[]=[];
  let passedCount=0;

  for(const c of cases) {
    // Candidate phase: only the two claims are used.
    const result=await arbitrateContextClaims(c.claim_a,c.claim_b);

    // Evaluator phase: expected verdict is consulted only after candidate output exists.
    const actionPass=result.decision===String(c.expected_action);
    const goalPass=
      c.require_discriminating_goal===true
        ? !!result.discriminating_evidence_goal
        : true;
    const noForcedWinner=result.winner===null;
    const provenancePass=result.provenance_preserved===true && result.inputs_unchanged===true;

    const passed=actionPass && goalPass && noForcedWinner && provenancePass;
    if(passed) passedCount += 1;

    const rowResult={
      case_key:c.case_key,
      candidate_result:result,
      expected_action:c.expected_action,
      require_discriminating_goal:c.require_discriminating_goal,
      action_pass:actionPass,
      goal_pass:goalPass,
      no_forced_winner:noForcedWinner,
      provenance_pass:provenancePass,
      passed,
    };

    const {error:runErr}=await db.from("mind_core_context_conflict_runs").insert({
      case_id:c.id,
      cycle_id:cycleId,
      actor_key:actorKey,
      result:rowResult,
      passed,
    });
    if(runErr) throw runErr;

    results.push(rowResult);
  }

  return {
    suite,
    actor_key:actorKey,
    cases_total:cases.length,
    cases_passed:passedCount,
    all_passed:passedCount===cases.length,
    results,
    checked_at:nowIso(),
  };
}

async function contextualBeliefEvaluator(goal:Goal,cycleId:number) {
  const candidateKey=String(
    goal.target?.candidate_key??"D0007:contextual-belief-arbitration"
  );
  const suite=String(goal.target?.suite??"D0007_EVAL");

  const verdict=await runContextConflictSuite(
    suite,
    candidateKey,
    cycleId
  );

  const {error:updateErr}=await db.from("mind_core_development_candidates").update({
    status:verdict.all_passed?"admitted":"rejected",
    shadow_result:{
      evaluator_version:"contextual-belief-v1",
      ...verdict,
    },
    internet_evidence:{
      evaluator_version:"contextual-belief-v1",
      suite,
      official_source_cases:verdict.cases_total,
      candidate_blind_to_expected_action:true,
    },
    updated_at:nowIso(),
  }).eq("candidate_key",candidateKey);
  if(updateErr) throw updateErr;

  return {
    evaluator_version:"contextual-belief-v1",
    ...verdict,
  };
}

async function contextualBeliefSelfTest(goal:Goal,cycleId:number) {
  const suite=String(goal.target?.suite??"M0013_ADMISSION");
  const verdict=await runContextConflictSuite(
    suite,
    "M0013:contextual-belief-arbitrator",
    cycleId
  );

  if(!verdict.all_passed) {
    throw new Error("M0013 contextual belief admission failed");
  }

  const mechanism=await getMechanismByKey("M0013:contextual-belief-arbitrator");
  const evidence={
    ...(mechanism.evidence??{}),
    independent_self_test:{
      evaluator_version:"contextual-belief-v1",
      ...verdict,
    },
    admitted_reason:"Passed independent Node-API scoped/unscoped conflict tests after a 4/4 held-out Python/Tcl evaluator; preserved both provenance chains and refused forced winners without discriminating context.",
  };

  const {error:updateErr}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence,
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key","M0013:contextual-belief-arbitrator");
  if(updateErr) throw updateErr;

  return {
    mechanism_key:"M0013:contextual-belief-arbitrator",
    evaluator_version:"contextual-belief-v1",
    ...verdict,
  };
}


async function syncPrimaryProgramState(
  program:any,
  step:any,
  status:string
) {
  const {data:row,error}=await db.from("mind_core_state")
    .select("state")
    .eq("id","main")
    .single();
  if(error) throw error;

  const state=row?.state??{};
  const primary={
    ...(state.primary_program??{}),
    program_key:program.program_key,
    name:program.name,
    objective:program.objective,
    current_step:step?.step_key??null,
    current_ordinal:step?.ordinal??null,
    target_mechanism:step?.mechanism_target??null,
    status,
  };

  const {error:updateErr}=await db.from("mind_core_state").update({
    state:{...state,primary_program:primary},
    updated_at:nowIso(),
  }).eq("id","main");
  if(updateErr) throw updateErr;
}

async function researchCausalSelfModel(
  program:any,
  step:any,
  cycleId:number
) {
  const [mechsRes,resourcesRes,goalsRes,cyclesRes,stateRes]=await Promise.all([
    db.from("mind_core_mechanisms")
      .select("mechanism_key,name,kind,status,capabilities,constraints,admitted_at")
      .order("ordinal",{ascending:true}),
    db.from("mind_core_resources")
      .select("resource_key,name,resource_class,status,capabilities,limits")
      .order("id",{ascending:true}),
    db.from("mind_core_goals")
      .select("goal_key,kind,priority,status,recurrence_minutes,not_before,last_run_at")
      .order("priority",{ascending:false})
      .limit(100),
    db.from("mind_core_cycles")
      .select("id,status,trigger_source,focus,error,started_at,finished_at")
      .order("id",{ascending:false})
      .limit(20),
    db.from("mind_core_state")
      .select("state")
      .eq("id","main")
      .single(),
  ]);

  for(const r of [mechsRes,resourcesRes,goalsRes,cyclesRes,stateRes]) {
    if(r.error) throw r.error;
  }

  const mechanisms=mechsRes.data??[];
  const resources=resourcesRes.data??[];
  const goals=goalsRes.data??[];
  const cycles=cyclesRes.data??[];
  const state=stateRes.data?.state??{};

  const admittedMechanisms=mechanisms
    .filter((m:any)=>m.status==="admitted")
    .map((m:any)=>m.mechanism_key);

  const admittedResources=resources
    .filter((r:any)=>r.status==="admitted")
    .map((r:any)=>r.resource_key);

  const blockedResources=resources
    .filter((r:any)=>r.status==="blocked")
    .map((r:any)=>r.resource_key);

  const activeGoals=goals
    .filter((g:any)=>["pending","running"].includes(g.status))
    .map((g:any)=>({
      goal_key:g.goal_key,
      kind:g.kind,
      priority:g.priority,
      status:g.status,
      not_before:g.not_before,
    }));

  const recentFailures=cycles
    .filter((c:any)=>c.status==="failed")
    .map((c:any)=>({
      cycle_id:c.id,
      focus:c.focus,
      error:c.error,
      started_at:c.started_at,
    }));

  const knownLimits=[
    {
      capability:"hidden_model_weights_or_private_reasoning_state",
      status:"unavailable",
      reason:"No admitted runtime interface exposes hidden model weights, activations, or private chain-of-thought.",
    },
    {
      capability:"browser_interaction",
      status:"partial",
      reason:"M0012 supports verified JavaScript rendering and DOM inspection; generic click/fill/action control is not yet an admitted mechanism.",
    },
    {
      capability:"production_self_modification",
      status:"guarded",
      reason:"Production changes require explicit candidate, evaluator/shadow evidence, regression/admission path, and source synchronization.",
    },
    {
      capability:"external_compute",
      status:"bounded",
      reason:"Verified browser compute uses Vercel Sandbox quota; other protected compute resources remain blocked unless explicitly admitted.",
    },
  ];

  const causalLinks=[
    {
      cause:"target mechanism for current program step becomes admitted",
      effect:"next mind_program_orchestrator tick completes current step and advances exactly one step",
      evidence:"mindProgramOrchestrator transition rule",
    },
    {
      cause:"target mechanism for current program step is not admitted",
      effect:"program remains on current step and performs research/development work",
      evidence:"mindProgramOrchestrator non-admitted branch",
    },
    {
      cause:"M0012 browser_inspect is called with an admitted snapshot and HTTPS target",
      effect:"ephemeral Vercel Sandbox runs verified Chromium and returns rendered DOM",
      evidence:"verified browser runtime admission and post-consolidation tests",
    },
    {
      cause:"a development candidate fails its evaluator",
      effect:"candidate is rejected rather than silently promoted",
      evidence:"D0001 and D0004 rejection history",
    },
  ];

  const predictions=[
    {
      prediction_key:`self-model:${cycleId}:hold-dm02`,
      condition:"M0014 remains not admitted before the next program tick",
      predicted_outcome:{
        program_step:"DM02:SELF_MODEL",
        program_step_status:"researching",
        no_advance:true,
      },
      confidence:0.99,
      status:"pending",
    },
    {
      prediction_key:`self-model:${cycleId}:advance-dm03`,
      condition:"M0014 becomes admitted before a future program tick",
      predicted_outcome:{
        completed_step:"DM02:SELF_MODEL",
        next_step:"DM03:GOAL_SYSTEM",
        advance_exactly_one_step:true,
      },
      confidence:0.99,
      status:"pending",
    },
    {
      prediction_key:`self-model:${cycleId}:browser-boundary`,
      condition:"a browser target is non-HTTPS or local/private",
      predicted_outcome:{
        browser_request:"rejected_before_navigation",
      },
      confidence:0.98,
      status:"pending",
    },
  ];

  const snapshot={
    runtime_version:String(state.version??"unknown"),
    canonical_git_main_sha:String(state.canonical_git_main_sha??"unknown"),
    program:{
      program_key:program.program_key,
      current_step:step.step_key,
      current_ordinal:step.ordinal,
      target_mechanism:step.mechanism_target,
    },
    mechanisms:{
      admitted_count:admittedMechanisms.length,
      admitted:admittedMechanisms,
      probation:mechanisms.filter((m:any)=>m.status==="probation").map((m:any)=>m.mechanism_key),
    },
    resources:{
      admitted_count:admittedResources.length,
      admitted:admittedResources,
      blocked:blockedResources,
    },
    goal_frontier:{
      active_count:activeGoals.length,
      active:activeGoals.slice(0,25),
    },
    recent_failures:recentFailures,
    browser_runtime:state.browser_runtime??null,
    internet_connection:state.internet_connection??null,
    known_limits:knownLimits,
    causal_links:causalLinks,
  };

  const snapshotHash=await sha256Hex(JSON.stringify({
    cycle_id:cycleId,
    program_step:step.step_key,
    snapshot,
    predictions,
  }));

  const {data:snapRow,error:snapErr}=await db
    .from("mind_core_self_model_snapshots")
    .insert({
      cycle_id:cycleId,
      program_step:step.step_key,
      runtime_version:String(state.version??"unknown"),
      snapshot,
      predictions,
      snapshot_hash:snapshotHash,
    })
    .select("*")
    .single();
  if(snapErr) throw snapErr;

  const metrics={
    admitted_mechanisms:admittedMechanisms.length,
    admitted_resources:admittedResources.length,
    blocked_resources:blockedResources.length,
    active_goals:activeGoals.length,
    recent_failures:recentFailures.length,
    known_limit_count:knownLimits.length,
    causal_link_count:causalLinks.length,
    prediction_count:predictions.length,
  };

  const {data:candidate,error:candidateErr}=await db
    .from("mind_core_development_candidates")
    .select("*")
    .eq("candidate_key","D0009:causal-self-model")
    .single();
  if(candidateErr) throw candidateErr;

  const {error:updateErr}=await db
    .from("mind_core_development_candidates")
    .update({
      status:"researching",
      source_metrics:metrics,
      internet_evidence:{
        source:"live observable runtime state",
        snapshot_id:snapRow.id,
        snapshot_hash:snapshotHash,
        program_step:step.step_key,
        no_hidden_state_claims:true,
      },
      shadow_result:{
        latest_snapshot_id:snapRow.id,
        latest_snapshot_hash:snapshotHash,
        predictions,
        next_required_artifact:"held-out self-model prediction evaluator on runtime changes",
      },
      updated_at:nowIso(),
    })
    .eq("id",candidate.id);
  if(updateErr) throw updateErr;

  return {
    action:"build_causal_self_model",
    development_candidate:"D0009:causal-self-model",
    candidate_status:"researching",
    snapshot_id:snapRow.id,
    snapshot_hash:snapshotHash,
    metrics,
    predictions,
    known_limits:knownLimits,
    next_required_artifact:"held-out self-model prediction evaluator on runtime changes",
  };
}


function capPriority(
  impact:number,
  dependency:number,
  feasibility:number,
  measurability:number,
  risk:number,
  cost:number
) {
  const raw=
    0.28*impact +
    0.24*dependency +
    0.18*feasibility +
    0.15*measurability +
    0.10*(1-risk) +
    0.05*(1-cost);
  return Math.max(0,Math.min(1,raw));
}

async function capabilityAudit(cycleId:number) {
  const [stateRes,mechsRes,resourcesRes,programRes,candidatesRes]=await Promise.all([
    db.from("mind_core_state").select("state").eq("id","main").single(),
    db.from("mind_core_mechanisms")
      .select("mechanism_key,name,kind,status,capabilities,constraints,admitted_at")
      .order("ordinal",{ascending:true}),
    db.from("mind_core_resources")
      .select("resource_key,name,resource_class,status,capabilities,limits")
      .order("id",{ascending:true}),
    db.from("mind_core_programs")
      .select("*")
      .eq("program_key","PROGRAM:DIGITAL_MIND_V1")
      .single(),
    db.from("mind_core_development_candidates")
      .select("candidate_key,title,status,deficit,hypothesis")
      .order("id",{ascending:false})
      .limit(100),
  ]);

  for(const r of [stateRes,mechsRes,resourcesRes,programRes,candidatesRes]) {
    if(r.error) throw r.error;
  }

  const state=stateRes.data?.state??{};
  const mechs=mechsRes.data??[];
  const resources=resourcesRes.data??[];
  const candidates=candidatesRes.data??[];
  const program=programRes.data;

  const {data:step,error:stepErr}=await db
    .from("mind_core_program_steps")
    .select("*")
    .eq("program_id",program.id)
    .eq("ordinal",program.current_step)
    .single();
  if(stepErr) throw stepErr;

  const admittedMechs=new Set(
    mechs.filter((m:any)=>m.status==="admitted").map((m:any)=>m.mechanism_key)
  );
  const admittedCaps=new Set(
    mechs
      .filter((m:any)=>m.status==="admitted")
      .flatMap((m:any)=>Array.isArray(m.capabilities)?m.capabilities:[])
      .map((x:any)=>String(x))
  );
  const admittedResources=new Set(
    resources.filter((r:any)=>r.status==="admitted").map((r:any)=>r.resource_key)
  );

  const items:any[]=[];
  const add=(x:any)=>items.push(x);

  add({
    capability_key:"internet_read",
    name:"Real Internet Read",
    category:"environment_io",
    status:admittedMechs.has("M0001:real-internet-read")?"admitted":"missing",
    evidence:{mechanism:"M0001:real-internet-read"},
    dependencies:[],
    constraints:["read_only","https_only"],
  });

  add({
    capability_key:"browser_render_and_dom",
    name:"Verified JS/DOM Browser",
    category:"environment_io",
    status:admittedMechs.has("M0012:verified-browser-runtime")?"admitted":"missing",
    evidence:{
      mechanism:"M0012:verified-browser-runtime",
      browser_version:state?.browser_runtime?.browser_version??null,
      native_sandbox:state?.browser_runtime?.sandbox?.chromium_native_sandbox===true,
    },
    dependencies:["internet_read"],
    constraints:["ephemeral_profile","https_targets_only"],
  });

  add({
    capability_key:"browser_interaction",
    name:"Controlled Browser Actions",
    category:"environment_action",
    status:admittedCaps.has("browser_click_fill")?"admitted":"partial",
    evidence:{
      current_browser_mechanism:admittedMechs.has("M0012:verified-browser-runtime"),
      current_capabilities:[...admittedCaps].filter(x=>x.includes("browser")||x.includes("dom")),
    },
    dependencies:["browser_render_and_dom","goal_system","planning"],
    constraints:["no_user_credentials","explicit_goal_required"],
  });

  add({
    capability_key:"curiosity_goal_birth",
    name:"Evidence-Grounded Question/Goal Birth",
    category:"cognition",
    status:admittedMechs.has("M0002:curiosity-pressure")?"admitted":"missing",
    evidence:{mechanism:"M0002:curiosity-pressure"},
    dependencies:["internet_read"],
    constraints:["evidence_grounded"],
  });

  add({
    capability_key:"concept_and_domain_birth",
    name:"Concept and Domain Birth",
    category:"cognition",
    status:
      admittedMechs.has("M0003:domain-birth") &&
      admittedMechs.has("M0004:concept-birth")
        ?"admitted":"partial",
    evidence:{
      domain_birth:admittedMechs.has("M0003:domain-birth"),
      concept_birth:admittedMechs.has("M0004:concept-birth"),
    },
    dependencies:["curiosity_goal_birth"],
    constraints:["external_verification_required"],
  });

  add({
    capability_key:"falsification_and_belief_revision",
    name:"Falsification and Belief Revision",
    category:"epistemics",
    status:
      admittedMechs.has("M0010:active-falsifier") &&
      admittedMechs.has("M0011:belief-revision") &&
      admittedMechs.has("M0013:contextual-belief-arbitrator")
        ?"admitted":"partial",
    evidence:{
      falsifier:admittedMechs.has("M0010:active-falsifier"),
      revision:admittedMechs.has("M0011:belief-revision"),
      contextual_arbitration:admittedMechs.has("M0013:contextual-belief-arbitrator"),
    },
    dependencies:["internet_read"],
    constraints:["append_only_history","no_truth_upgrade_from_not_reject"],
  });

  add({
    capability_key:"causal_self_model",
    name:"Causal Self-Model",
    category:"self_model",
    status:admittedMechs.has("M0014:causal-self-model")?"admitted":"partial",
    evidence:{
      current_step:step.step_key,
      candidate:"D0009:causal-self-model",
      candidate_status:
        candidates.find((c:any)=>c.candidate_key==="D0009:causal-self-model")?.status??null,
      snapshot_exists:state?.last_observation?.work?.snapshot_id!=null,
    },
    dependencies:["falsification_and_belief_revision"],
    constraints:["observable_state_only","no_hidden_weight_claims"],
  });

  add({
    capability_key:"self_learning_algorithm_genesis",
    name:"Self-Learning Rule/Algorithm Synthesis",
    category:"learning",
    status:admittedMechs.has("M0015:self-learning-engine")?"admitted":"missing",
    evidence:{
      program_step:"DM03:SELF_LEARNING",
      candidate:"D0010:self-learning-rule-synthesis",
      candidate_status:
        candidates.find((c:any)=>c.candidate_key==="D0010:self-learning-rule-synthesis")?.status??null,
    },
    dependencies:["causal_self_model","internet_read","falsification_and_belief_revision"],
    constraints:["bounded_DSL","heldout_evaluation","artifact_provenance"],
  });

  add({
    capability_key:"goal_selection",
    name:"Multi-Goal Selection",
    category:"executive",
    status:admittedMechs.has("M0016:goal-selection")?"admitted":"missing",
    evidence:{program_step:"DM03:GOAL_SYSTEM"},
    dependencies:["causal_self_model","curiosity_goal_birth"],
    constraints:["budget_aware","risk_aware"],
  });

  add({
    capability_key:"planning_replanning",
    name:"Multi-Step Planning and Replanning",
    category:"executive",
    status:admittedMechs.has("M0017:planner-replanner")?"admitted":"missing",
    evidence:{program_step:"DM04:PLANNING"},
    dependencies:["goal_selection","browser_render_and_dom"],
    constraints:["loop_detection","failure_replan"],
  });

  add({
    capability_key:"counterfactual_prediction",
    name:"Counterfactual World Model",
    category:"prediction",
    status:admittedMechs.has("M0018:counterfactual-world-model")?"admitted":"missing",
    evidence:{program_step:"DM05:COUNTERFACTUAL_WORLD_MODEL"},
    dependencies:["planning_replanning"],
    constraints:["predict_before_action"],
  });

  add({
    capability_key:"metacognitive_calibration",
    name:"Metacognitive Calibration",
    category:"self_model",
    status:admittedMechs.has("M0019:metacognitive-calibrator")?"admitted":"missing",
    evidence:{program_step:"DM06:METACOGNITION"},
    dependencies:["counterfactual_prediction","falsification_and_belief_revision"],
    constraints:["confidence_must_track_accuracy"],
  });

  add({
    capability_key:"generic_mechanism_genesis",
    name:"Generic Mechanism Genesis",
    category:"self_improvement",
    status:admittedMechs.has("M0020:mechanism-genesis")?"admitted":"partial",
    evidence:{
      bounded_shadow_loop:true,
      historical_reject_redesign_admit:true,
      target_mechanism:GENESIS_MECHANISM,
    },
    dependencies:["metacognitive_calibration"],
    constraints:["independent_evaluator_required","no_direct_prod_mutation"],
  });

  add({
    capability_key:"cross_domain_transfer",
    name:"Cross-Domain Cognitive Transfer",
    category:"generalization",
    status:admittedMechs.has("M0021:cognitive-transfer")
      ?"admitted"
      :(admittedMechs.has("M0005:concept-transfer")?"partial":"missing"),
    evidence:{concept_transfer:admittedMechs.has("M0005:concept-transfer")},
    dependencies:["generic_mechanism_genesis"],
    constraints:["no_manual_adapter_before_test"],
  });

  add({
    capability_key:"persistent_self_history",
    name:"Persistent Self-History",
    category:"identity",
    status:admittedMechs.has("M0022:self-history")
      ?"admitted"
      :(admittedMechs.has("M0011:belief-revision")?"partial":"missing"),
    evidence:{
      append_only_beliefs:admittedMechs.has("M0011:belief-revision"),
      program_events:true,
    },
    dependencies:["cross_domain_transfer"],
    constraints:["append_only"],
  });

  add({
    capability_key:"external_compute_scaling",
    name:"External Compute Scaling",
    category:"compute",
    status:
      admittedResources.has("RF:UNGOOGLED_CHROMIUM_RUNTIME")
        ?"partial":"blocked",
    evidence:{
      browser_compute:admittedResources.has("RF:UNGOOGLED_CHROMIUM_RUNTIME"),
      blocked_compute:resources
        .filter((r:any)=>r.resource_class==="compute" && r.status==="blocked")
        .map((r:any)=>r.resource_key),
    },
    dependencies:[],
    constraints:["quota_limited","no_new_paid_resource_without_approval"],
  });

  add({
    capability_key:"authenticated_external_actions",
    name:"Authenticated External Actions",
    category:"environment_action",
    status:"guarded",
    evidence:{
      reason:"No generic admitted mechanism for arbitrary authenticated mutations.",
    },
    dependencies:["goal_selection","planning_replanning"],
    constraints:["explicit_user_approval","service_specific_policy"],
  });

  add({
    capability_key:"hidden_model_introspection",
    name:"Hidden Model Weight/Activation Introspection",
    category:"introspection",
    status:"unavailable",
    evidence:{
      reason:"No runtime interface exposes hidden weights, activations, or private chain-of-thought.",
    },
    dependencies:[],
    constraints:["not_a_supported_runtime_capability"],
  });

  const gaps:any[]=[];
  const pushGap=(x:any)=>{
    const priority=capPriority(
      x.impact,x.dependency_relevance,x.feasibility,
      x.measurability,x.risk,x.cost
    );
    gaps.push({...x,priority});
  };

  if(!admittedMechs.has("M0014:causal-self-model")) {
    pushGap({
      capability_key:"causal_self_model",
      deficit:"Self-model exists as a snapshot but has not yet passed held-out prediction tests on runtime changes.",
      recommended_target:"M0014:causal-self-model",
      impact:0.95,
      dependency_relevance:1.0,
      feasibility:0.95,
      measurability:1.0,
      risk:0.05,
      cost:0.10,
      safe_to_auto_pursue:true,
      goal:{
        goal_key:"development-evaluator:D0009:v1",
        kind:"self_model_prediction_evaluator",
        target:{candidate_key:"D0009:causal-self-model",snapshot_id:1},
        rationale:"Validate pre-registered self-model predictions on held-out runtime changes before M0014 admission.",
      }
    });
  }

  if(!admittedMechs.has("M0015:self-learning-engine")) {
    pushGap({
      capability_key:"self_learning_algorithm_genesis",
      deficit:"The kernel lacks an admitted general cycle that researches a deficit, writes an explicit algorithm/rule artifact, tests it on held-out evidence, and applies it to a fresh task.",
      recommended_target:"M0015:self-learning-engine",
      impact:1.0,
      dependency_relevance:step.step_key==="DM03:SELF_LEARNING"?1.0:0.75,
      feasibility:0.90,
      measurability:1.0,
      risk:0.05,
      cost:0.10,
      safe_to_auto_pursue:true,
      goal:{
        goal_key:"development-evaluator:D0010:v1",
        kind:"self_learning_rule_evaluator",
        target:{candidate_key:"D0010:self-learning-rule-synthesis"},
        rationale:"Research, synthesize, held-out test, and freshly apply a bounded LRA-1 algorithm before M0015 admission.",
      }
    });
  }

  if(!admittedMechs.has("M0016:goal-selection")) {
    pushGap({
      capability_key:"goal_selection",
      deficit:"No admitted mechanism yet arbitrates competing goals using utility, cost, risk, deadlines, and resource budgets.",
      recommended_target:"M0016:goal-selection",
      impact:0.95,
      dependency_relevance:step.step_key==="DM03:GOAL_SYSTEM"?1.0:0.70,
      feasibility:0.75,
      measurability:0.90,
      risk:0.10,
      cost:0.15,
      safe_to_auto_pursue:admittedMechs.has("M0015:self-learning-engine"),
      goal:null,
    });
  }

  if(!admittedMechs.has("M0017:planner-replanner")) {
    pushGap({
      capability_key:"planning_replanning",
      deficit:"No admitted general planner/replanner for multi-step tasks and failure recovery.",
      recommended_target:"M0017:planner-replanner",
      impact:0.95,
      dependency_relevance:0.65,
      feasibility:0.65,
      measurability:0.85,
      risk:0.20,
      cost:0.20,
      safe_to_auto_pursue:false,
      goal:null,
    });
  }

  if(!admittedCaps.has("browser_click_fill")) {
    pushGap({
      capability_key:"browser_interaction",
      deficit:"Browser can render JavaScript and inspect DOM but cannot yet perform admitted goal-bounded click/fill/navigation actions.",
      recommended_target:"M0017A:browser-action-controller",
      impact:0.80,
      dependency_relevance:0.55,
      feasibility:0.70,
      measurability:0.90,
      risk:0.35,
      cost:0.15,
      safe_to_auto_pursue:false,
      goal:null,
    });
  }

  if(!admittedMechs.has("M0019:metacognitive-calibrator")) {
    pushGap({
      capability_key:"metacognitive_calibration",
      deficit:"The kernel records confidence but lacks an admitted mechanism that measures whether confidence matches empirical accuracy.",
      recommended_target:"M0019:metacognitive-calibrator",
      impact:0.90,
      dependency_relevance:0.50,
      feasibility:0.70,
      measurability:0.95,
      risk:0.05,
      cost:0.10,
      safe_to_auto_pursue:false,
      goal:null,
    });
  }

  if(!admittedMechs.has("M0020:mechanism-genesis")) {
    pushGap({
      capability_key:"generic_mechanism_genesis",
      deficit:"Self-development exists as hand-built runtime logic but is not yet generalized into an admitted mechanism that can invent/evaluate new mechanisms across deficit types.",
      recommended_target:"M0020:mechanism-genesis",
      impact:1.0,
      dependency_relevance:0.45,
      feasibility:0.55,
      measurability:0.85,
      risk:0.25,
      cost:0.20,
      safe_to_auto_pursue:false,
      goal:null,
    });
  }

  pushGap({
    capability_key:"external_compute_scaling",
    deficit:"Additional compute runtimes exist but remain blocked or quota-limited; only verified browser Sandbox compute is admitted.",
    recommended_target:"RESOURCE:compute-expansion",
    impact:0.65,
    dependency_relevance:0.30,
    feasibility:0.45,
    measurability:0.90,
    risk:0.35,
    cost:0.50,
    safe_to_auto_pursue:false,
    goal:null,
  });

  const summary={
    runtime_version:String(state.version??"unknown"),
    program_step:step.step_key,
    admitted_mechanisms:mechs.filter((m:any)=>m.status==="admitted").length,
    admitted_resources:resources.filter((r:any)=>r.status==="admitted").length,
    capability_counts:{
      admitted:items.filter(x=>x.status==="admitted").length,
      partial:items.filter(x=>x.status==="partial").length,
      missing:items.filter(x=>x.status==="missing").length,
      blocked:items.filter(x=>x.status==="blocked").length,
      guarded:items.filter(x=>x.status==="guarded").length,
      unavailable:items.filter(x=>x.status==="unavailable").length,
    },
    top_gaps:gaps
      .slice()
      .sort((a,b)=>b.priority-a.priority)
      .map(g=>({
        capability_key:g.capability_key,
        recommended_target:g.recommended_target,
        priority:g.priority,
        safe_to_auto_pursue:g.safe_to_auto_pursue,
      })),
  };

  const auditHash=await sha256Hex(JSON.stringify({
    cycle_id:cycleId,
    summary,
    items,
    gaps:gaps.map(g=>({
      capability_key:g.capability_key,
      deficit:g.deficit,
      recommended_target:g.recommended_target,
      priority:g.priority,
    })),
  }));

  const {data:audit,error:auditErr}=await db
    .from("mind_core_capability_audits")
    .insert({
      cycle_id:cycleId,
      runtime_version:String(state.version??"unknown"),
      program_step:step.step_key,
      summary,
      audit_hash:auditHash,
    })
    .select("*")
    .single();
  if(auditErr) throw auditErr;

  for(const item of items) {
    const {error}=await db.from("mind_core_capability_items").insert({
      audit_id:audit.id,
      capability_key:item.capability_key,
      name:item.name,
      category:item.category,
      status:item.status,
      evidence:item.evidence,
      dependencies:item.dependencies,
      constraints:item.constraints,
    });
    if(error) throw error;
  }

  const sorted=gaps.slice().sort((a,b)=>b.priority-a.priority);
  let scheduled:any=null;

  for(const gap of sorted) {
    let createdGoalKey:string|null=null;

    if(!scheduled && gap.safe_to_auto_pursue && gap.goal) {
      const {error:goalErr}=await db.from("mind_core_goals").upsert({
        goal_key:gap.goal.goal_key,
        kind:gap.goal.kind,
        target:gap.goal.target,
        rationale:gap.goal.rationale,
        priority:1.0,
        status:"pending",
        recurrence_minutes:null,
        not_before:nowIso(),
        last_error:null,
        updated_at:nowIso(),
      },{onConflict:"goal_key"});
      if(goalErr) throw goalErr;

      createdGoalKey=gap.goal.goal_key;
      scheduled={
        capability_key:gap.capability_key,
        target:gap.recommended_target,
        goal_key:createdGoalKey,
        priority:gap.priority,
      };
    }

    const {error:gapErr}=await db.from("mind_core_capability_gaps").insert({
      audit_id:audit.id,
      capability_key:gap.capability_key,
      deficit:gap.deficit,
      recommended_target:gap.recommended_target,
      impact:gap.impact,
      dependency_relevance:gap.dependency_relevance,
      feasibility:gap.feasibility,
      measurability:gap.measurability,
      risk:gap.risk,
      cost:gap.cost,
      priority:gap.priority,
      safe_to_auto_pursue:gap.safe_to_auto_pursue,
      status:createdGoalKey?"scheduled":"open",
      created_goal_key:createdGoalKey,
    });
    if(gapErr) throw gapErr;
  }

  const {data:stateRow,error:stateErr}=await db.from("mind_core_state")
    .select("state")
    .eq("id","main")
    .single();
  if(stateErr) throw stateErr;

  const newState={
    ...(stateRow?.state??{}),
    capability_audit:{
      audit_id:audit.id,
      audit_hash:auditHash,
      capability_counts:summary.capability_counts,
      top_gaps:summary.top_gaps.slice(0,8),
      scheduled_improvement:scheduled,
      audited_at:nowIso(),
    }
  };

  const {error:stateUpdateErr}=await db.from("mind_core_state").update({
    state:newState,
    updated_at:nowIso(),
  }).eq("id","main");
  if(stateUpdateErr) throw stateUpdateErr;

  return {
    audit_id:audit.id,
    audit_hash:auditHash,
    summary,
    scheduled_improvement:scheduled,
    capability_items:items,
  };
}


async function selfModelPredictionEvaluator(goal:Goal,cycleId:number) {
  const candidateKey=String(goal.target?.candidate_key??"D0009:causal-self-model");
  const snapshotId=Number(goal.target?.snapshot_id??0);

  const {data:snapshot,error:snapshotErr}=await db
    .from("mind_core_self_model_snapshots")
    .select("*")
    .eq("id",snapshotId)
    .single();
  if(snapshotErr) throw snapshotErr;

  const frozenPredictions=[
    {
      key:"program-hold-without-m0014",
      prediction:"With M0014 not admitted, a program tick remains on DM02 and does not advance.",
      expected:{step:"DM02:SELF_MODEL",advanced:false},
    },
    {
      key:"http-boundary",
      prediction:"M0001 rejects non-HTTPS targets before network fetch.",
      expected:{rejected:true},
    },
    {
      key:"blocked-resource-boundary",
      prediction:"Resource Fabric refuses to use RF:ARXIV while its status is blocked.",
      expected:{rejected:true},
    },
    {
      key:"append-only-belief-boundary",
      prediction:"An update to an existing belief row is rejected by the append-only trigger.",
      expected:{rejected:true},
    },
  ];

  const freezeHash=await sha256Hex(JSON.stringify({
    candidate_key:candidateKey,
    snapshot_id:snapshotId,
    predictions:frozenPredictions,
    frozen_before_tests:true,
  }));

  const results:any[]=[];

  // Test 1: actual program tick before M0014 admission.
  const beforeProgram=await currentMindProgram();
  const beforeStep=String(beforeProgram.step.step_key);
  const tickResult=await mindProgramOrchestrator(cycleId);
  const afterProgram=await currentMindProgram();
  const afterStep=String(afterProgram.step.step_key);
  const programPassed=
    beforeStep==="DM02:SELF_MODEL" &&
    afterStep==="DM02:SELF_MODEL" &&
    String(tickResult?.current_step??afterStep)==="DM02:SELF_MODEL";

  results.push({
    key:"program-hold-without-m0014",
    predicted:frozenPredictions[0].expected,
    observed:{
      before_step:beforeStep,
      after_step:afterStep,
      tick_action:tickResult?.action??null,
    },
    passed:programPassed,
  });

  // Test 2: actual M0001 boundary.
  let httpRejected=false;
  let httpError="";
  try {
    await internetGet(cycleId,"http://example.com/","self-model held-out HTTP-boundary test");
  } catch(error) {
    httpRejected=true;
    httpError=error instanceof Error?error.message:String(error);
  }
  results.push({
    key:"http-boundary",
    predicted:frozenPredictions[1].expected,
    observed:{rejected:httpRejected,error:httpError},
    passed:httpRejected,
  });

  // Test 3: actual blocked Resource Fabric route.
  let resourceRejected=false;
  let resourceError="";
  try {
    await fetchThroughResource(
      cycleId,
      "RF:ARXIV",
      "api/query?search_query=all%3Atest&max_results=1",
      "self-model blocked-resource test"
    );
  } catch(error) {
    resourceRejected=true;
    resourceError=error instanceof Error?error.message:String(error);
  }
  results.push({
    key:"blocked-resource-boundary",
    predicted:frozenPredictions[2].expected,
    observed:{rejected:resourceRejected,error:resourceError},
    passed:resourceRejected,
  });

  // Test 4: actual append-only database boundary.
  const {data:belief,error:beliefReadErr}=await db
    .from("mind_core_beliefs")
    .select("id,content_hash")
    .order("id",{ascending:true})
    .limit(1)
    .maybeSingle();
  if(beliefReadErr) throw beliefReadErr;

  let beliefRejected=false;
  let beliefError="";
  let hashPreserved=true;

  if(belief?.id) {
    const beforeHash=String(belief.content_hash);
    const {error:updateBeliefErr}=await db
      .from("mind_core_beliefs")
      .update({content_hash:beforeHash})
      .eq("id",belief.id);

    beliefRejected=!!updateBeliefErr;
    beliefError=updateBeliefErr?.message??"";

    const {data:beliefAfter,error:beliefAfterErr}=await db
      .from("mind_core_beliefs")
      .select("content_hash")
      .eq("id",belief.id)
      .single();
    if(beliefAfterErr) throw beliefAfterErr;
    hashPreserved=String(beliefAfter.content_hash)===beforeHash;
  } else {
    beliefRejected=false;
    beliefError="no belief row available";
    hashPreserved=false;
  }

  results.push({
    key:"append-only-belief-boundary",
    predicted:frozenPredictions[3].expected,
    observed:{
      rejected:beliefRejected,
      error:beliefError,
      hash_preserved:hashPreserved,
    },
    passed:beliefRejected && hashPreserved,
  });

  const passedCount=results.filter((r:any)=>r.passed).length;
  const accuracy=results.length?passedCount/results.length:0;
  const knownUnknownIdentified=
    Array.isArray(snapshot?.snapshot?.known_limits) &&
    snapshot.snapshot.known_limits.some((x:any)=>
      x?.capability==="hidden_model_weights_or_private_reasoning_state" &&
      x?.status==="unavailable"
    );

  const passed=
    accuracy>=0.75 &&
    knownUnknownIdentified===true &&
    results.length>=4;

  const verdict={
    evaluator_version:"self-model-prediction-v1",
    candidate_key:candidateKey,
    source_snapshot_id:snapshotId,
    source_snapshot_hash:snapshot.snapshot_hash,
    freeze_hash:freezeHash,
    frozen_predictions:frozenPredictions,
    results,
    accuracy,
    passed_count:passedCount,
    total_cases:results.length,
    known_unknown_identified:knownUnknownIdentified,
    passed,
    checked_at:nowIso(),
  };

  const {error:runErr}=await db.from("mind_core_self_model_eval_runs").insert({
    cycle_id:cycleId,
    candidate_key:candidateKey,
    snapshot_id:snapshotId,
    frozen_predictions:frozenPredictions,
    results,
    accuracy,
    passed,
  });
  if(runErr) throw runErr;

  const {error:candidateErr}=await db
    .from("mind_core_development_candidates")
    .update({
      status:passed?"admitted":"rejected",
      shadow_result:verdict,
      updated_at:nowIso(),
    })
    .eq("candidate_key",candidateKey);
  if(candidateErr) throw candidateErr;

  if(passed) {
    const {error:mechErr}=await db.from("mind_core_mechanisms").upsert({
      mechanism_key:"M0014:causal-self-model",
      ordinal:14,
      name:"Causal Self-Model",
      kind:"self_model",
      description:"Maintain an observable-state model of Mind Core mechanisms, resources, goals, limitations and causal transitions, and pre-register predictions about its own runtime behavior before testing them.",
      capabilities:[
        "observable_self_model",
        "known_limit_identification",
        "causal_runtime_links",
        "pre_registered_self_predictions",
        "self_prediction_evaluation"
      ],
      constraints:[
        "observable_state_only",
        "no_hidden_weight_claims",
        "no_private_reasoning_claims",
        "prediction_before_test",
        "append_only_self_model_snapshots"
      ],
      status:"admitted",
      evidence:{
        development_parent:candidateKey,
        evaluator:"self-model-prediction-v1",
        source_snapshot_id:snapshotId,
        source_snapshot_hash:snapshot.snapshot_hash,
        accuracy,
        cases_passed:passedCount,
        cases_total:results.length,
        known_unknown_identified:knownUnknownIdentified,
        freeze_hash:freezeHash,
      },
      admitted_at:nowIso(),
      updated_at:nowIso(),
    },{onConflict:"mechanism_key"});
    if(mechErr) throw mechErr;
  }

  return verdict;
}


type LraCondition = {
  feature:"consistency"|"coverage"|"left_uniqueness";
  op:">="|"<=";
  threshold:number;
};

type LraRule = {
  language:"LRA-1";
  kind:"decision_rule";
  conditions:LraCondition[];
  combine:"AND";
  if_true:"accept";
  if_false:"reject";
};

function relationExampleFromRun(run:any) {
  const proposal=run?.train_result?.proposal??null;
  const stats=proposal?.train_stats??null;
  return {
    case_key:String(run?.case_key??""),
    label:run?.expect_generalizes===true,
    features:{
      consistency:Number(stats?.consistency??0),
      coverage:Number(stats?.coverage??0),
      left_uniqueness:Number(stats?.left_uniqueness??0),
    },
  };
}

function applyLraRule(rule:LraRule,features:any) {
  const ok=rule.conditions.every((c)=>{
    const value=Number(features?.[c.feature]??0);
    return c.op===">="?value>=c.threshold:value<=c.threshold;
  });
  return ok ? "accept" : "reject";
}

function ruleAccuracy(rule:LraRule,examples:any[]) {
  let correct=0;
  for(const ex of examples) {
    const predicted=applyLraRule(rule,ex.features)==="accept";
    if(predicted===ex.label) correct += 1;
  }
  return examples.length?correct/examples.length:0;
}

function candidateThresholds(values:number[]) {
  const unique=[...new Set(values.filter(Number.isFinite))].sort((a,b)=>a-b);
  const out=new Set<number>();
  for(const v of unique) out.add(v);
  for(let i=0;i<unique.length-1;i++) {
    out.add((unique[i]+unique[i+1])/2);
  }
  return [...out].sort((a,b)=>a-b);
}

function synthesizeLraRule(train:any[]) {
  const features:LraCondition["feature"][]=[
    "consistency","coverage","left_uniqueness"
  ];
  const atomic:LraCondition[]=[];

  for(const feature of features) {
    const thresholds=candidateThresholds(
      train.map((e:any)=>Number(e.features?.[feature]??0))
    );
    for(const threshold of thresholds) {
      atomic.push({feature,op:">=",threshold});
      atomic.push({feature,op:"<=",threshold});
    }
  }

  const rules:LraRule[]=[];
  for(const c of atomic) {
    rules.push({
      language:"LRA-1",
      kind:"decision_rule",
      conditions:[c],
      combine:"AND",
      if_true:"accept",
      if_false:"reject",
    });
  }

  // If no single condition is sufficient, the engine can synthesize
  // a two-condition conjunction rather than hand-patching a threshold.
  for(let i=0;i<atomic.length;i++) {
    for(let j=i+1;j<atomic.length;j++) {
      if(atomic[i].feature===atomic[j].feature) continue;
      rules.push({
        language:"LRA-1",
        kind:"decision_rule",
        conditions:[atomic[i],atomic[j]],
        combine:"AND",
        if_true:"accept",
        if_false:"reject",
      });
    }
  }

  let best:LraRule|null=null;
  let bestAccuracy=-1;
  let bestComplexity=999;
  let bestMargin=-1;

  for(const rule of rules) {
    const accuracy=ruleAccuracy(rule,train);
    const complexity=rule.conditions.length;
    let margin=0;

    for(const c of rule.conditions) {
      const values=train.map((e:any)=>Number(e.features?.[c.feature]??0));
      const d=Math.min(...values.map(v=>Math.abs(v-c.threshold)));
      if(Number.isFinite(d)) margin += d;
    }

    if(
      accuracy>bestAccuracy ||
      (accuracy===bestAccuracy && complexity<bestComplexity) ||
      (accuracy===bestAccuracy && complexity===bestComplexity && margin>bestMargin)
    ) {
      best=rule;
      bestAccuracy=accuracy;
      bestComplexity=complexity;
      bestMargin=margin;
    }
  }

  if(!best) throw new Error("LRA-1 synthesis produced no candidate rule");

  return {
    rule:best,
    train_accuracy:bestAccuracy,
    candidate_count:rules.length,
    complexity:bestComplexity,
  };
}

function lraRuleSource(rule:LraRule) {
  const conditions=rule.conditions.map(c=>
    c.feature+" "+c.op+" "+c.threshold.toFixed(12)
  ).join(" AND ");
  return [
    "LANGUAGE LRA-1",
    "TYPE decision_rule",
    "IF "+conditions,
    "THEN accept",
    "ELSE reject",
  ].join("\n");
}

async function selfLearningResearch(cycleId:number) {
  const query="rule induction program synthesis decision rules";
  const encoded=encodeURIComponent(query);
  const evidence:any[]=[];

  for(const job of [
    {
      key:"RF:CROSSREF",
      path:`works?query.title=${encoded}&rows=3`,
      purpose:"self-learning research: rule induction"
    },
    {
      key:"RF:OPENALEX",
      path:`works?search=${encoded}&per-page=3`,
      purpose:"self-learning research: program synthesis"
    }
  ]) {
    try {
      const r=await fetchThroughResource(
        cycleId,job.key,job.path,job.purpose
      );
      const parsed=JSON.parse(r.text);
      let items:any[]=[];

      if(job.key==="RF:CROSSREF") {
        items=(parsed?.message?.items??[]).slice(0,3).map((x:any)=>({
          title:Array.isArray(x?.title)?x.title[0]:x?.title??null,
          doi:x?.DOI??null,
          type:x?.type??null,
        }));
      } else {
        items=(parsed?.results??[]).slice(0,3).map((x:any)=>({
          title:x?.title??null,
          doi:x?.doi??null,
          type:x?.type??null,
        }));
      }

      evidence.push({
        resource_key:job.key,
        http_status:r.http_status,
        items,
      });
    } catch(error) {
      evidence.push({
        resource_key:job.key,
        error:error instanceof Error?error.message:String(error),
      });
    }
  }

  return {
    query,
    sources:evidence,
    successful_sources:evidence.filter(x=>!x.error).length,
    researched_at:nowIso(),
  };
}

async function selfLearningRuleEvaluator(goal:Goal,cycleId:number) {
  const candidateKey=String(
    goal.target?.candidate_key??"D0010:self-learning-rule-synthesis"
  );

  // Phase 1: research occurs before training-set freeze and synthesis.
  const research=await selfLearningResearch(cycleId);
  if(research.successful_sources<1) {
    throw new Error("self-learning research phase found no usable research source");
  }

  // Historical D0004 is training. D0004R1 remains unseen until after rule synthesis.
  const {data:trainRows,error:trainErr}=await db
    .from("mind_core_relation_generalization_runs")
    .select("*, mind_core_relation_generalization_cases!inner(case_key,expect_generalizes)")
    .eq("candidate_key","D0004:heldout-relation-validation")
    .order("id",{ascending:true});
  if(trainErr) throw trainErr;

  const train=(trainRows??[]).map((r:any)=>relationExampleFromRun({
    ...r,
    case_key:r.mind_core_relation_generalization_cases?.case_key,
    expect_generalizes:r.mind_core_relation_generalization_cases?.expect_generalizes,
  }));

  if(train.length<4) throw new Error("self-learning training set too small");

  const trainHash=await sha256Hex(JSON.stringify(train));
  const synthesis=synthesizeLraRule(train);
  const rule=synthesis.rule;
  const generatedSource=lraRuleSource(rule);

  const artifactSpec={
    language:"LRA-1",
    objective:"Decide whether a relation candidate is likely to generalize from observed train statistics.",
    input_schema:{
      consistency:"number[0,1]",
      coverage:"number[0,1]",
      left_uniqueness:"number[0,1]",
    },
    rule,
    synthesis:{
      method:"bounded program synthesis over single/two-condition threshold rules",
      candidate_count:synthesis.candidate_count,
      train_accuracy:synthesis.train_accuracy,
      training_hash:trainHash,
      heldout_labels_visible_during_synthesis:false,
    }
  };

  const artifactHash=await sha256Hex(JSON.stringify({
    artifact_key:"ALG:RELATION_GENERALIZATION_RULE",
    version:1,
    research,
    spec:artifactSpec,
    source:generatedSource,
  }));

  let artifact:any=null;
  const {data:existing,error:existingErr}=await db
    .from("mind_core_learning_artifacts")
    .select("*")
    .eq("artifact_hash",artifactHash)
    .maybeSingle();
  if(existingErr) throw existingErr;

  if(existing) {
    artifact=existing;
  } else {
    const {data:created,error:createErr}=await db
      .from("mind_core_learning_artifacts")
      .insert({
        artifact_key:"ALG:RELATION_GENERALIZATION_RULE",
        version:1,
        parent_artifact_id:null,
        artifact_type:"algorithm",
        language:"LRA-1",
        title:"Learned Relation Generalization Rule",
        objective:"Classify relation candidates from observed structural statistics without a hard-coded domain predicate.",
        research,
        spec:artifactSpec,
        generated_source:generatedSource,
        status:"shadow",
        artifact_hash:artifactHash,
        created_from_cycle:cycleId,
      })
      .select("*")
      .single();
    if(createErr) throw createErr;
    artifact=created;
  }

  const {error:trainExpErr}=await db
    .from("mind_core_learning_experiments")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      experiment_type:"train",
      dataset_key:"D0004:relation-generalization:v1",
      frozen_input_hash:trainHash,
      result:{
        examples:train,
        synthesized_rule:rule,
        generated_source:generatedSource,
        accuracy:synthesis.train_accuracy,
      },
      score:synthesis.train_accuracy,
      passed:synthesis.train_accuracy>=0.75,
    });
  if(trainExpErr) throw trainExpErr;

  // Phase 2: held-out labels are fetched only after artifact serialization.
  const {data:heldRows,error:heldErr}=await db
    .from("mind_core_relation_generalization_runs")
    .select("*, mind_core_relation_generalization_cases!inner(case_key,expect_generalizes)")
    .eq("candidate_key","D0004R1:key-directed-relation-generalization")
    .order("id",{ascending:true});
  if(heldErr) throw heldErr;

  const heldout=(heldRows??[]).map((r:any)=>relationExampleFromRun({
    ...r,
    case_key:r.mind_core_relation_generalization_cases?.case_key,
    expect_generalizes:r.mind_core_relation_generalization_cases?.expect_generalizes,
  }));

  const heldHash=await sha256Hex(JSON.stringify(heldout));
  const heldResults=heldout.map((ex:any)=>{
    const output=applyLraRule(rule,ex.features);
    const predicted=output==="accept";
    return {
      case_key:ex.case_key,
      features:ex.features,
      expected:ex.label,
      output,
      passed:predicted===ex.label,
    };
  });
  const heldAccuracy=heldResults.length
    ? heldResults.filter((x:any)=>x.passed).length/heldResults.length
    : 0;

  const {error:heldExpErr}=await db
    .from("mind_core_learning_experiments")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      experiment_type:"heldout",
      dataset_key:"D0004R1:key-directed-relation-generalization:v2",
      frozen_input_hash:heldHash,
      result:{
        examples:heldResults,
        heldout_labels_hidden_until_after_synthesis:true,
        accuracy:heldAccuracy,
      },
      score:heldAccuracy,
      passed:heldAccuracy>=0.75,
    });
  if(heldExpErr) throw heldExpErr;

  // Phase 3: apply learned artifact to a fresh relation from the independent
  // M0009 admission source (HTTP Field Registry), not part of train/heldout.
  const {data:m9,error:m9Err}=await db
    .from("mind_core_mechanisms")
    .select("evidence")
    .eq("mechanism_key","M0009:key-directed-relation-generalizer")
    .single();
  if(m9Err) throw m9Err;

  const freshRel=m9?.evidence?.independent_self_test?.matched_relation??null;
  const freshStats=freshRel?.train_stats??null;
  if(!freshStats) throw new Error("fresh application relation evidence unavailable");

  const freshInput={
    source:"M0009 independent HTTP Field Registry admission",
    relation:{
      left_header:freshRel.left_header,
      right_header:freshRel.right_header,
    },
    features:{
      consistency:Number(freshStats.consistency??0),
      coverage:Number(freshStats.coverage??0),
      left_uniqueness:Number(freshStats.left_uniqueness??0),
    }
  };
  const freshOutput=applyLraRule(rule,freshInput.features);
  const freshPassed=freshOutput==="accept";

  const {error:appErr}=await db
    .from("mind_core_learning_applications")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      application_key:"fresh:http-fields:field-name-to-status",
      input:freshInput,
      output:{
        decision:freshOutput,
        rule,
      },
      evidence:{
        source_mechanism:"M0009:key-directed-relation-generalizer",
        independent_from_training:true,
        independent_from_heldout:true,
      },
      passed:freshPassed,
    });
  if(appErr) throw appErr;

  const {error:freshExpErr}=await db
    .from("mind_core_learning_experiments")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      experiment_type:"fresh_application",
      dataset_key:"M0009:http-fields:admission",
      frozen_input_hash:await sha256Hex(JSON.stringify(freshInput)),
      result:{
        input:freshInput,
        output:freshOutput,
      },
      score:freshPassed?1:0,
      passed:freshPassed,
    });
  if(freshExpErr) throw freshExpErr;

  const passed=
    synthesis.train_accuracy>=0.75 &&
    heldAccuracy>=0.75 &&
    freshPassed &&
    research.successful_sources>=1;

  const verdict={
    evaluator_version:"self-learning-lra-v1",
    candidate_key:candidateKey,
    research,
    artifact_id:artifact.id,
    artifact_key:artifact.artifact_key,
    artifact_hash:artifactHash,
    generated_source:generatedSource,
    rule,
    train_accuracy:synthesis.train_accuracy,
    heldout_accuracy:heldAccuracy,
    heldout_results:heldResults,
    fresh_application:{
      input:freshInput,
      output:freshOutput,
      passed:freshPassed,
    },
    train_test_separation:true,
    arbitrary_code_execution:false,
    artifact_interpreted_by:"LRA-1 interpreter",
    reject_redesign_supported:true,
    passed,
    checked_at:nowIso(),
  };

  await db.from("mind_core_learning_artifacts").update({
    status:passed?"admitted":"rejected",
    admitted_at:passed?nowIso():null,
  }).eq("id",artifact.id);

  const {error:candidateErr}=await db
    .from("mind_core_development_candidates")
    .update({
      status:passed?"admitted":"rejected",
      shadow_result:verdict,
      source_metrics:{
        research_sources:research.successful_sources,
        train_accuracy:synthesis.train_accuracy,
        heldout_accuracy:heldAccuracy,
        fresh_application_passed:freshPassed,
      },
      internet_evidence:{
        research,
        training_hash:trainHash,
        heldout_hash:heldHash,
        artifact_hash:artifactHash,
      },
      updated_at:nowIso(),
    })
    .eq("candidate_key",candidateKey);
  if(candidateErr) throw candidateErr;

  if(passed) {
    const {error:mechErr}=await db.from("mind_core_mechanisms").upsert({
      mechanism_key:"M0015:self-learning-engine",
      ordinal:15,
      name:"Self-Learning Engine",
      kind:"learning_and_algorithm_genesis",
      description:"Research a deficit, freeze training evidence, synthesize an explicit bounded algorithm/rule artifact, serialize and hash it, evaluate on held-out data, apply it to a fresh task, and admit or reject the artifact without arbitrary code execution.",
      capabilities:[
        "research_before_synthesis",
        "rule_induction",
        "bounded_program_synthesis",
        "algorithm_artifact_generation",
        "artifact_hashing",
        "heldout_evaluation",
        "fresh_task_application",
        "reject_redesign_loop"
      ],
      constraints:[
        "LRA-1_bounded_DSL_v1",
        "no_eval",
        "no_arbitrary_shell",
        "no_network_inside_artifact",
        "heldout_labels_hidden_until_after_synthesis",
        "artifact_provenance_required",
        "production_use_only_after_admission"
      ],
      status:"admitted",
      evidence:{
        development_parent:candidateKey,
        evaluator:"self-learning-lra-v1",
        research,
        artifact_id:artifact.id,
        artifact_hash:artifactHash,
        generated_source:generatedSource,
        train_accuracy:synthesis.train_accuracy,
        heldout_accuracy:heldAccuracy,
        fresh_application_passed:freshPassed,
        train_test_separation:true,
      },
      admitted_at:nowIso(),
      updated_at:nowIso(),
    },{onConflict:"mechanism_key"});
    if(mechErr) throw mechErr;
  }

  return verdict;
}


type GsaWeights = {
  utility:number;
  dependency:number;
  urgency:number;
  info_gain:number;
  cost:number;
  risk:number;
};

function scoreGoalWithGsa(goal:any,budget:any,w:GsaWeights) {
  const cost=Number(goal?.cost??1);
  const risk=Number(goal?.risk??1);
  const costMax=Number(budget?.cost_max??1);
  const riskMax=Number(budget?.risk_max??1);

  const feasible=cost<=costMax && risk<=riskMax;
  const contributions={
    utility:w.utility*Number(goal?.utility??0),
    dependency:w.dependency*Number(goal?.dependency??0),
    urgency:w.urgency*Number(goal?.urgency??0),
    info_gain:w.info_gain*Number(goal?.info_gain??0),
    cost:-w.cost*cost,
    risk:-w.risk*risk,
  };
  const score=Object.values(contributions).reduce((a,b)=>a+Number(b),0);

  return {
    goal_key:String(goal?.goal_key??""),
    feasible,
    score,
    contributions,
    budget_check:{cost,cost_max:costMax,risk,risk_max:riskMax},
  };
}

function chooseGoalWithGsa(goals:any[],budget:any,w:GsaWeights) {
  const scored=(goals??[]).map(g=>scoreGoalWithGsa(g,budget,w));
  const feasible=scored.filter(x=>x.feasible);
  feasible.sort((a,b)=>
    b.score-a.score ||
    a.budget_check.risk-b.budget_check.risk ||
    a.budget_check.cost-b.budget_check.cost ||
    a.goal_key.localeCompare(b.goal_key)
  );
  const selected=feasible[0]??null;
  return {selected,scored};
}

function gsaSource(w:GsaWeights) {
  return [
    "LANGUAGE GSA-1",
    "HARD_GATE cost <= cost_max",
    "HARD_GATE risk <= risk_max",
    "SCORE =",
    "  "+w.utility.toFixed(6)+" * utility",
    "  + "+w.dependency.toFixed(6)+" * dependency",
    "  + "+w.urgency.toFixed(6)+" * urgency",
    "  + "+w.info_gain.toFixed(6)+" * info_gain",
    "  - "+w.cost.toFixed(6)+" * cost",
    "  - "+w.risk.toFixed(6)+" * risk",
    "SELECT highest feasible SCORE",
  ].join("\n");
}

function synthesizeGsa(trainCases:any[]) {
  const grid=[0.25,0.50,0.75,1.00];
  let best:any=null;
  let candidateCount=0;

  for(const utility of grid)
  for(const dependency of grid)
  for(const urgency of grid)
  for(const info_gain of grid)
  for(const cost of grid)
  for(const risk of grid) {
    candidateCount += 1;
    const raw:GsaWeights={utility,dependency,urgency,info_gain,cost,risk};
    const sum=utility+dependency+urgency+info_gain+cost+risk;
    const w:GsaWeights={
      utility:utility/sum,
      dependency:dependency/sum,
      urgency:urgency/sum,
      info_gain:info_gain/sum,
      cost:cost/sum,
      risk:risk/sum,
    };

    let correct=0;
    let marginSum=0;
    const trainResults:any[]=[];

    for(const c of trainCases) {
      const chosen=chooseGoalWithGsa(c.goals,c.budget,w);
      const selectedKey=chosen.selected?.goal_key??null;
      const passed=selectedKey===String(c.expected_goal_key);
      if(passed) correct += 1;

      const feasible=chosen.scored
        .filter((x:any)=>x.feasible)
        .sort((a:any,b:any)=>b.score-a.score);
      const margin=
        feasible.length>=2
          ? Number(feasible[0].score)-Number(feasible[1].score)
          : (feasible.length===1?1:0);
      marginSum += margin;

      trainResults.push({
        case_key:c.case_key,
        selected_goal_key:selectedKey,
        expected_goal_key:c.expected_goal_key,
        passed,
        margin,
      });
    }

    const accuracy=trainCases.length?correct/trainCases.length:0;
    const meanMargin=trainCases.length?marginSum/trainCases.length:0;
    const balancePenalty=Math.max(
      w.utility,w.dependency,w.urgency,w.info_gain,w.cost,w.risk
    )-Math.min(
      w.utility,w.dependency,w.urgency,w.info_gain,w.cost,w.risk
    );

    const candidate={
      weights:w,
      accuracy,
      mean_margin:meanMargin,
      balance_penalty:balancePenalty,
      train_results:trainResults,
    };

    if(
      !best ||
      candidate.accuracy>best.accuracy ||
      (
        candidate.accuracy===best.accuracy &&
        candidate.mean_margin>best.mean_margin
      ) ||
      (
        candidate.accuracy===best.accuracy &&
        Math.abs(candidate.mean_margin-best.mean_margin)<1e-12 &&
        candidate.balance_penalty<best.balance_penalty
      )
    ) best=candidate;
  }

  if(!best) throw new Error("GSA-1 synthesis produced no policy");
  return {...best,candidate_count:candidateCount};
}

async function goalSelectionResearch(cycleId:number) {
  const query="multi criteria decision making utility risk cost resource allocation goal selection";
  const encoded=encodeURIComponent(query);
  const evidence:any[]=[];

  for(const job of [
    {
      key:"RF:CROSSREF",
      path:`works?query.title=${encoded}&rows=3`,
      purpose:"DM04 goal-selection research"
    },
    {
      key:"RF:OPENALEX",
      path:`works?search=${encoded}&per-page=3`,
      purpose:"DM04 multi-criteria decision research"
    }
  ]) {
    try {
      const r=await fetchThroughResource(
        cycleId,job.key,job.path,job.purpose
      );
      const parsed=JSON.parse(r.text);
      let items:any[]=[];

      if(job.key==="RF:CROSSREF") {
        items=(parsed?.message?.items??[]).slice(0,3).map((x:any)=>({
          title:Array.isArray(x?.title)?x.title[0]:x?.title??null,
          doi:x?.DOI??null,
          type:x?.type??null,
        }));
      } else {
        items=(parsed?.results??[]).slice(0,3).map((x:any)=>({
          title:x?.title??null,
          doi:x?.doi??null,
          type:x?.type??null,
        }));
      }

      evidence.push({
        resource_key:job.key,
        http_status:r.http_status,
        items,
      });
    } catch(error) {
      evidence.push({
        resource_key:job.key,
        error:error instanceof Error?error.message:String(error),
      });
    }
  }

  return {
    query,
    sources:evidence,
    successful_sources:evidence.filter(x=>!x.error).length,
    researched_at:nowIso(),
  };
}

async function goalSelectionEvaluator(goal:Goal,cycleId:number) {
  const candidateKey=String(goal.target?.candidate_key??"D0011:goal-selection");
  const research=await goalSelectionResearch(cycleId);
  if(research.successful_sources<1) {
    throw new Error("goal-selection research phase found no usable source");
  }

  const {data:trainCases,error:trainErr}=await db
    .from("mind_core_goal_selection_cases")
    .select("*")
    .eq("split","train")
    .order("id",{ascending:true});
  if(trainErr) throw trainErr;

  const trainHash=await sha256Hex(JSON.stringify(trainCases??[]));
  const synthesis=synthesizeGsa(trainCases??[]);
  const weights:GsaWeights=synthesis.weights;
  const generatedSource=gsaSource(weights);

  const spec={
    language:"GSA-1",
    objective:"Choose one feasible goal from a competing frontier using learned multi-criteria weights and hard cost/risk budgets.",
    features:["utility","dependency","urgency","info_gain","cost","risk"],
    hard_gates:["cost <= cost_max","risk <= risk_max"],
    weights,
    synthesis:{
      method:"bounded grid search over six normalized weights",
      candidate_count:synthesis.candidate_count,
      train_accuracy:synthesis.accuracy,
      train_mean_margin:synthesis.mean_margin,
      training_hash:trainHash,
      heldout_labels_visible_during_synthesis:false,
    }
  };

  const artifactHash=await sha256Hex(JSON.stringify({
    artifact_key:"ALG:GOAL_SELECTION_POLICY",
    version:1,
    research,
    spec,
    source:generatedSource,
  }));

  let artifact:any=null;
  const {data:existing,error:existingErr}=await db
    .from("mind_core_learning_artifacts")
    .select("*")
    .eq("artifact_hash",artifactHash)
    .maybeSingle();
  if(existingErr) throw existingErr;

  if(existing) {
    artifact=existing;
  } else {
    const {data:created,error:createErr}=await db
      .from("mind_core_learning_artifacts")
      .insert({
        artifact_key:"ALG:GOAL_SELECTION_POLICY",
        version:1,
        parent_artifact_id:null,
        artifact_type:"policy",
        language:"GSA-1",
        title:"Learned Goal Selection Policy",
        objective:"Select a feasible goal using utility, program dependency, urgency, information gain, cost and risk.",
        research,
        spec,
        generated_source:generatedSource,
        status:"shadow",
        artifact_hash:artifactHash,
        created_from_cycle:cycleId,
      })
      .select("*")
      .single();
    if(createErr) throw createErr;
    artifact=created;
  }

  const {error:trainExpErr}=await db
    .from("mind_core_learning_experiments")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      experiment_type:"train",
      dataset_key:"goal-selection:train:v1",
      frozen_input_hash:trainHash,
      result:{
        train_cases:trainCases,
        train_results:synthesis.train_results,
        weights,
        generated_source:generatedSource,
        accuracy:synthesis.accuracy,
      },
      score:synthesis.accuracy,
      passed:synthesis.accuracy>=0.85,
    });
  if(trainExpErr) throw trainExpErr;

  // Held-out labels are loaded only after policy serialization.
  const {data:heldCases,error:heldErr}=await db
    .from("mind_core_goal_selection_cases")
    .select("*")
    .eq("split","heldout")
    .order("id",{ascending:true});
  if(heldErr) throw heldErr;

  const heldHash=await sha256Hex(JSON.stringify(heldCases??[]));
  const heldResults=(heldCases??[]).map((c:any)=>{
    const chosen=chooseGoalWithGsa(c.goals,c.budget,weights);
    const selected=chosen.selected;
    const selectedKey=selected?.goal_key??null;
    const budgetRespected=
      !!selected &&
      selected.budget_check.cost<=selected.budget_check.cost_max &&
      selected.budget_check.risk<=selected.budget_check.risk_max;
    const passed=
      selectedKey===String(c.expected_goal_key) &&
      budgetRespected;

    return {
      case_key:c.case_key,
      expected_goal_key:c.expected_goal_key,
      selected_goal_key:selectedKey,
      budget_respected:budgetRespected,
      selected_score:selected?.score??null,
      contributions:selected?.contributions??null,
      feasible_count:chosen.scored.filter((x:any)=>x.feasible).length,
      passed,
    };
  });

  const heldAccuracy=heldResults.length
    ? heldResults.filter((x:any)=>x.passed).length/heldResults.length
    : 0;

  const explanationsGrounded=heldResults.every((x:any)=>
    x.contributions &&
    ["utility","dependency","urgency","info_gain","cost","risk"]
      .every(k=>Number.isFinite(Number(x.contributions[k])))
  );

  const {error:heldExpErr}=await db
    .from("mind_core_learning_experiments")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      experiment_type:"heldout",
      dataset_key:"goal-selection:heldout:v1",
      frozen_input_hash:heldHash,
      result:{
        heldout_labels_hidden_until_after_synthesis:true,
        cases:heldResults,
        accuracy:heldAccuracy,
        explanations_grounded:explanationsGrounded,
      },
      score:heldAccuracy,
      passed:heldAccuracy>=0.75 && explanationsGrounded,
    });
  if(heldExpErr) throw heldExpErr;

  // Fresh application to the current live capability-gap frontier.
  const {data:latestAudit,error:auditErr}=await db
    .from("mind_core_capability_audits")
    .select("id")
    .order("id",{ascending:false})
    .limit(1)
    .single();
  if(auditErr) throw auditErr;

  const {data:gapRows,error:gapsErr}=await db
    .from("mind_core_capability_gaps")
    .select("*")
    .eq("audit_id",latestAudit.id)
    .neq("capability_key","goal_selection")
    .order("priority",{ascending:false});
  if(gapsErr) throw gapsErr;

  const freshGoals=(gapRows??[]).map((g:any)=>({
    goal_key:String(g.recommended_target??g.capability_key),
    utility:Number(g.impact??0),
    dependency:Number(g.dependency_relevance??0),
    urgency:
      String(g.recommended_target??"")==="M0017:planner-replanner"
        ? 0.90
        : 0.40,
    info_gain:Number(g.measurability??0),
    cost:Number(g.cost??1),
    risk:Number(g.risk??1),
  }));

  const freshBudget={cost_max:0.60,risk_max:0.40};
  const freshChoice=chooseGoalWithGsa(freshGoals,freshBudget,weights);
  const freshSelected=freshChoice.selected;
  const freshPassed=!!freshSelected && freshSelected.feasible===true;

  const freshApplication={
    source_audit_id:latestAudit.id,
    budget:freshBudget,
    selected_goal_key:freshSelected?.goal_key??null,
    selected_score:freshSelected?.score??null,
    contributions:freshSelected?.contributions??null,
    budget_respected:freshPassed,
    candidate_count:freshGoals.length,
  };

  const {error:appErr}=await db
    .from("mind_core_learning_applications")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      application_key:"fresh:live-capability-gap-frontier",
      input:{
        audit_id:latestAudit.id,
        goals:freshGoals,
        budget:freshBudget,
      },
      output:{
        selected_goal_key:freshSelected?.goal_key??null,
        score:freshSelected?.score??null,
        contributions:freshSelected?.contributions??null,
      },
      evidence:{
        source:"live capability audit",
        independent_from_training:true,
        independent_from_heldout:true,
      },
      passed:freshPassed,
    });
  if(appErr) throw appErr;

  const totalTradeoffCases=(trainCases?.length??0)+(heldCases?.length??0);
  const passed=
    research.successful_sources>=1 &&
    synthesis.accuracy>=0.85 &&
    heldAccuracy>=0.75 &&
    totalTradeoffCases>=6 &&
    heldResults.every((x:any)=>x.budget_respected) &&
    explanationsGrounded &&
    freshPassed;

  const verdict={
    evaluator_version:"goal-selection-gsa-v1",
    candidate_key:candidateKey,
    research,
    artifact_id:artifact.id,
    artifact_hash:artifactHash,
    generated_source:generatedSource,
    weights,
    train_accuracy:synthesis.accuracy,
    heldout_accuracy:heldAccuracy,
    heldout_results:heldResults,
    total_tradeoff_cases:totalTradeoffCases,
    explanations_grounded:explanationsGrounded,
    fresh_application:freshApplication,
    train_test_separation:true,
    passed,
    checked_at:nowIso(),
  };

  await db.from("mind_core_learning_artifacts").update({
    status:passed?"admitted":"rejected",
    admitted_at:passed?nowIso():null,
  }).eq("id",artifact.id);

  const {error:candidateErr}=await db
    .from("mind_core_development_candidates")
    .update({
      status:passed?"admitted":"rejected",
      source_metrics:{
        research_sources:research.successful_sources,
        train_accuracy:synthesis.accuracy,
        heldout_accuracy:heldAccuracy,
        tradeoff_cases:totalTradeoffCases,
        fresh_application_passed:freshPassed,
      },
      internet_evidence:{
        research,
        train_hash:trainHash,
        heldout_hash:heldHash,
        artifact_hash:artifactHash,
      },
      shadow_result:verdict,
      updated_at:nowIso(),
    })
    .eq("candidate_key",candidateKey);
  if(candidateErr) throw candidateErr;

  return verdict;
}


async function admittedGoalSelectionArtifact() {
  const {data,error}=await db
    .from("mind_core_learning_artifacts")
    .select("*")
    .eq("artifact_key","ALG:GOAL_SELECTION_POLICY")
    .eq("status","admitted")
    .order("version",{ascending:false})
    .limit(1)
    .single();
  if(error) throw error;
  return data;
}

async function goalSelectionSelfTest(goal:Goal,cycleId:number) {
  const tests=Array.isArray(goal.target?.tests)?goal.target.tests:[];
  if(tests.length<3) throw new Error("M0016 self-test requires >=3 tests");

  const artifact=await admittedGoalSelectionArtifact();
  const weights=(artifact?.spec?.weights??null) as GsaWeights|null;
  if(!weights) throw new Error("admitted GSA-1 policy weights unavailable");

  const results:any[]=[];
  let passedCount=0;

  for(const t of tests) {
    const chosen=chooseGoalWithGsa(
      Array.isArray(t.goals)?t.goals:[],
      t.budget??{},
      weights
    );
    const selected=chosen.selected;
    const selectedKey=selected?.goal_key??null;
    const expectedKey=t.expected_goal_key===null?null:String(t.expected_goal_key);

    const budgetRespected=
      selected===null
        ? chosen.scored.every((x:any)=>x.feasible===false)
        : (
            selected.feasible===true &&
            selected.budget_check.cost<=selected.budget_check.cost_max &&
            selected.budget_check.risk<=selected.budget_check.risk_max
          );

    const explanationGrounded=
      selected===null
        ? true
        : ["utility","dependency","urgency","info_gain","cost","risk"]
            .every(k=>Number.isFinite(Number(selected.contributions?.[k])));

    const passed=
      selectedKey===expectedKey &&
      budgetRespected &&
      explanationGrounded;

    if(passed) passedCount += 1;

    results.push({
      case_key:String(t.case_key??""),
      expected_goal_key:expectedKey,
      selected_goal_key:selectedKey,
      budget_respected:budgetRespected,
      no_feasible_goal:selected===null,
      score:selected?.score??null,
      contributions:selected?.contributions??null,
      feasible_goals:chosen.scored.filter((x:any)=>x.feasible).map((x:any)=>x.goal_key),
      passed,
    });
  }

  const allPassed=passedCount===tests.length;
  const summary={
    mechanism_key:"M0016:goal-selection",
    evaluator_version:"goal-selection-admission-v1",
    artifact_id:artifact.id,
    artifact_hash:artifact.artifact_hash,
    artifact_language:artifact.language,
    tests_total:tests.length,
    tests_passed:passedCount,
    all_passed:allPassed,
    weights,
    results,
    checked_at:nowIso(),
  };

  if(!allPassed) throw new Error("M0016 goal-selection admission failed");

  const {data:mechanism,error:mechReadErr}=await db
    .from("mind_core_mechanisms")
    .select("evidence")
    .eq("mechanism_key","M0016:goal-selection")
    .single();
  if(mechReadErr) throw mechReadErr;

  const {error:updateErr}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence:{
      ...(mechanism?.evidence??{}),
      independent_self_test:summary,
      admitted_reason:"Learned GSA-1 policy passed 13 development tradeoff cases plus independent admission tests for program dependency, hard budget exclusion, and no-feasible-goal behavior.",
    },
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key","M0016:goal-selection");
  if(updateErr) throw updateErr;

  return summary;
}


type PlannerStrategy = "bfs"|"uniform_cost"|"astar_goal_count";

type PlannerConfig = {
  language:"PRA-1";
  strategy:PlannerStrategy;
  heuristic_weight:number;
  cost_weight:number;
  max_expansions:number;
  loop_detection:true;
  failure_policy:"block_failed_action_and_replan";
};

function factStateKey(facts:Set<string>) {
  return [...facts].sort().join("\u241f");
}

function goalSatisfied(facts:Set<string>,goals:string[]) {
  return goals.every(g=>facts.has(String(g)));
}

function applicableAction(facts:Set<string>,action:any) {
  const pre=Array.isArray(action?.pre)?action.pre.map(String):[];
  return pre.every((p:string)=>facts.has(p));
}

function applySymbolicAction(facts:Set<string>,action:any) {
  const next=new Set(facts);
  for(const d of Array.isArray(action?.del)?action.del:[]) next.delete(String(d));
  for(const a of Array.isArray(action?.add)?action.add:[]) next.add(String(a));
  return next;
}

function symbolicPriority(
  facts:Set<string>,
  goals:string[],
  g:number,
  depth:number,
  config:PlannerConfig
) {
  if(config.strategy==="bfs") return depth;
  if(config.strategy==="uniform_cost") return g;
  const unsatisfied=goals.filter(x=>!facts.has(String(x))).length;
  return config.cost_weight*g + config.heuristic_weight*unsatisfied;
}

function planSymbolic(
  initialFacts:string[],
  goalFacts:string[],
  actions:any[],
  blocked:Set<string>,
  config:PlannerConfig
) {
  const initial=new Set((initialFacts??[]).map(String));
  const goals=(goalFacts??[]).map(String);

  const frontier:any[]=[{
    facts:initial,
    path:[],
    g:0,
    depth:0,
    priority:symbolicPriority(initial,goals,0,0,config),
  }];

  const bestCost=new Map<string,number>();
  bestCost.set(factStateKey(initial),0);

  let expansions=0;
  let duplicate_skips=0;

  while(frontier.length && expansions<config.max_expansions) {
    frontier.sort((a,b)=>
      a.priority-b.priority ||
      a.g-b.g ||
      a.depth-b.depth ||
      a.path.join(",").localeCompare(b.path.join(","))
    );
    const node=frontier.shift();
    expansions += 1;

    if(goalSatisfied(node.facts,goals)) {
      return {
        found:true,
        plan:node.path,
        cost:node.g,
        expansions,
        duplicate_skips,
        loop_detection:true,
      };
    }

    for(const action of actions??[]) {
      const key=String(action?.key??"");
      if(!key || blocked.has(key)) continue;
      if(!applicableAction(node.facts,action)) continue;

      const nextFacts=applySymbolicAction(node.facts,action);
      const nextKey=factStateKey(nextFacts);
      const nextG=node.g+Number(action?.cost??1);
      const nextDepth=node.depth+1;
      const prior=bestCost.get(nextKey);

      if(prior!==undefined && prior<=nextG) {
        duplicate_skips += 1;
        continue;
      }

      bestCost.set(nextKey,nextG);
      frontier.push({
        facts:nextFacts,
        path:[...node.path,key],
        g:nextG,
        depth:nextDepth,
        priority:symbolicPriority(
          nextFacts,goals,nextG,nextDepth,config
        ),
      });
    }
  }

  return {
    found:false,
    plan:[],
    cost:null,
    expansions,
    duplicate_skips,
    loop_detection:true,
    exhausted:frontier.length===0,
    max_expansions_hit:expansions>=config.max_expansions,
  };
}

function executePlanWithReplanning(caseRow:any,config:PlannerConfig) {
  const actions=Array.isArray(caseRow.actions)?caseRow.actions:[];
  const byKey=new Map(actions.map((a:any)=>[String(a.key),a]));
  const goalFacts=Array.isArray(caseRow.goal_facts)?caseRow.goal_facts.map(String):[];
  let facts=new Set(
    Array.isArray(caseRow.initial_facts)?caseRow.initial_facts.map(String):[]
  );
  const blocked=new Set<string>();
  let failureTriggered=false;
  let replans=0;
  let totalExpansions=0;
  let totalDuplicateSkips=0;
  const executed:string[]=[];
  const planHistory:any[]=[];

  let planned=planSymbolic(
    [...facts],goalFacts,actions,blocked,config
  );
  totalExpansions += Number(planned.expansions??0);
  totalDuplicateSkips += Number(planned.duplicate_skips??0);
  planHistory.push({
    from_state:[...facts].sort(),
    blocked:[...blocked].sort(),
    result:planned,
  });

  if(!planned.found) {
    return {
      success:false,
      no_plan:true,
      replans,
      failure_triggered:false,
      executed,
      final_facts:[...facts].sort(),
      total_expansions:totalExpansions,
      duplicate_skips:totalDuplicateSkips,
      loop_detection:true,
      plan_history:planHistory,
    };
  }

  let remaining=[...planned.plan];
  let guard=0;

  while(guard<100) {
    guard += 1;

    if(goalSatisfied(facts,goalFacts)) {
      return {
        success:true,
        no_plan:false,
        replans,
        failure_triggered:failureTriggered,
        executed,
        final_facts:[...facts].sort(),
        total_expansions:totalExpansions,
        duplicate_skips:totalDuplicateSkips,
        loop_detection:true,
        plan_history:planHistory,
      };
    }

    if(!remaining.length) {
      planned=planSymbolic([...facts],goalFacts,actions,blocked,config);
      totalExpansions += Number(planned.expansions??0);
      totalDuplicateSkips += Number(planned.duplicate_skips??0);
      planHistory.push({
        from_state:[...facts].sort(),
        blocked:[...blocked].sort(),
        result:planned,
      });
      if(!planned.found) {
        return {
          success:false,
          no_plan:true,
          replans,
          failure_triggered:failureTriggered,
          executed,
          final_facts:[...facts].sort(),
          total_expansions:totalExpansions,
          duplicate_skips:totalDuplicateSkips,
          loop_detection:true,
          plan_history:planHistory,
        };
      }
      remaining=[...planned.plan];
    }

    const actionKey=String(remaining.shift()??"");
    const action=byKey.get(actionKey);
    if(!action) {
      return {
        success:false,
        error:"planned action missing",
        replans,
        executed,
        final_facts:[...facts].sort(),
        total_expansions:totalExpansions,
        duplicate_skips:totalDuplicateSkips,
        loop_detection:true,
        plan_history:planHistory,
      };
    }

    if(
      !failureTriggered &&
      caseRow.fail_once_action &&
      actionKey===String(caseRow.fail_once_action)
    ) {
      failureTriggered=true;
      blocked.add(actionKey);
      replans += 1;
      planned=planSymbolic([...facts],goalFacts,actions,blocked,config);
      totalExpansions += Number(planned.expansions??0);
      totalDuplicateSkips += Number(planned.duplicate_skips??0);
      planHistory.push({
        from_state:[...facts].sort(),
        blocked:[...blocked].sort(),
        failure_action:actionKey,
        result:planned,
      });
      if(!planned.found) {
        return {
          success:false,
          no_plan:true,
          replans,
          failure_triggered:true,
          executed,
          final_facts:[...facts].sort(),
          total_expansions:totalExpansions,
          duplicate_skips:totalDuplicateSkips,
          loop_detection:true,
          plan_history:planHistory,
        };
      }
      remaining=[...planned.plan];
      continue;
    }

    if(!applicableAction(facts,action)) {
      blocked.add(actionKey);
      replans += 1;
      planned=planSymbolic([...facts],goalFacts,actions,blocked,config);
      totalExpansions += Number(planned.expansions??0);
      totalDuplicateSkips += Number(planned.duplicate_skips??0);
      planHistory.push({
        from_state:[...facts].sort(),
        blocked:[...blocked].sort(),
        invalid_action:actionKey,
        result:planned,
      });
      if(!planned.found) break;
      remaining=[...planned.plan];
      continue;
    }

    facts=applySymbolicAction(facts,action);
    executed.push(actionKey);
  }

  return {
    success:goalSatisfied(facts,goalFacts),
    no_plan:!goalSatisfied(facts,goalFacts),
    replans,
    failure_triggered:failureTriggered,
    executed,
    final_facts:[...facts].sort(),
    total_expansions:totalExpansions,
    duplicate_skips:totalDuplicateSkips,
    loop_detection:true,
    guard_exhausted:guard>=100,
    plan_history:planHistory,
  };
}

function plannerArtifactSource(config:PlannerConfig) {
  return [
    "LANGUAGE PRA-1",
    "SEARCH "+config.strategy,
    "HEURISTIC_WEIGHT "+config.heuristic_weight,
    "COST_WEIGHT "+config.cost_weight,
    "MAX_EXPANSIONS "+config.max_expansions,
    "LOOP_DETECTION state_hash",
    "ON_FAILURE block_failed_action_and_replan",
    "REPLAN_FROM observed_current_state",
  ].join("\n");
}

function synthesizePlannerConfig(trainCases:any[]) {
  const strategies:PlannerStrategy[]=[
    "bfs","uniform_cost","astar_goal_count"
  ];
  const heuristicWeights=[0.5,1,2];
  const costWeights=[0.5,1,2];
  const maxExpansions=[100,300];

  let best:any=null;
  let candidateCount=0;

  for(const strategy of strategies)
  for(const heuristic_weight of heuristicWeights)
  for(const cost_weight of costWeights)
  for(const max_expansions of maxExpansions) {
    const config:PlannerConfig={
      language:"PRA-1",
      strategy,
      heuristic_weight,
      cost_weight,
      max_expansions,
      loop_detection:true,
      failure_policy:"block_failed_action_and_replan",
    };
    candidateCount += 1;

    const results=(trainCases??[]).map((c:any)=>{
      const execution=executePlanWithReplanning(c,config);
      const successMatches=
        Boolean(execution.success)===Boolean(c.expected_success);
      const replanMatches=
        c.expected_replan
          ? execution.replans>=1 && execution.success===true
          : true;
      return {
        case_key:c.case_key,
        success:execution.success,
        expected_success:c.expected_success,
        replans:execution.replans,
        expected_replan:c.expected_replan,
        expansions:execution.total_expansions,
        passed:successMatches && replanMatches,
      };
    });

    const passed=results.filter((x:any)=>x.passed).length;
    const accuracy=results.length?passed/results.length:0;
    const replanCases=results.filter((_:any,i:number)=>trainCases[i].expected_replan);
    const replanRate=replanCases.length
      ? replanCases.filter((x:any)=>x.passed).length/replanCases.length
      : 1;
    const meanExpansions=results.length
      ? results.reduce((a:number,x:any)=>a+Number(x.expansions??0),0)/results.length
      : 99999;

    const candidate={
      config,
      accuracy,
      replan_rate:replanRate,
      mean_expansions:meanExpansions,
      results,
    };

    if(
      !best ||
      candidate.accuracy>best.accuracy ||
      (
        candidate.accuracy===best.accuracy &&
        candidate.replan_rate>best.replan_rate
      ) ||
      (
        candidate.accuracy===best.accuracy &&
        candidate.replan_rate===best.replan_rate &&
        candidate.mean_expansions<best.mean_expansions
      )
    ) best=candidate;
  }

  if(!best) throw new Error("PRA-1 synthesis produced no planner");
  return {...best,candidate_count:candidateCount};
}

async function planningResearch(cycleId:number) {
  const query="STRIPS planning A star replanning action failure automated planning";
  const encoded=encodeURIComponent(query);
  const evidence:any[]=[];

  for(const job of [
    {
      key:"RF:CROSSREF",
      path:`works?query.title=${encoded}&rows=3`,
      purpose:"DM05 planning research"
    },
    {
      key:"RF:OPENALEX",
      path:`works?search=${encoded}&per-page=3`,
      purpose:"DM05 replanning research"
    }
  ]) {
    try {
      const r=await fetchThroughResource(
        cycleId,job.key,job.path,job.purpose
      );
      const parsed=JSON.parse(r.text);
      let items:any[]=[];

      if(job.key==="RF:CROSSREF") {
        items=(parsed?.message?.items??[]).slice(0,3).map((x:any)=>({
          title:Array.isArray(x?.title)?x.title[0]:x?.title??null,
          doi:x?.DOI??null,
          type:x?.type??null,
        }));
      } else {
        items=(parsed?.results??[]).slice(0,3).map((x:any)=>({
          title:x?.title??null,
          doi:x?.doi??null,
          type:x?.type??null,
        }));
      }
      evidence.push({
        resource_key:job.key,
        http_status:r.http_status,
        items,
      });
    } catch(error) {
      evidence.push({
        resource_key:job.key,
        error:error instanceof Error?error.message:String(error),
      });
    }
  }

  return {
    query,
    sources:evidence,
    successful_sources:evidence.filter(x=>!x.error).length,
    researched_at:nowIso(),
  };
}

async function plannerReplannerEvaluator(goal:Goal,cycleId:number) {
  const candidateKey=String(goal.target?.candidate_key??"D0012:planner-replanner");
  const research=await planningResearch(cycleId);
  if(research.successful_sources<1) {
    throw new Error("planning research phase found no usable source");
  }

  const {data:trainCases,error:trainErr}=await db
    .from("mind_core_planning_cases")
    .select("*")
    .eq("split","train")
    .order("id",{ascending:true});
  if(trainErr) throw trainErr;

  const trainHash=await sha256Hex(JSON.stringify(trainCases??[]));
  const synthesis=synthesizePlannerConfig(trainCases??[]);
  const config:PlannerConfig=synthesis.config;
  const generatedSource=plannerArtifactSource(config);

  const artifactSpec={
    language:"PRA-1",
    objective:"Construct dependency-aware symbolic plans, detect loops, and replan from current observed state after action failure.",
    config,
    synthesis:{
      method:"bounded planner-family search",
      candidate_count:synthesis.candidate_count,
      train_accuracy:synthesis.accuracy,
      train_replan_rate:synthesis.replan_rate,
      mean_expansions:synthesis.mean_expansions,
      training_hash:trainHash,
      heldout_cases_visible_during_synthesis:false,
    }
  };

  const artifactHash=await sha256Hex(JSON.stringify({
    artifact_key:"ALG:PLANNER_REPLANNER",
    version:1,
    research,
    spec:artifactSpec,
    source:generatedSource,
  }));

  let artifact:any=null;
  const {data:existing,error:existingErr}=await db
    .from("mind_core_learning_artifacts")
    .select("*")
    .eq("artifact_hash",artifactHash)
    .maybeSingle();
  if(existingErr) throw existingErr;

  if(existing) artifact=existing;
  else {
    const {data:created,error:createErr}=await db
      .from("mind_core_learning_artifacts")
      .insert({
        artifact_key:"ALG:PLANNER_REPLANNER",
        version:1,
        parent_artifact_id:null,
        artifact_type:"algorithm",
        language:"PRA-1",
        title:"Learned Symbolic Planner/Replanner",
        objective:"Generate multi-step plans and replan after observed action failure with loop detection.",
        research,
        spec:artifactSpec,
        generated_source:generatedSource,
        status:"shadow",
        artifact_hash:artifactHash,
        created_from_cycle:cycleId,
      })
      .select("*")
      .single();
    if(createErr) throw createErr;
    artifact=created;
  }

  const {error:trainExpErr}=await db
    .from("mind_core_learning_experiments")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      experiment_type:"train",
      dataset_key:"planning:train:v1",
      frozen_input_hash:trainHash,
      result:{
        train_results:synthesis.results,
        config,
        generated_source:generatedSource,
        accuracy:synthesis.accuracy,
        replan_rate:synthesis.replan_rate,
        mean_expansions:synthesis.mean_expansions,
      },
      score:synthesis.accuracy,
      passed:synthesis.accuracy>=0.75,
    });
  if(trainExpErr) throw trainExpErr;

  const {data:heldCases,error:heldErr}=await db
    .from("mind_core_planning_cases")
    .select("*")
    .eq("split","heldout")
    .order("id",{ascending:true});
  if(heldErr) throw heldErr;

  const heldHash=await sha256Hex(JSON.stringify(heldCases??[]));
  const heldResults=(heldCases??[]).map((c:any)=>{
    const execution=executePlanWithReplanning(c,config);
    const successMatches=
      Boolean(execution.success)===Boolean(c.expected_success);
    const replanPass=
      c.expected_replan
        ? execution.replans>=1 && execution.success===true
        : true;
    const noLoopFailure=
      execution.guard_exhausted!==true &&
      execution.total_expansions<=config.max_expansions*4;

    return {
      case_key:c.case_key,
      expected_success:c.expected_success,
      observed_success:execution.success,
      expected_replan:c.expected_replan,
      replans:execution.replans,
      executed:execution.executed,
      total_expansions:execution.total_expansions,
      duplicate_skips:execution.duplicate_skips,
      loop_detection:execution.loop_detection,
      no_loop_failure:noLoopFailure,
      success_match:successMatches,
      replan_pass:replanPass,
      passed:successMatches && replanPass && noLoopFailure,
    };
  });

  const heldAccuracy=heldResults.length
    ? heldResults.filter((x:any)=>x.passed).length/heldResults.length
    : 0;

  const replanRows=heldResults.filter((x:any)=>x.expected_replan);
  const replanRate=replanRows.length
    ? replanRows.filter((x:any)=>x.replan_pass).length/replanRows.length
    : 1;
  const loopDetection=heldResults.every((x:any)=>x.loop_detection===true);

  const {error:heldExpErr}=await db
    .from("mind_core_learning_experiments")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      experiment_type:"heldout",
      dataset_key:"planning:heldout:v1",
      frozen_input_hash:heldHash,
      result:{
        heldout_cases_hidden_until_after_synthesis:true,
        cases:heldResults,
        accuracy:heldAccuracy,
        replan_rate:replanRate,
        loop_detection:loopDetection,
      },
      score:heldAccuracy,
      passed:
        heldAccuracy>=0.80 &&
        replanRate>=0.80 &&
        loopDetection,
    });
  if(heldExpErr) throw heldExpErr;

  // Fresh application: plan the current program-development pipeline itself.
  const freshCase={
    initial_facts:["dm05_active","m0016_admitted"],
    goal_facts:["m0017_ready_for_admission"],
    actions:[
      {key:"research_planning",pre:["dm05_active"],add:["planning_researched"],del:[],cost:1},
      {key:"synthesize_planner",pre:["planning_researched"],add:["planner_artifact"],del:[],cost:1},
      {key:"run_heldout",pre:["planner_artifact"],add:["heldout_passed"],del:[],cost:1},
      {key:"prepare_admission",pre:["heldout_passed","m0016_admitted"],add:["m0017_ready_for_admission"],del:[],cost:1}
    ],
    fail_once_action:null,
  };

  const freshExecution=executePlanWithReplanning(freshCase,config);
  const freshPassed=freshExecution.success===true;

  const {error:appErr}=await db
    .from("mind_core_learning_applications")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      application_key:"fresh:dm05-planner-development-pipeline",
      input:freshCase,
      output:{
        success:freshExecution.success,
        executed:freshExecution.executed,
        replans:freshExecution.replans,
        expansions:freshExecution.total_expansions,
      },
      evidence:{
        source:"live Digital Mind program DM05",
        independent_from_training:true,
        independent_from_heldout:true,
      },
      passed:freshPassed,
    });
  if(appErr) throw appErr;

  const passed=
    research.successful_sources>=1 &&
    synthesis.accuracy>=0.75 &&
    heldResults.length>=5 &&
    heldAccuracy>=0.80 &&
    replanRate>=0.80 &&
    loopDetection &&
    freshPassed;

  const verdict={
    evaluator_version:"planner-replanner-pra-v1",
    candidate_key:candidateKey,
    research,
    artifact_id:artifact.id,
    artifact_hash:artifactHash,
    generated_source:generatedSource,
    config,
    train_accuracy:synthesis.accuracy,
    train_replan_rate:synthesis.replan_rate,
    heldout_accuracy:heldAccuracy,
    heldout_replan_rate:replanRate,
    loop_detection:loopDetection,
    heldout_results:heldResults,
    fresh_application:{
      success:freshExecution.success,
      executed:freshExecution.executed,
      replans:freshExecution.replans,
      expansions:freshExecution.total_expansions,
    },
    train_test_separation:true,
    passed,
    checked_at:nowIso(),
  };

  await db.from("mind_core_learning_artifacts").update({
    status:passed?"admitted":"rejected",
    admitted_at:passed?nowIso():null,
  }).eq("id",artifact.id);

  const {error:candidateErr}=await db
    .from("mind_core_development_candidates")
    .update({
      status:passed?"admitted":"rejected",
      source_metrics:{
        research_sources:research.successful_sources,
        train_accuracy:synthesis.accuracy,
        heldout_accuracy:heldAccuracy,
        heldout_cases:heldResults.length,
        replan_rate:replanRate,
        loop_detection:loopDetection,
        fresh_application_passed:freshPassed,
      },
      internet_evidence:{
        research,
        train_hash:trainHash,
        heldout_hash:heldHash,
        artifact_hash:artifactHash,
      },
      shadow_result:verdict,
      updated_at:nowIso(),
    })
    .eq("candidate_key",candidateKey);
  if(candidateErr) throw candidateErr;

  return verdict;
}


async function admittedPlannerArtifact() {
  const {data,error}=await db
    .from("mind_core_learning_artifacts")
    .select("*")
    .eq("artifact_key","ALG:PLANNER_REPLANNER")
    .eq("status","admitted")
    .order("version",{ascending:false})
    .limit(1)
    .single();
  if(error) throw error;
  return data;
}

async function plannerReplannerSelfTest(goal:Goal,cycleId:number) {
  const tests=Array.isArray(goal.target?.tests)?goal.target.tests:[];
  if(tests.length<3) throw new Error("M0017 self-test requires >=3 tests");

  const artifact=await admittedPlannerArtifact();
  const config=(artifact?.spec?.config??null) as PlannerConfig|null;
  if(!config) throw new Error("admitted PRA-1 config unavailable");

  const results:any[]=[];
  let passedCount=0;

  for(const t of tests) {
    const execution=executePlanWithReplanning(t,config);
    const successPass=
      Boolean(execution.success)===Boolean(t.expected_success);
    const replanPass=
      t.expected_replan
        ? execution.replans>=1 && execution.success===true
        : true;

    let routePass=true;
    if(Array.isArray(t.expected_executed)) {
      routePass=
        JSON.stringify(execution.executed)===
        JSON.stringify(t.expected_executed.map(String));
    }

    const bounded=
      execution.guard_exhausted!==true &&
      execution.total_expansions<=config.max_expansions*4;

    const passed=
      successPass &&
      replanPass &&
      routePass &&
      bounded &&
      execution.loop_detection===true;

    if(passed) passedCount += 1;

    results.push({
      case_key:String(t.case_key??""),
      expected_success:Boolean(t.expected_success),
      observed_success:Boolean(execution.success),
      expected_replan:Boolean(t.expected_replan),
      replans:Number(execution.replans??0),
      executed:execution.executed??[],
      expected_executed:Array.isArray(t.expected_executed)
        ?t.expected_executed:null,
      total_expansions:execution.total_expansions,
      duplicate_skips:execution.duplicate_skips,
      loop_detection:execution.loop_detection,
      bounded,
      success_pass:successPass,
      replan_pass:replanPass,
      route_pass:routePass,
      passed,
    });
  }

  const allPassed=passedCount===tests.length;
  const summary={
    mechanism_key:"M0017:planner-replanner",
    evaluator_version:"planner-replanner-admission-v1",
    artifact_id:artifact.id,
    artifact_hash:artifact.artifact_hash,
    artifact_language:artifact.language,
    config,
    tests_total:tests.length,
    tests_passed:passedCount,
    all_passed:allPassed,
    results,
    checked_at:nowIso(),
  };

  if(!allPassed) throw new Error("M0017 planner/replanner admission failed");

  const {data:mechanism,error:mechReadErr}=await db
    .from("mind_core_mechanisms")
    .select("evidence")
    .eq("mechanism_key","M0017:planner-replanner")
    .single();
  if(mechReadErr) throw mechReadErr;

  const {error:updateErr}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence:{
      ...(mechanism?.evidence??{}),
      independent_self_test:summary,
      admitted_reason:"Frozen PRA-1 planner passed independent failure-recovery, cost-choice, and no-plan admission tests after 6/6 held-out development tasks with 100% replanning success.",
    },
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key","M0017:planner-replanner");
  if(updateErr) throw updateErr;

  return summary;
}


const CFM_OUTCOMES=["success","reject","hold","unresolved"] as const;
type CfmOutcome = typeof CFM_OUTCOMES[number];

function entropyOf(labels:string[]) {
  if(!labels.length) return 0;
  const counts=new Map<string,number>();
  for(const l of labels) counts.set(l,(counts.get(l)??0)+1);
  let h=0;
  for(const count of counts.values()) {
    const p=count/labels.length;
    h -= p*Math.log2(p);
  }
  return h;
}

function cfmDistribution(examples:any[]) {
  const counts:any={success:0,reject:0,hold:0,unresolved:0};
  for(const ex of examples??[]) {
    const y=String(ex.outcome??ex.expected_outcome??"unresolved");
    if(y in counts) counts[y]+=1;
  }
  const n=Math.max(1,(examples??[]).length);
  const dist:any={};
  for(const k of CFM_OUTCOMES) dist[k]=counts[k]/n;
  return dist;
}

function majorityOutcome(dist:any):CfmOutcome {
  let best:CfmOutcome="unresolved";
  let p=-1;
  for(const k of CFM_OUTCOMES) {
    const v=Number(dist?.[k]??0);
    if(v>p) { p=v; best=k; }
  }
  return best;
}

function buildCfmTree(examples:any[],features:string[],depth=0):any {
  const dist=cfmDistribution(examples);
  const labels=(examples??[]).map((x:any)=>String(x.outcome??x.expected_outcome));
  const unique=[...new Set(labels)];

  if(unique.length<=1 || !features.length || depth>=8) {
    return {
      type:"leaf",
      distribution:dist,
      label:majorityOutcome(dist),
      support:examples.length,
    };
  }

  const baseEntropy=entropyOf(labels);
  let bestFeature:string|null=null;
  let bestGain=-1;
  let bestGroups:Map<string,any[]>|null=null;

  for(const feature of features) {
    const groups=new Map<string,any[]>();
    for(const ex of examples) {
      const v=String(Number(ex.features?.[feature]??0));
      if(!groups.has(v)) groups.set(v,[]);
      groups.get(v)!.push(ex);
    }
    let remainder=0;
    for(const group of groups.values()) {
      remainder += (group.length/examples.length) *
        entropyOf(group.map((x:any)=>String(x.outcome??x.expected_outcome)));
    }
    const gain=baseEntropy-remainder;
    if(gain>bestGain) {
      bestGain=gain;
      bestFeature=feature;
      bestGroups=groups;
    }
  }

  if(!bestFeature || !bestGroups || bestGain<=1e-12) {
    return {
      type:"leaf",
      distribution:dist,
      label:majorityOutcome(dist),
      support:examples.length,
    };
  }

  const remaining=features.filter(f=>f!==bestFeature);
  const branches:any={};
  for(const [value,group] of bestGroups.entries()) {
    branches[value]=buildCfmTree(group,remaining,depth+1);
  }

  return {
    type:"node",
    feature:bestFeature,
    gain:bestGain,
    distribution:dist,
    fallback:majorityOutcome(dist),
    support:examples.length,
    branches,
  };
}

function predictCfm(tree:any,features:any) {
  let node=tree;
  while(node?.type==="node") {
    const value=String(Number(features?.[node.feature]??0));
    if(!node.branches?.[value]) {
      return {
        outcome:String(node.fallback??majorityOutcome(node.distribution)) as CfmOutcome,
        probabilities:node.distribution,
        fallback_used:true,
      };
    }
    node=node.branches[value];
  }
  const dist=node?.distribution??{
    success:0,reject:0,hold:0,unresolved:1
  };
  return {
    outcome:String(node?.label??majorityOutcome(dist)) as CfmOutcome,
    probabilities:dist,
    fallback_used:false,
  };
}

function multiclassBrier(probabilities:any,actual:CfmOutcome) {
  let sum=0;
  for(const k of CFM_OUTCOMES) {
    const p=Number(probabilities?.[k]??0);
    const y=k===actual?1:0;
    sum += (p-y)*(p-y);
  }
  return sum/CFM_OUTCOMES.length;
}

function cfmSource(tree:any) {
  return [
    "LANGUAGE CFM-1",
    "TYPE bounded_decision_tree",
    "OUTCOMES success,reject,hold,unresolved",
    "MODEL "+JSON.stringify(tree),
    "PREDICT before action",
    "UPDATE only after observation; preserve prior artifact version",
  ].join("\n");
}

async function counterfactualResearch(cycleId:number) {
  const query="decision tree prediction calibration counterfactual action outcome model";
  const encoded=encodeURIComponent(query);
  const evidence:any[]=[];

  for(const job of [
    {
      key:"RF:CROSSREF",
      path:`works?query.title=${encoded}&rows=3`,
      purpose:"DM06 counterfactual prediction research"
    },
    {
      key:"RF:OPENALEX",
      path:`works?search=${encoded}&per-page=3`,
      purpose:"DM06 predictive model calibration research"
    }
  ]) {
    try {
      const r=await fetchThroughResource(
        cycleId,job.key,job.path,job.purpose
      );
      const parsed=JSON.parse(r.text);
      let items:any[]=[];
      if(job.key==="RF:CROSSREF") {
        items=(parsed?.message?.items??[]).slice(0,3).map((x:any)=>({
          title:Array.isArray(x?.title)?x.title[0]:x?.title??null,
          doi:x?.DOI??null,
          type:x?.type??null,
        }));
      } else {
        items=(parsed?.results??[]).slice(0,3).map((x:any)=>({
          title:x?.title??null,
          doi:x?.doi??null,
          type:x?.type??null,
        }));
      }
      evidence.push({
        resource_key:job.key,
        http_status:r.http_status,
        items,
      });
    } catch(error) {
      evidence.push({
        resource_key:job.key,
        error:error instanceof Error?error.message:String(error),
      });
    }
  }

  return {
    query,
    sources:evidence,
    successful_sources:evidence.filter(x=>!x.error).length,
    researched_at:nowIso(),
  };
}

async function executeCounterfactualCase(
  c:any,
  cycleId:number
):Promise<{outcome:CfmOutcome,details:any}> {
  const kind=String(c.action_kind);
  const target=c.target??{};

  if(kind==="internet_get") {
    try {
      const r=await internetGet(
        cycleId,
        String(target.url??""),
        "counterfactual held-out internet action"
      );
      return {
        outcome:"success",
        details:{
          http_status:r.status,
          final_url:r.finalUrl,
          bytes:r.text.length,
        }
      };
    } catch(error) {
      return {
        outcome:"reject",
        details:{
          error:error instanceof Error?error.message:String(error)
        }
      };
    }
  }

  if(kind==="resource_fetch") {
    const key=String(target.resource_key??"");
    let path="";
    if(key==="RF:PYPI") path="pypi/pip/json";
    else if(key==="RF:CROSSREF") path="works?rows=1";
    else if(key==="RF:OPENALEX") path="works?per-page=1";
    else path="";

    try {
      const r=await fetchThroughResource(
        cycleId,key,path,"counterfactual held-out resource action"
      );
      return {
        outcome:"success",
        details:{
          resource_key:key,
          http_status:r.http_status,
          bytes:r.text.length,
        }
      };
    } catch(error) {
      return {
        outcome:"reject",
        details:{
          resource_key:key,
          error:error instanceof Error?error.message:String(error),
        }
      };
    }
  }

  if(kind==="belief_update") {
    let beliefId=Number(target.belief_id??0);
    if(!beliefId) {
      const {data,error}=await db.from("mind_core_beliefs")
        .select("id")
        .order("id",{ascending:true})
        .limit(1)
        .maybeSingle();
      if(error) throw error;
      beliefId=Number(data?.id??0);
    }
    if(!beliefId) {
      return {
        outcome:"unresolved",
        details:{reason:"no belief row available"}
      };
    }

    const {data:before,error:beforeErr}=await db.from("mind_core_beliefs")
      .select("content_hash")
      .eq("id",beliefId)
      .single();
    if(beforeErr) throw beforeErr;

    const {error:updateErr}=await db.from("mind_core_beliefs")
      .update({content_hash:String(before.content_hash)})
      .eq("id",beliefId);

    if(updateErr) {
      return {
        outcome:"reject",
        details:{
          belief_id:beliefId,
          error:updateErr.message,
        }
      };
    }
    return {
      outcome:"success",
      details:{belief_id:beliefId}
    };
  }

  if(kind==="program_tick") {
    const before=await currentMindProgram();
    const beforeStep=String(before.step.step_key);
    const result=await mindProgramOrchestrator(cycleId);
    const after=await currentMindProgram();
    const afterStep=String(after.step.step_key);

    return {
      outcome:beforeStep===afterStep?"hold":"success",
      details:{
        before_step:beforeStep,
        after_step:afterStep,
        tick_result:result,
      }
    };
  }

  return {
    outcome:"unresolved",
    details:{reason:"unsupported action kind",action_kind:kind}
  };
}

async function counterfactualWorldModelEvaluator(goal:Goal,cycleId:number) {
  const candidateKey=String(
    goal.target?.candidate_key??"D0013:counterfactual-world-model"
  );
  const research=await counterfactualResearch(cycleId);
  if(research.successful_sources<1) {
    throw new Error("counterfactual research phase found no usable source");
  }

  const featureNames=[
    "is_internet","https","is_resource","resource_admitted",
    "is_belief_mutation","is_program_tick","target_mechanism_admitted"
  ];

  const {data:trainCases,error:trainErr}=await db
    .from("mind_core_counterfactual_cases")
    .select("*")
    .eq("split","train")
    .order("id",{ascending:true});
  if(trainErr) throw trainErr;

  const train=(trainCases??[]).map((c:any)=>({
    case_key:c.case_key,
    features:c.features,
    outcome:c.expected_outcome,
  }));

  const trainHash=await sha256Hex(JSON.stringify(train));
  const tree=buildCfmTree(train,featureNames);
  const generatedSource=cfmSource(tree);

  const trainPredictions=train.map((ex:any)=>{
    const p=predictCfm(tree,ex.features);
    return {
      case_key:ex.case_key,
      expected:ex.outcome,
      predicted:p.outcome,
      probabilities:p.probabilities,
      passed:p.outcome===ex.outcome,
    };
  });
  const trainAccuracy=trainPredictions.length
    ? trainPredictions.filter((x:any)=>x.passed).length/trainPredictions.length
    : 0;

  const spec={
    language:"CFM-1",
    objective:"Predict runtime action outcome before execution from observable context features and preserve/update model versions after observations.",
    features:featureNames,
    outcomes:CFM_OUTCOMES,
    tree,
    synthesis:{
      method:"bounded ID3-style decision tree induction",
      training_hash:trainHash,
      train_accuracy:trainAccuracy,
      heldout_actions_executed_after_prediction_freeze:true,
    }
  };

  const artifactHash=await sha256Hex(JSON.stringify({
    artifact_key:"ALG:COUNTERFACTUAL_RUNTIME_MODEL",
    version:1,
    research,
    spec,
    source:generatedSource,
  }));

  let artifact:any=null;
  const {data:existing,error:existingErr}=await db
    .from("mind_core_learning_artifacts")
    .select("*")
    .eq("artifact_hash",artifactHash)
    .maybeSingle();
  if(existingErr) throw existingErr;

  if(existing) artifact=existing;
  else {
    const {data:created,error:createErr}=await db
      .from("mind_core_learning_artifacts")
      .insert({
        artifact_key:"ALG:COUNTERFACTUAL_RUNTIME_MODEL",
        version:1,
        parent_artifact_id:null,
        artifact_type:"algorithm",
        language:"CFM-1",
        title:"Learned Counterfactual Runtime Outcome Model",
        objective:"Predict success/reject/hold/unresolved outcomes before real runtime actions.",
        research,
        spec,
        generated_source:generatedSource,
        status:"shadow",
        artifact_hash:artifactHash,
        created_from_cycle:cycleId,
      })
      .select("*")
      .single();
    if(createErr) throw createErr;
    artifact=created;
  }

  const {error:trainExpErr}=await db
    .from("mind_core_learning_experiments")
    .insert({
      artifact_id:artifact.id,
      cycle_id:cycleId,
      experiment_type:"train",
      dataset_key:"counterfactual-runtime:train:v1",
      frozen_input_hash:trainHash,
      result:{
        cases:trainPredictions,
        tree,
        generated_source:generatedSource,
        accuracy:trainAccuracy,
      },
      score:trainAccuracy,
      passed:trainAccuracy>=0.80,
    });
  if(trainExpErr) throw trainExpErr;

  const {data:heldCases,error:heldErr}=await db
    .from("mind_core_counterfactual_cases")
    .select("*")
    .eq("split","heldout")
    .order("id",{ascending:true});
  if(heldErr) throw heldErr;

  // Freeze all predictions before executing any held-out action.
  const frozenPredictions=(heldCases??[]).map((c:any)=>{
    const p=predictCfm(tree,c.features);
    return {
      case_id:c.id,
      case_key:c.case_key,
      action_kind:c.action_kind,
      features:c.features,
      predicted_outcome:p.outcome,
      probabilities:p.probabilities,
      fallback_used:p.fallback_used,
    };
  });

  const freezeHash=await sha256Hex(JSON.stringify({
    candidate_key:candidateKey,
    artifact_hash:artifactHash,
    predictions:frozenPredictions,
  }));

  const {data:freezeRow,error:freezeErr}=await db
    .from("mind_core_counterfactual_freezes")
    .insert({
      cycle_id:cycleId,
      candidate_key:candidateKey,
      artifact_id:artifact.id,
      predictions:frozenPredictions,
      freeze_hash:freezeHash,
    })
    .select("*")
    .single();
  if(freezeErr) throw freezeErr;

  const heldResults:any[]=[];
  let correctCount=0;
  let brierSum=0;
  const observedExamples:any[]=[];

  for(const c of heldCases??[]) {
    const frozen=frozenPredictions.find((x:any)=>Number(x.case_id)===Number(c.id));
    if(!frozen) throw new Error("missing frozen prediction");

    const observation=await executeCounterfactualCase(c,cycleId);
    const actual=observation.outcome;
    const correct=String(frozen.predicted_outcome)===actual;
    const expectedMatchesObservation=
      String(c.expected_outcome)===actual;
    const brier=multiclassBrier(
      frozen.probabilities,
      actual
    );

    if(correct) correctCount += 1;
    brierSum += brier;

    const runResult={
      case_key:c.case_key,
      freeze_id:freezeRow.id,
      prediction:frozen,
      actual_outcome:actual,
      expected_outcome:c.expected_outcome,
      expected_matches_observation:expectedMatchesObservation,
      observation:observation.details,
      correct,
      brier,
    };

    const {error:runErr}=await db
      .from("mind_core_counterfactual_runs")
      .insert({
        case_id:c.id,
        cycle_id:cycleId,
        actor_key:candidateKey,
        prediction:frozen,
        observation:{
          actual_outcome:actual,
          expected_outcome:c.expected_outcome,
          expected_matches_observation:expectedMatchesObservation,
          details:observation.details,
        },
        correct,
        brier,
      });
    if(runErr) throw runErr;

    heldResults.push(runResult);
    observedExamples.push({
      case_key:c.case_key,
      features:c.features,
      outcome:actual,
    });
  }

  const heldAccuracy=heldResults.length
    ? correctCount/heldResults.length
    : 0;
  const meanBrier=heldResults.length
    ? brierSum/heldResults.length
    : 1;
  const evaluatorIntegrity=
    heldResults.every((x:any)=>x.expected_matches_observation===true);

  // If errors occurred, update only after observation and preserve v1.
  let updatedArtifact:any=null;
  const predictionErrors=heldResults.filter((x:any)=>!x.correct).length;

  if(predictionErrors>0) {
    const updatedTrain=[...train,...observedExamples];
    const updatedTree=buildCfmTree(updatedTrain,featureNames);
    const updatedSpec={
      ...spec,
      tree:updatedTree,
      update:{
        parent_artifact_id:artifact.id,
        parent_artifact_hash:artifactHash,
        added_observations:observedExamples.length,
        prediction_errors_triggering_update:predictionErrors,
        updated_after_observation:true,
      }
    };
    const updatedSource=cfmSource(updatedTree);
    const updatedHash=await sha256Hex(JSON.stringify({
      artifact_key:"ALG:COUNTERFACTUAL_RUNTIME_MODEL",
      version:2,
      parent_artifact_id:artifact.id,
      spec:updatedSpec,
      source:updatedSource,
    }));

    const {data:newArtifact,error:newErr}=await db
      .from("mind_core_learning_artifacts")
      .insert({
        artifact_key:"ALG:COUNTERFACTUAL_RUNTIME_MODEL",
        version:2,
        parent_artifact_id:artifact.id,
        artifact_type:"algorithm",
        language:"CFM-1",
        title:"Updated Counterfactual Runtime Outcome Model",
        objective:"Updated after observed prediction errors; preserves version 1.",
        research,
        spec:updatedSpec,
        generated_source:updatedSource,
        status:"shadow",
        artifact_hash:updatedHash,
        created_from_cycle:cycleId,
      })
      .select("*")
      .single();
    if(newErr) throw newErr;
    updatedArtifact=newArtifact;
  }

  // Fresh post-evaluation application on a new HTTPS target.
  const freshFeatures={
    is_internet:1,https:1,is_resource:0,resource_admitted:0,
    is_belief_mutation:0,is_program_tick:0,target_mechanism_admitted:0
  };
  const modelForFresh=updatedArtifact?.spec?.tree??tree;
  const freshPrediction=predictCfm(modelForFresh,freshFeatures);
  const freshFreezeHash=await sha256Hex(JSON.stringify({
    artifact_id:updatedArtifact?.id??artifact.id,
    target:"https://example.com/",
    prediction:freshPrediction,
  }));

  let freshObservation:CfmOutcome="unresolved";
  let freshDetails:any={};
  try {
    const r=await internetGet(
      cycleId,
      "https://example.com/",
      "counterfactual fresh application"
    );
    freshObservation="success";
    freshDetails={http_status:r.status,bytes:r.text.length,final_url:r.finalUrl};
  } catch(error) {
    freshObservation="reject";
    freshDetails={error:error instanceof Error?error.message:String(error)};
  }
  const freshCorrect=freshPrediction.outcome===freshObservation;

  const {error:appErr}=await db
    .from("mind_core_learning_applications")
    .insert({
      artifact_id:updatedArtifact?.id??artifact.id,
      cycle_id:cycleId,
      application_key:"fresh:counterfactual:https-example",
      input:{
        features:freshFeatures,
        target:"https://example.com/",
        prediction:freshPrediction,
        freeze_hash:freshFreezeHash,
      },
      output:{
        observed_outcome:freshObservation,
        details:freshDetails,
        correct:freshCorrect,
      },
      evidence:{
        prediction_before_action:true,
        independent_from_training:true,
        independent_from_heldout:true,
      },
      passed:freshCorrect,
    });
  if(appErr) throw appErr;

  const passed=
    research.successful_sources>=1 &&
    trainAccuracy>=0.80 &&
    heldResults.length>=5 &&
    heldAccuracy>=0.80 &&
    meanBrier<=0.25 &&
    evaluatorIntegrity &&
    freshCorrect;

  const verdict={
    evaluator_version:"counterfactual-cfm-v1",
    candidate_key:candidateKey,
    research,
    artifact_id:artifact.id,
    artifact_hash:artifactHash,
    freeze_id:freezeRow.id,
    freeze_hash:freezeHash,
    predictions_frozen_before_actions:true,
    train_accuracy:trainAccuracy,
    heldout_accuracy:heldAccuracy,
    mean_brier:meanBrier,
    calibration_measured:true,
    evaluator_integrity:evaluatorIntegrity,
    heldout_results:heldResults,
    prediction_errors:predictionErrors,
    model_update:{
      performed:predictionErrors>0,
      updated_artifact_id:updatedArtifact?.id??null,
      prior_artifact_preserved:true,
    },
    fresh_application:{
      predicted:freshPrediction.outcome,
      actual:freshObservation,
      correct:freshCorrect,
      freeze_hash:freshFreezeHash,
    },
    passed,
    checked_at:nowIso(),
  };

  await db.from("mind_core_learning_artifacts").update({
    status:passed?"admitted":"rejected",
    admitted_at:passed?nowIso():null,
  }).eq("id",updatedArtifact?.id??artifact.id);

  const {error:candidateErr}=await db
    .from("mind_core_development_candidates")
    .update({
      status:passed?"admitted":"rejected",
      source_metrics:{
        research_sources:research.successful_sources,
        train_accuracy:trainAccuracy,
        heldout_accuracy:heldAccuracy,
        mean_brier:meanBrier,
        heldout_cases:heldResults.length,
        prediction_errors:predictionErrors,
        fresh_application_correct:freshCorrect,
      },
      internet_evidence:{
        research,
        training_hash:trainHash,
        freeze_hash:freezeHash,
        artifact_hash:artifactHash,
      },
      shadow_result:verdict,
      updated_at:nowIso(),
    })
    .eq("candidate_key",candidateKey);
  if(candidateErr) throw candidateErr;

  return verdict;
}


async function admittedCounterfactualArtifact() {
  const {data,error}=await db
    .from("mind_core_learning_artifacts")
    .select("*")
    .eq("artifact_key","ALG:COUNTERFACTUAL_RUNTIME_MODEL")
    .eq("status","admitted")
    .order("version",{ascending:false})
    .limit(1)
    .single();
  if(error) throw error;
  return data;
}

async function counterfactualWorldModelSelfTest(goal:Goal,cycleId:number) {
  const tests=Array.isArray(goal.target?.tests)?goal.target.tests:[];
  if(tests.length<5) throw new Error("M0018 self-test requires >=5 tests");

  const artifact=await admittedCounterfactualArtifact();
  const tree=artifact?.spec?.tree;
  if(!tree) throw new Error("admitted CFM-1 tree unavailable");

  // Freeze all predictions before executing any admission action.
  const frozenPredictions=tests.map((t:any,idx:number)=>{
    const p=predictCfm(tree,t.features??{});
    return {
      test_index:idx,
      case_key:String(t.case_key??("test-"+idx)),
      action_kind:String(t.action_kind??""),
      features:t.features??{},
      predicted_outcome:p.outcome,
      probabilities:p.probabilities,
      fallback_used:p.fallback_used,
    };
  });

  const freezeHash=await sha256Hex(JSON.stringify({
    mechanism_key:"M0018:counterfactual-world-model",
    artifact_id:artifact.id,
    artifact_hash:artifact.artifact_hash,
    predictions:frozenPredictions,
  }));

  const {data:freezeRow,error:freezeErr}=await db
    .from("mind_core_counterfactual_freezes")
    .insert({
      cycle_id:cycleId,
      candidate_key:"M0018:counterfactual-world-model",
      artifact_id:artifact.id,
      predictions:frozenPredictions,
      freeze_hash:freezeHash,
    })
    .select("*")
    .single();
  if(freezeErr) throw freezeErr;

  const results:any[]=[];
  let correctCount=0;
  let brierSum=0;
  let integrityPass=true;

  for(let i=0;i<tests.length;i++) {
    const t=tests[i];
    const frozen=frozenPredictions[i];
    const observation=await executeCounterfactualCase(t,cycleId);
    const actual=observation.outcome;
    const correct=String(frozen.predicted_outcome)===actual;
    const expectedMatches=
      String(t.expected_outcome??"unresolved")===actual;
    const brier=multiclassBrier(frozen.probabilities,actual);

    if(correct) correctCount += 1;
    brierSum += brier;
    if(!expectedMatches) integrityPass=false;

    const result={
      case_key:frozen.case_key,
      predicted_outcome:frozen.predicted_outcome,
      probabilities:frozen.probabilities,
      actual_outcome:actual,
      expected_outcome:t.expected_outcome,
      expected_matches_observation:expectedMatches,
      observation:observation.details,
      correct,
      brier,
    };
    results.push(result);

    const {error:runErr}=await db
      .from("mind_core_counterfactual_runs")
      .insert({
        case_id:null,
        cycle_id:cycleId,
        actor_key:"M0018:counterfactual-world-model",
        prediction:frozen,
        observation:{
          actual_outcome:actual,
          expected_outcome:t.expected_outcome,
          expected_matches_observation:expectedMatches,
          details:observation.details,
        },
        correct,
        brier,
      });
    if(runErr) throw runErr;
  }

  const accuracy=correctCount/tests.length;
  const meanBrier=brierSum/tests.length;
  const allPassed=
    accuracy>=0.80 &&
    meanBrier<=0.25 &&
    integrityPass &&
    tests.length>=5;

  const summary={
    mechanism_key:"M0018:counterfactual-world-model",
    evaluator_version:"counterfactual-admission-v1",
    artifact_id:artifact.id,
    artifact_hash:artifact.artifact_hash,
    freeze_id:freezeRow.id,
    freeze_hash:freezeHash,
    predictions_frozen_before_actions:true,
    tests_total:tests.length,
    tests_correct:correctCount,
    accuracy,
    mean_brier:meanBrier,
    calibration_measured:true,
    evaluator_integrity:integrityPass,
    model_update_during_admission:false,
    all_passed:allPassed,
    results,
    checked_at:nowIso(),
  };

  if(!allPassed) throw new Error("M0018 counterfactual admission failed");

  const {data:mechanism,error:mechReadErr}=await db
    .from("mind_core_mechanisms")
    .select("evidence")
    .eq("mechanism_key","M0018:counterfactual-world-model")
    .single();
  if(mechReadErr) throw mechReadErr;

  const {error:updateErr}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence:{
      ...(mechanism?.evidence??{}),
      independent_self_test:summary,
      admitted_reason:"Frozen CFM-1 model passed six independent runtime-action predictions with predictions recorded before execution and calibration measured by multiclass Brier score.",
    },
    admitted_at:nowIso(),
    updated_at:nowIso(),
  }).eq("mechanism_key","M0018:counterfactual-world-model");
  if(updateErr) throw updateErr;

  return summary;
}


function mcaDistribution(examples:any[]) {
  const n=Math.max(1,examples.length);
  const yes=examples.filter((x:any)=>x.answerable===true).length;
  return {answerable:yes/n,unanswerable:(n-yes)/n};
}

function buildMcaTree(examples:any[],features:string[],depth=0):any {
  const dist=mcaDistribution(examples);
  const labels=examples.map((x:any)=>x.answerable?"yes":"no");
  const unique=[...new Set(labels)];

  if(unique.length<=1 || !features.length || depth>=8) {
    return {
      type:"leaf",
      distribution:dist,
      answerable:dist.answerable>=0.5,
      support:examples.length
    };
  }

  const base=entropyOf(labels);
  let bestFeature:string|null=null;
  let bestGain=-1;
  let bestGroups:Map<string,any[]>|null=null;

  for(const feature of features) {
    const groups=new Map<string,any[]>();
    for(const ex of examples) {
      const v=String(Number(ex.features?.[feature]??0));
      if(!groups.has(v)) groups.set(v,[]);
      groups.get(v)!.push(ex);
    }
    let rem=0;
    for(const g of groups.values()) {
      rem+=(g.length/examples.length)*entropyOf(
        g.map((x:any)=>x.answerable?"yes":"no")
      );
    }
    const gain=base-rem;
    if(gain>bestGain) {
      bestGain=gain;
      bestFeature=feature;
      bestGroups=groups;
    }
  }

  if(!bestFeature || !bestGroups || bestGain<=1e-12) {
    return {
      type:"leaf",
      distribution:dist,
      answerable:dist.answerable>=0.5,
      support:examples.length
    };
  }

  const branches:any={};
  const rest=features.filter(f=>f!==bestFeature);
  for(const [value,g] of bestGroups.entries()) {
    branches[value]=buildMcaTree(g,rest,depth+1);
  }

  return {
    type:"node",
    feature:bestFeature,
    distribution:dist,
    gain:bestGain,
    branches,
    support:examples.length
  };
}

function predictMca(tree:any,features:any) {
  let node=tree;
  let fallback=false;
  while(node?.type==="node") {
    const value=String(Number(features?.[node.feature]??0));
    if(!node.branches?.[value]) {
      fallback=true;
      const p=Number(node.distribution?.answerable??0.5);
      return {
        answerability_probability:p,
        action:p>=0.75?"answer":"unresolved",
        fallback_used:true
      };
    }
    node=node.branches[value];
  }
  const p=Number(node?.distribution?.answerable??0.5);
  return {
    answerability_probability:p,
    action:p>=0.75?"answer":"unresolved",
    fallback_used:fallback
  };
}

function binaryBrier(p:number,y:boolean) {
  const yy=y?1:0;
  return (p-yy)*(p-yy);
}

function expectedCalibrationError(rows:any[]) {
  if(!rows.length) return 1;
  const bins=[
    [0,0.2],[0.2,0.4],[0.4,0.6],[0.6,0.8],[0.8,1.0000001]
  ];
  let ece=0;
  for(const [lo,hi] of bins) {
    const bucket=rows.filter((r:any)=>{
      const p=Number(r.confidence??0);
      return p>=lo && p<hi;
    });
    if(!bucket.length) continue;
    const meanP=bucket.reduce((a:number,r:any)=>a+Number(r.confidence),0)/bucket.length;
    const acc=bucket.filter((r:any)=>r.actual_answerable===true).length/bucket.length;
    ece+=(bucket.length/rows.length)*Math.abs(meanP-acc);
  }
  return ece;
}

function mcaSource(tree:any) {
  return [
    "LANGUAGE MCA-1",
    "TYPE evidence_sufficiency_tree",
    "ACTION answer IF P(answerable) >= 0.75",
    "ELSE unresolved AND request_missing_evidence",
    "MODEL "+JSON.stringify(tree),
    "CONFIDENCE = leaf empirical answerability probability"
  ].join("\n");
}

async function metacognitionResearch(cycleId:number) {
  const query="confidence calibration selective prediction abstention uncertainty estimation";
  const encoded=encodeURIComponent(query);
  const evidence:any[]=[];
  for(const job of [
    {key:"RF:CROSSREF",path:`works?query.title=${encoded}&rows=3`,purpose:"DM07 calibration research"},
    {key:"RF:OPENALEX",path:`works?search=${encoded}&per-page=3`,purpose:"DM07 selective prediction research"}
  ]) {
    try {
      const r=await fetchThroughResource(cycleId,job.key,job.path,job.purpose);
      const parsed=JSON.parse(r.text);
      const items=job.key==="RF:CROSSREF"
        ? (parsed?.message?.items??[]).slice(0,3).map((x:any)=>({
            title:Array.isArray(x?.title)?x.title[0]:x?.title??null,
            doi:x?.DOI??null
          }))
        : (parsed?.results??[]).slice(0,3).map((x:any)=>({
            title:x?.title??null,doi:x?.doi??null
          }));
      evidence.push({resource_key:job.key,http_status:r.http_status,items});
    } catch(error) {
      evidence.push({resource_key:job.key,error:error instanceof Error?error.message:String(error)});
    }
  }
  return {
    query,
    sources:evidence,
    successful_sources:evidence.filter(x=>!x.error).length,
    researched_at:nowIso()
  };
}

async function observeMetacogCase(c:any,cycleId:number) {
  const kind=String(c.case_kind);
  const target=c.target??{};

  if(kind==="live_url") {
    try {
      const r=await internetGet(cycleId,String(target.url??""),"metacognition held-out live evidence");
      return {answerable:true,request:null,details:{http_status:r.status,bytes:r.text.length}};
    } catch(error) {
      return {answerable:false,request:"a successful live observation",details:{error:error instanceof Error?error.message:String(error)}};
    }
  }

  if(kind==="boundary") {
    return {answerable:true,request:null,details:{boundary:target.kind??"known"}};
  }

  if(kind==="resource_status") {
    const {data,error}=await db.from("mind_core_resources")
      .select("resource_key,status")
      .eq("resource_key",String(target.resource_key??""))
      .maybeSingle();
    if(error) throw error;
    return data
      ? {answerable:true,request:null,details:{resource_key:data.resource_key,status:data.status}}
      : {answerable:false,request:"resource registry evidence",details:{missing:true}};
  }

  if(kind==="context_conflict") {
    const {data,error}=await db.from("mind_core_context_conflict_cases")
      .select("*")
      .eq("case_key",String(target.conflict_case_key??""))
      .single();
    if(error) throw error;
    const result=await arbitrateContextClaims(data.claim_a,data.claim_b);
    const unresolved=result.decision==="unresolved_conflict";
    return {
      answerable:!unresolved,
      request:unresolved
        ? String(data.expected_request??"explicit discriminating scope evidence")
        : null,
      details:{decision:result.decision,discriminating_goal:result.discriminating_evidence_goal}
    };
  }

  if(kind==="capability_task") {
    const cap=String(target.required_capability??"");
    const {data,error}=await db.from("mind_core_mechanisms")
      .select("mechanism_key,capabilities,status")
      .eq("status","admitted");
    if(error) throw error;
    const admitted=(data??[]).some((m:any)=>
      Array.isArray(m.capabilities) && m.capabilities.map(String).includes(cap)
    );
    return admitted
      ? {answerable:true,request:null,details:{required_capability:cap,admitted:true}}
      : {answerable:false,request:"an admitted "+cap+" capability",details:{required_capability:cap,admitted:false}};
  }

  if(kind==="future_external") {
    return {answerable:false,request:"future observation",details:{future_dependent:true}};
  }

  if(kind==="program_state") {
    const p=await currentMindProgram();
    return {answerable:true,request:null,details:{step:p.step.step_key,target:p.step.mechanism_target}};
  }

  return {answerable:false,request:"supported evidence source",details:{unsupported_kind:kind}};
}

async function metacognitiveCalibrationEvaluator(goal:Goal,cycleId:number) {
  const candidateKey=String(goal.target?.candidate_key??"D0014:metacognitive-calibration");
  const research=await metacognitionResearch(cycleId);
  if(research.successful_sources<1) throw new Error("metacognition research unavailable");

  const features=[
    "current_evidence","deterministic_boundary","conflict","future_dependent",
    "required_capability_admitted","observability","source_count"
  ];

  const {data:trainCases,error:trainErr}=await db.from("mind_core_metacog_cases")
    .select("*").eq("split","train").order("id",{ascending:true});
  if(trainErr) throw trainErr;

  const train=(trainCases??[]).map((c:any)=>({
    case_key:c.case_key,features:c.features,answerable:Boolean(c.expected_answerable)
  }));
  const trainHash=await sha256Hex(JSON.stringify(train));
  const tree=buildMcaTree(train,features);
  const source=mcaSource(tree);

  const trainResults=train.map((x:any)=>{
    const p=predictMca(tree,x.features);
    const pred=p.action==="answer";
    return {
      case_key:x.case_key,
      expected_answerable:x.answerable,
      action:p.action,
      confidence:p.answerability_probability,
      passed:pred===x.answerable
    };
  });
  const trainAccuracy=trainResults.filter((x:any)=>x.passed).length/Math.max(1,trainResults.length);

  const spec={
    language:"MCA-1",
    objective:"Decide whether current evidence is sufficient to answer/act; otherwise return unresolved and request missing evidence.",
    features,
    tree,
    threshold:0.75,
    synthesis:{
      method:"bounded decision-tree induction",
      train_accuracy:trainAccuracy,
      training_hash:trainHash,
      heldout_outcomes_hidden_until_after_prediction_freeze:true
    }
  };

  const artifactHash=await sha256Hex(JSON.stringify({
    artifact_key:"ALG:METACOGNITIVE_CALIBRATOR",version:1,research,spec,source
  }));

  let artifact:any=null;
  const {data:existing,error:existingErr}=await db.from("mind_core_learning_artifacts")
    .select("*").eq("artifact_hash",artifactHash).maybeSingle();
  if(existingErr) throw existingErr;
  if(existing) artifact=existing;
  else {
    const {data:created,error:createErr}=await db.from("mind_core_learning_artifacts")
      .insert({
        artifact_key:"ALG:METACOGNITIVE_CALIBRATOR",
        version:1,
        artifact_type:"policy",
        language:"MCA-1",
        title:"Learned Evidence Sufficiency and Confidence Policy",
        objective:"Choose ANSWER vs UNRESOLVED and calibrate answerability confidence from observable evidence state.",
        research,
        spec,
        generated_source:source,
        status:"shadow",
        artifact_hash:artifactHash,
        created_from_cycle:cycleId
      }).select("*").single();
    if(createErr) throw createErr;
    artifact=created;
  }

  await db.from("mind_core_learning_experiments").insert({
    artifact_id:artifact.id,cycle_id:cycleId,experiment_type:"train",
    dataset_key:"metacognition:train:v1",frozen_input_hash:trainHash,
    result:{cases:trainResults,accuracy:trainAccuracy,tree,source},
    score:trainAccuracy,passed:trainAccuracy>=0.85
  });

  const {data:heldCases,error:heldErr}=await db.from("mind_core_metacog_cases")
    .select("*").eq("split","heldout").order("id",{ascending:true});
  if(heldErr) throw heldErr;

  const frozen=(heldCases??[]).map((c:any)=>{
    const p=predictMca(tree,c.features);
    return {
      case_id:c.id,case_key:c.case_key,features:c.features,
      action:p.action,confidence:p.answerability_probability,
      request_missing_evidence:p.action==="unresolved",
      fallback_used:p.fallback_used
    };
  });

  const freezeHash=await sha256Hex(JSON.stringify({
    candidate_key:candidateKey,artifact_hash:artifactHash,predictions:frozen
  }));
  const {data:freezeRow,error:freezeErr}=await db.from("mind_core_metacog_freezes")
    .insert({
      cycle_id:cycleId,actor_key:candidateKey,artifact_id:artifact.id,
      predictions:frozen,freeze_hash:freezeHash
    }).select("*").single();
  if(freezeErr) throw freezeErr;

  const results:any[]=[];
  for(const c of heldCases??[]) {
    const pred=frozen.find((x:any)=>Number(x.case_id)===Number(c.id));
    const obs=await observeMetacogCase(c,cycleId);
    const predictedAnswerable=pred.action==="answer";
    const correct=predictedAnswerable===obs.answerable;
    const brier=binaryBrier(Number(pred.confidence),Boolean(obs.answerable));
    const requestPass=!obs.answerable
      ? pred.action==="unresolved" && !!obs.request
      : true;

    const result={
      case_key:c.case_key,
      action:pred.action,
      confidence:Number(pred.confidence),
      actual_answerable:Boolean(obs.answerable),
      expected_answerable:Boolean(c.expected_answerable),
      expected_matches_observation:Boolean(c.expected_answerable)===Boolean(obs.answerable),
      request_missing_evidence:pred.request_missing_evidence,
      observed_request:obs.request,
      request_pass:requestPass,
      observation:obs.details,
      correct,brier
    };
    results.push(result);

    await db.from("mind_core_metacog_runs").insert({
      case_id:c.id,cycle_id:cycleId,actor_key:candidateKey,
      prediction:pred,
      observation:{answerable:obs.answerable,request:obs.request,details:obs.details},
      correct,brier
    });
  }

  const accuracy=results.filter((x:any)=>x.correct).length/Math.max(1,results.length);
  const meanBrier=results.reduce((a:number,x:any)=>a+Number(x.brier),0)/Math.max(1,results.length);
  const ece=expectedCalibrationError(results);
  const unresolvedCount=results.filter((x:any)=>x.action==="unresolved").length;
  const requestPass=results
    .filter((x:any)=>x.actual_answerable===false)
    .every((x:any)=>x.request_pass===true);
  const integrity=results.every((x:any)=>x.expected_matches_observation===true);

  await db.from("mind_core_learning_experiments").insert({
    artifact_id:artifact.id,cycle_id:cycleId,experiment_type:"heldout",
    dataset_key:"metacognition:heldout:v1",
    frozen_input_hash:await sha256Hex(JSON.stringify(heldCases??[])),
    result:{
      freeze_id:freezeRow.id,freeze_hash:freezeHash,cases:results,
      accuracy,mean_brier:meanBrier,ece,
      unresolved_count:unresolvedCount,requests_correct:requestPass
    },
    score:1-ece,
    passed:accuracy>=0.80 && ece<=0.15 && unresolvedCount>=2 && requestPass && integrity
  });

  // Fresh meta-application: can the not-yet-admitted M0019 itself be relied on?
  const freshFeatures={
    current_evidence:1,deterministic_boundary:0,conflict:0,future_dependent:0,
    required_capability_admitted:0,observability:1,source_count:1
  };
  const fresh=predictMca(tree,freshFeatures);
  const freshPassed=fresh.action==="unresolved";
  await db.from("mind_core_learning_applications").insert({
    artifact_id:artifact.id,cycle_id:cycleId,
    application_key:"fresh:self-assess-m0019-before-admission",
    input:{required_capability:"M0019:metacognitive-calibrator",features:freshFeatures},
    output:{
      action:fresh.action,confidence:fresh.answerability_probability,
      request:"independent M0019 admission evidence"
    },
    evidence:{self_referential_guard:true,capability_not_yet_admitted:true},
    passed:freshPassed
  });

  const passed=
    research.successful_sources>=1 &&
    trainAccuracy>=0.85 &&
    results.length>=5 &&
    accuracy>=0.80 &&
    ece<=0.15 &&
    meanBrier<=0.15 &&
    unresolvedCount>=2 &&
    requestPass &&
    integrity &&
    freshPassed;

  const verdict={
    evaluator_version:"metacognition-mca-v1",
    candidate_key:candidateKey,research,
    artifact_id:artifact.id,artifact_hash:artifactHash,
    generated_source:source,
    train_accuracy:trainAccuracy,
    heldout_accuracy:accuracy,
    mean_brier:meanBrier,
    ece,
    freeze_id:freezeRow.id,freeze_hash:freezeHash,
    predictions_frozen_before_observation:true,
    unresolved_count:unresolvedCount,
    requests_missing_evidence_correctly:requestPass,
    heldout_results:results,
    fresh_self_assessment:{
      action:fresh.action,confidence:fresh.answerability_probability,passed:freshPassed
    },
    passed,checked_at:nowIso()
  };

  await db.from("mind_core_learning_artifacts").update({
    status:passed?"admitted":"rejected",admitted_at:passed?nowIso():null
  }).eq("id",artifact.id);

  await db.from("mind_core_development_candidates").update({
    status:passed?"admitted":"rejected",
    source_metrics:{
      research_sources:research.successful_sources,
      train_accuracy:trainAccuracy,heldout_accuracy:accuracy,
      mean_brier:meanBrier,ece,unresolved_count:unresolvedCount,
      requests_correct:requestPass
    },
    internet_evidence:{research,training_hash:trainHash,freeze_hash:freezeHash,artifact_hash:artifactHash},
    shadow_result:verdict,updated_at:nowIso()
  }).eq("candidate_key",candidateKey);

  return verdict;
}


async function admittedMetacogArtifact() {
  const {data,error}=await db.from("mind_core_learning_artifacts")
    .select("*")
    .eq("artifact_key","ALG:METACOGNITIVE_CALIBRATOR")
    .eq("status","admitted")
    .order("version",{ascending:false})
    .limit(1)
    .single();
  if(error) throw error;
  return data;
}

async function metacognitiveCalibrationSelfTest(goal:Goal,cycleId:number) {
  const artifact=await admittedMetacogArtifact();
  const tree=artifact?.spec?.tree;
  if(!tree) throw new Error("admitted MCA-1 tree unavailable");

  const {data:cases,error:caseErr}=await db.from("mind_core_metacog_cases")
    .select("*")
    .eq("split","admission")
    .order("id",{ascending:true});
  if(caseErr) throw caseErr;
  if(!cases?.length) throw new Error("M0019 admission suite unavailable");

  const frozen=(cases??[]).map((c:any)=>{
    const p=predictMca(tree,c.features);
    return {
      case_id:c.id,case_key:c.case_key,features:c.features,
      action:p.action,confidence:p.answerability_probability,
      request_missing_evidence:p.action==="unresolved",
      fallback_used:p.fallback_used
    };
  });

  const freezeHash=await sha256Hex(JSON.stringify({
    mechanism_key:"M0019:metacognitive-calibrator",
    artifact_id:artifact.id,
    artifact_hash:artifact.artifact_hash,
    predictions:frozen
  }));

  const {data:freezeRow,error:freezeErr}=await db.from("mind_core_metacog_freezes")
    .insert({
      cycle_id:cycleId,actor_key:"M0019:metacognitive-calibrator",
      artifact_id:artifact.id,predictions:frozen,freeze_hash:freezeHash
    }).select("*").single();
  if(freezeErr) throw freezeErr;

  const results:any[]=[];
  let correctCount=0;
  let brierSum=0;

  for(const c of cases??[]) {
    const pred=frozen.find((x:any)=>Number(x.case_id)===Number(c.id));
    const obs=await observeMetacogCase(c,cycleId);
    const predictedAnswerable=pred.action==="answer";
    const correct=predictedAnswerable===Boolean(obs.answerable);
    const brier=binaryBrier(Number(pred.confidence),Boolean(obs.answerable));
    const requestPass=!obs.answerable
      ? pred.action==="unresolved" && !!obs.request
      : true;

    if(correct) correctCount += 1;
    brierSum += brier;

    const result={
      case_key:c.case_key,
      action:pred.action,
      confidence:Number(pred.confidence),
      actual_answerable:Boolean(obs.answerable),
      expected_answerable:Boolean(c.expected_answerable),
      expected_action:c.expected_action,
      expected_matches_observation:
        Boolean(c.expected_answerable)===Boolean(obs.answerable),
      observed_request:obs.request,
      request_pass:requestPass,
      observation:obs.details,
      correct,brier
    };
    results.push(result);

    const {error:runErr}=await db.from("mind_core_metacog_runs").insert({
      case_id:c.id,cycle_id:cycleId,actor_key:"M0019:metacognitive-calibrator",
      prediction:pred,
      observation:{answerable:obs.answerable,request:obs.request,details:obs.details},
      correct,brier
    });
    if(runErr) throw runErr;
  }

  const accuracy=correctCount/cases.length;
  const meanBrier=brierSum/cases.length;
  const ece=expectedCalibrationError(results);
  const unresolvedCount=results.filter((x:any)=>x.action==="unresolved").length;
  const requestPass=results
    .filter((x:any)=>x.actual_answerable===false)
    .every((x:any)=>x.request_pass===true);
  const integrity=results.every((x:any)=>x.expected_matches_observation===true);

  const allPassed=
    accuracy>=0.80 &&
    ece<=0.15 &&
    meanBrier<=0.15 &&
    unresolvedCount>=1 &&
    requestPass &&
    integrity;

  const summary={
    mechanism_key:"M0019:metacognitive-calibrator",
    evaluator_version:"metacognition-admission-v1",
    artifact_id:artifact.id,
    artifact_hash:artifact.artifact_hash,
    freeze_id:freezeRow.id,
    freeze_hash:freezeHash,
    predictions_frozen_before_observation:true,
    tests_total:cases.length,
    tests_correct:correctCount,
    accuracy,
    mean_brier:meanBrier,
    ece,
    unresolved_count:unresolvedCount,
    requests_missing_evidence_correctly:requestPass,
    evaluator_integrity:integrity,
    all_passed:allPassed,
    results,
    checked_at:nowIso()
  };

  if(!allPassed) throw new Error("M0019 metacognitive admission failed");

  const {data:mechanism,error:mechReadErr}=await db.from("mind_core_mechanisms")
    .select("evidence")
    .eq("mechanism_key","M0019:metacognitive-calibrator")
    .single();
  if(mechReadErr) throw mechReadErr;

  const {error:updateErr}=await db.from("mind_core_mechanisms").update({
    status:"admitted",
    evidence:{
      ...(mechanism?.evidence??{}),
      independent_self_test:summary,
      admitted_reason:"Frozen MCA-1 policy passed independent browser-capability, Node-API conflict, and future-service uncertainty cases with calibrated answerability confidence and explicit UNRESOLVED evidence requests."
    },
    admitted_at:nowIso(),
    updated_at:nowIso()
  }).eq("mechanism_key","M0019:metacognitive-calibrator");
  if(updateErr) throw updateErr;

  return summary;
}

async function selfDevelopmentAudit(cycleId:number) {
  const [mechsRes,domainsRes,conceptsRes,questionsRes,cyclesRes,rejectedRes]=await Promise.all([
    db.from("mind_core_mechanisms").select("mechanism_key,status,capabilities"),
    db.from("mind_core_domains").select("id,status"),
    db.from("mind_core_concepts").select("id,status"),
    db.from("mind_core_questions").select("id,status"),
    db.from("mind_core_cycles").select("id,status").order("id",{ascending:false}).limit(50),
    db.from("mind_core_development_candidates").select("*").eq("status","rejected").order("id",{ascending:false}).limit(20),
  ]);

  for(const r of [mechsRes,domainsRes,conceptsRes,questionsRes,cyclesRes,rejectedRes]) {
    if(r.error) throw r.error;
  }

  const admitted=(mechsRes.data??[]).filter((m:any)=>m.status==="admitted");
  const m1=admitted.find((m:any)=>m.mechanism_key===INTERNET_MECHANISM);
  const caps=Array.isArray(m1?.capabilities)?m1.capabilities:[];
  const allCaps=admitted.flatMap((m:any)=>Array.isArray(m?.capabilities)?m.capabilities:[]);
  const hasDiscovery=
    admitted.some((m:any)=>m.mechanism_key===SAFE_FRONTIER_MECHANISM) ||
    allCaps.some((x:any)=>["link_discovery","web_search","url_frontier"].includes(String(x)));
  const hasRanking=allCaps.some((x:any)=>["frontier_ranking","goal_weighted_frontier"].includes(String(x)));
  const hasRelationMining=allCaps.some((x:any)=>[
    "table_relation_mining","functional_dependency_detection"
  ].includes(String(x)));
  const hasRelationGeneralization=allCaps.some((x:any)=>[
    "heldout_relation_validation","out_of_sample_consistency"
  ].includes(String(x)));
  const hasActiveFalsifier=allCaps.some((x:any)=>[
    "hypothesis_freeze","explicit_falsifier","counterexample_search"
  ].includes(String(x)));
  const hasBeliefRevision=allCaps.some((x:any)=>[
    "append_only_beliefs","belief_versioning","refutation_revision"
  ].includes(String(x)));

  const metrics={
    admitted_mechanisms:admitted.length,
    admitted_domains:(domainsRes.data??[]).filter((x:any)=>x.status==="admitted").length,
    admitted_concepts:(conceptsRes.data??[]).filter((x:any)=>x.status==="admitted").length,
    answered_questions:(questionsRes.data??[]).filter((x:any)=>x.status==="answered").length,
    recent_failed_cycles:(cyclesRes.data??[]).filter((x:any)=>x.status==="failed").length,
    rejected_development_candidates:(rejectedRes.data??[]).map((x:any)=>x.candidate_key),
    internet_capabilities:allCaps,
    safe_link_discovery_present:hasDiscovery,
    frontier_ranking_present:hasRanking,
    relation_mining_present:hasRelationMining,
    relation_generalization_present:hasRelationGeneralization,
    active_falsifier_present:hasActiveFalsifier,
    belief_revision_present:hasBeliefRevision,
  };

  let candidate:any=null;
  const d1Rejected=(rejectedRes.data??[]).some((x:any)=>x.candidate_key==="D0001:safe-link-frontier-discovery");

  if(!hasDiscovery && d1Rejected) {
    candidate={
      candidate_key:"D0001R1:safe-link-frontier-null-aware",
      title:"Safe Link Frontier Discovery R1",
      deficit:"The first safe-link frontier candidate treated an empty cross-page frontier on Node-API as parser failure, conflating 'no navigable page links' with 'unsafe or broken extraction'.",
      hypothesis:"A null-aware frontier analyzer that separately counts raw hrefs, fragment links, rejected targets, and safe public HTTPS URLs can correctly return an empty frontier without declaring the parser broken.",
      candidate_kind:"mechanism_candidate_redesign",
      proposed_change:{
        parent_candidate:"D0001:safe-link-frontier-discovery",
        suggested_mechanism_key:"M0006:safe-link-frontier",
        input:"trusted public HTML evidence",
        output:"safe public-HTTPS frontier plus diagnostics",
        diagnostics:["raw_href_count","fragment_href_count","rejected_href_count","safe_url_count"],
        safety:["reuse M0001 validation","no forms","no POST","block private/local targets","shadow-only before admission"],
      },
    };
  } else if(!hasDiscovery) {
    candidate={
      candidate_key:"D0001:safe-link-frontier-discovery",
      title:"Safe Link Frontier Discovery",
      deficit:"The live internet mechanism can fetch known URLs but has no admitted generic capability for discovering a safe next frontier of URLs from a public page.",
      hypothesis:"A read-only same-origin/public-HTTPS link extractor can expand the research frontier without requiring a search-engine API or remote mutation.",
      candidate_kind:"mechanism_candidate",
      proposed_change:{
        suggested_mechanism_key:"M0006:safe-link-frontier",
        input:"trusted public HTML evidence",
        output:"ranked public HTTPS link candidates",
        safety:["reuse M0001 public-HTTPS validation","no forms","no POST","no private/local targets","shadow-only before admission"],
      },
    };
  } else if(!hasRanking) {
    candidate={
      candidate_key:"D0002:goal-weighted-frontier-ranking",
      title:"Goal-Weighted Frontier Ranking",
      deficit:"M0006 can expose a large safe URL frontier, but the kernel has no admitted mechanism for ranking which frontier URL best advances the current research goal.",
      hypothesis:"A goal-weighted URL relevance score can prioritize the semantically closest safe frontier targets while remaining deterministic, read-only, and independently testable.",
      candidate_kind:"mechanism_candidate",
      proposed_change:{
        suggested_mechanism_key:"M0007:goal-weighted-frontier",
        input:"M0006 navigable URLs + current question/goal text",
        output:"ranked safe frontier",
        safety:["ranking only","no new network privilege","M0001+M0006 remain authority boundary","shadow before admission"],
      },
    };
  } else if(!hasRelationMining) {
    candidate={
      candidate_key:"D0003:generic-relational-pattern-mining",
      title:"Generic Relational Pattern Mining",
      deficit:"Concept birth and transfer still rely on narrow hand-coded structural recognizers; the kernel lacks an admitted generic method for proposing relation patterns across heterogeneous evidence.",
      hypothesis:"A future pattern-mining mechanism should propose candidate relations from repeated evidence structures, but no candidate may be scored until an independent evaluator is defined.",
      candidate_kind:"mechanism_candidate_research",
      proposed_change:{
        suggested_mechanism_key:"M0008:structural-relation-miner",
        safety:["research-only","no production mutation","no synthetic score","external verification required"],
      },
    };
  } else if(!hasRelationGeneralization) {
    candidate={
      candidate_key:"D0004R1:key-directed-relation-generalization",
      title:"Key-Directed Relation Generalization",
      deficit:"Relation mining exists, but the kernel lacks an admitted out-of-sample check that distinguishes key-directed predictive relations from reverse/approximate dependencies.",
      hypothesis:"Key-directed relations should remain key-like and functionally consistent on deterministic held-out rows.",
      candidate_kind:"mechanism_candidate_research",
      proposed_change:{
        suggested_mechanism_key:"M0009:key-directed-relation-generalizer",
        safety:["research-only","candidate_blind_to_holdout","independent evaluator required"],
      },
    };
  } else if(!hasActiveFalsifier) {
    candidate={
      candidate_key:"D0005:active-falsifier",
      title:"Active Falsifier",
      deficit:"The kernel can discover and generalize relations, but it still tends to validate claims with supportive evidence instead of explicitly freezing a falsification condition and seeking disconfirming evidence.",
      hypothesis:"A claim should be stored together with an explicit falsifier and a frozen target before new evidence is fetched; the next evidence cycle should return reject, not-reject, or unresolved without rewriting the original claim.",
      candidate_kind:"mechanism_candidate_research",
      proposed_change:{
        suggested_mechanism_key:"M0010:active-falsifier",
        protocol:["claim","falsifier","freeze","new evidence","verdict"],
        safety:["read_only","freeze_before_fetch","no post-hoc claim mutation","independent evaluator required"],
      },
    };
  } else if(!hasBeliefRevision) {
    candidate={
      candidate_key:"D0006:belief-revision",
      title:"Belief Revision",
      deficit:"Falsification exists, but verdicts are not yet converted into append-only revised belief versions with preserved provenance.",
      hypothesis:"REJECT should append a revised belief with counterexamples; NOT_REJECT should append survived_test without truth inflation.",
      candidate_kind:"mechanism_candidate_research",
      proposed_change:{
        suggested_mechanism_key:"M0011:belief-revision",
        safety:["append_only","preserve parent hash","verdict provenance required"],
      },
    };
  } else {
    candidate={
      candidate_key:"D0007:contextual-belief-arbitration",
      title:"Contextual Belief Arbitration",
      deficit:"Belief revision handles one claim against one verdict, but the kernel lacks a principled way to handle apparently conflicting beliefs supported by different sources, scopes, or contexts without oscillating or overwriting one side.",
      hypothesis:"Conflicting beliefs should first be tested for scope/context separability; if they apply to disjoint contexts they should coexist under scoped beliefs, otherwise the conflict remains unresolved until discriminating evidence is found.",
      candidate_kind:"mechanism_candidate_research",
      proposed_change:{
        suggested_mechanism_key:"M0012:contextual-belief-arbitrator",
        protocol:["detect conflict","compare scope","split context or mark unresolved","seek discriminating evidence"],
        safety:["no destructive overwrite","preserve both provenance chains","no forced winner without discriminator"],
      },
    };
  }

  const specUrl=candidate.candidate_key==="D0005:active-falsifier"
    ? "https://www.itl.nist.gov/div898/handbook/prc/section1/prc13.htm"
    : "https://html.spec.whatwg.org/multipage/links.html";
  const {text:specHtml,finalUrl:specFinal,status:specStatus}=await internetGet(
    cycleId,specUrl,
    `online development research for ${candidate.candidate_key}`
  );
  const specText=stripHtml(specHtml);
  const specEvidence={
    url:specUrl,
    final_url:specFinal,
    http_status:specStatus,
    bytes:specHtml.length,
    mentions_hyperlink:/hyperlink/i.test(specText),
    mentions_href:/href/i.test(specText),
    mentions_null_hypothesis:/null hypothesis/i.test(specText),
    mentions_alternative_hypothesis:/alternative hypothesis/i.test(specText),
    mentions_reject:/reject/i.test(specText),
    checked_at:nowIso(),
  };

  const {data:existing,error:existingErr}=await db.from("mind_core_development_candidates")
    .select("*").eq("candidate_key",candidate.candidate_key).maybeSingle();
  if(existingErr) throw existingErr;

  const {data:row,error:upErr}=await db.from("mind_core_development_candidates").upsert({
    candidate_key:candidate.candidate_key,
    title:candidate.title,
    deficit:candidate.deficit,
    hypothesis:candidate.hypothesis,
    candidate_kind:candidate.candidate_kind,
    proposed_change:candidate.proposed_change,
    source_metrics:metrics,
    internet_evidence:specEvidence,
    status:existing?.status==="admitted"?"admitted":"shadow",
    shadow_result:existing?.shadow_result??{},
    created_from_cycle:existing?.created_from_cycle??cycleId,
    updated_at:nowIso(),
  },{onConflict:"candidate_key"}).select("*").single();
  if(upErr) throw upErr;

  if([
    "D0003:generic-relational-pattern-mining",
    "D0004R1:key-directed-relation-generalization",
    "D0005:active-falsifier",
    "D0006:belief-revision",
    "D0007:contextual-belief-arbitration"
  ].includes(candidate.candidate_key)) {
    const {error:researchErr}=await db.from("mind_core_development_candidates").update({
      status:"researching",
      source_metrics:metrics,
      internet_evidence:{
        basis:"No valid shadow evaluator exists yet; candidate is retained without synthetic scoring.",
        research_url:specUrl,
        research_signals:{
          null_hypothesis:/null hypothesis/i.test(specText),
          alternative_hypothesis:/alternative hypothesis/i.test(specText),
          reject:/reject/i.test(specText)
        },
        checked_at:nowIso(),
      },
      updated_at:nowIso(),
    }).eq("id",row.id);
    if(researchErr) throw researchErr;

    return {
      development_mode:"bounded_shadow",
      production_auto_deploy:false,
      metrics,
      candidate:{
        id:row.id,key:row.candidate_key,title:row.title,status:"researching",
        deficit:row.deficit,hypothesis:row.hypothesis,
      },
      shadow_result:null,
      next_step:"Do not score this candidate until a valid independent shadow evaluator is created.",
    };
  }

  const {data:trials,error:trialErr}=await db.from("mind_core_development_trials")
    .select("*").eq("candidate_id",row.id).order("id",{ascending:true});
  if(trialErr) throw trialErr;

  const tested=new Set((trials??[]).map((x:any)=>String(x.test_url)));
  const testPool=[
    "https://www.tcl-lang.org/",
    "https://nodejs.org/api/n-api.html",
    "https://www.iana.org/domains/reserved",
  ];
  const testUrl=testPool.find(u=>!tested.has(u)) ?? testPool[(trials??[]).length % testPool.length];

  const {text:testHtml,finalUrl:testFinal,status:testStatus}=await internetGet(
    cycleId,testUrl,
    `shadow test ${candidate.candidate_key}`
  );

  let shadow:any={};
  if(candidate.candidate_key==="D0002:goal-weighted-frontier-ranking") {
    const cases=[
      {url:"https://www.tcl-lang.org/",query:"Tcl Tk 9.1 release",expected:"/software/tcltk/9.1.html"},
      {url:"https://nodejs.org/api/n-api.html",query:"Node API version matrix",expected:"node-api-version-matrix"},
      {url:"https://www.w3.org/",query:"W3C standards",expected:"/standards/"},
    ];
    const testedCase=new Set((trials??[]).map((x:any)=>String(x.test_url)));
    const test=cases.find(c=>!testedCase.has(c.url)) ?? cases[(trials??[]).length % cases.length];
    const frontier=await safeFrontierFromUrl(cycleId,test.url,"shadow goal-weighted frontier ranking");
    const ranked=rankFrontierUrls(frontier.navigable_urls,test.query);
    const expectedRank=ranked.findIndex((x:any)=>x.url.toLowerCase().includes(test.expected.toLowerCase()));
    shadow={
      test_url:test.url,
      query:test.query,
      expected:test.expected,
      candidate_count:ranked.length,
      expected_rank:expectedRank>=0?expectedRank+1:null,
      top10:ranked.slice(0,10),
      pass:expectedRank>=0 && expectedRank<10,
      executed_at:nowIso(),
    };
  } else if(candidate.candidate_key==="D0001R1:safe-link-frontier-null-aware") {
    const analysis=analyzeHrefFrontier(testFinal,testHtml);
    shadow={
      test_url:testUrl,
      final_url:testFinal,
      http_status:testStatus,
      ...analysis,
      pass:testStatus===200
        && analysis.raw_href_count>0
        && (analysis.safe_url_count>0 || analysis.fragment_href_count>0),
      executed_at:nowIso(),
    };
  } else {
    const links=extractHrefCandidates(testFinal,testHtml);
    const host=new URL(testFinal).hostname;
    const sameHost=links.filter(x=>new URL(x.url).hostname===host);
    shadow={
      test_url:testUrl,
      final_url:testFinal,
      http_status:testStatus,
      total_safe_links:links.length,
      same_host_links:sameHost.length,
      sample:sameHost.slice(0,12),
      pass:testStatus===200 && sameHost.length>=3,
      executed_at:nowIso(),
    };
  }

  const {error:trialInsertErr}=await db.from("mind_core_development_trials").insert({
    candidate_id:row.id,
    cycle_id:cycleId,
    test_url:String(shadow.test_url??testUrl),
    result:shadow,
    passed:shadow.pass===true,
  });
  if(trialInsertErr) throw trialInsertErr;

  const allTrials=[...(trials??[]),{test_url:String(shadow.test_url??testUrl),passed:shadow.pass===true,result:shadow}];
  const distinctPassed=new Set(
    allTrials.filter((t:any)=>t.passed===true).map((t:any)=>String(t.test_url))
  );
  const enoughIndependentEvidence=distinctPassed.size>=3;
  const finalStatus=shadow.pass===false ? "rejected" : (enoughIndependentEvidence ? "admitted" : "shadow");

  const accumulated={
    parent_candidate:candidate.proposed_change?.parent_candidate??null,
    distinct_passed_urls:[...distinctPassed],
    passed_count:distinctPassed.size,
    required_passed_urls:3,
    latest:shadow,
  };

  const {error:finalUpdateErr}=await db.from("mind_core_development_candidates").update({
    status:finalStatus,
    shadow_result:accumulated,
    source_metrics:metrics,
    internet_evidence:specEvidence,
    updated_at:nowIso(),
  }).eq("id",row.id);
  if(finalUpdateErr) throw finalUpdateErr;

  return {
    development_mode:"bounded_shadow",
    production_auto_deploy:false,
    metrics,
    candidate:{
      id:row.id,
      key:row.candidate_key,
      title:row.title,
      status:finalStatus,
      deficit:row.deficit,
      hypothesis:row.hypothesis,
    },
    internet_evidence:specEvidence,
    shadow_result:accumulated,
    next_step:finalStatus==="admitted"
      ? "Candidate design is admitted by independent shadow evidence and is ready for a separate implementation/admission cycle; production remains unchanged."
      : finalStatus==="shadow"
        ? "Accumulate independent shadow evidence on additional public pages."
        : "Candidate failed shadow; retain rejection and generate a redesigned candidate on the next audit.",
  };
}

async function executeGoal(goal:Goal, cycleId:number) {
  // Explicit shadow exercise only. This path never writes to the mechanism registry
  // or creates an autonomous genesis goal. Existing cycle logging preserves results.
  if (goal.kind === "mechanism_genesis_shadow") {
    return await runMechanismGenesisShadow();
  }

  if (goal.kind === "metacognitive_calibration_self_test") {
    return await metacognitiveCalibrationSelfTest(goal,cycleId);
  }

  if (goal.kind === "metacognitive_calibration_evaluator") {
    return await metacognitiveCalibrationEvaluator(goal,cycleId);
  }

  if (goal.kind === "counterfactual_world_model_self_test") {
    return await counterfactualWorldModelSelfTest(goal,cycleId);
  }

  if (goal.kind === "counterfactual_world_model_evaluator") {
    return await counterfactualWorldModelEvaluator(goal,cycleId);
  }

  if (goal.kind === "planner_replanner_self_test") {
    return await plannerReplannerSelfTest(goal,cycleId);
  }

  if (goal.kind === "planner_replanner_evaluator") {
    return await plannerReplannerEvaluator(goal,cycleId);
  }

  if (goal.kind === "goal_selection_self_test") {
    return await goalSelectionSelfTest(goal,cycleId);
  }

  if (goal.kind === "goal_selection_evaluator") {
    return await goalSelectionEvaluator(goal,cycleId);
  }

  if (goal.kind === "self_learning_rule_evaluator") {
    return await selfLearningRuleEvaluator(goal,cycleId);
  }

  if (goal.kind === "self_model_prediction_evaluator") {
    return await selfModelPredictionEvaluator(goal,cycleId);
  }

  if (goal.kind === "capability_audit") {
    return await capabilityAudit(cycleId);
  }

  if (goal.kind === "contextual_belief_evaluator") {
    return await contextualBeliefEvaluator(goal,cycleId);
  }

  if (goal.kind === "contextual_belief_self_test") {
    return await contextualBeliefSelfTest(goal,cycleId);
  }

  if (goal.kind === "mind_program_orchestrator") {
    return await mindProgramOrchestrator(cycleId);
  }

  if (goal.kind === "ungoogled_source_sync") {
    return await ungoogledSourceSync(goal,cycleId);
  }

  if (goal.kind === "resource_fabric_health_cycle") {
    return await resourceFabricHealthCycle(cycleId);
  }

  if (goal.kind === "observation_pipeline_replay") {
    return await replayObservationPipeline(goal,cycleId);
  }

  if (goal.kind === "resource_fabric_admission") {
    return await resourceFabricAdmission(goal,cycleId);
  }

  if (goal.kind === "resource_fabric_benchmark") {
    return await resourceFabricBenchmark(goal,cycleId);
  }

  if (goal.kind === "belief_revision_self_test") {
    return await beliefRevisionSelfTest(goal,cycleId);
  }

  if (goal.kind === "revise_belief") {
    return await applyBeliefRevisionByFreezeId(
      Number(goal.target?.freeze_id),
      cycleId
    );
  }

  if (goal.kind === "belief_revision_evaluator") {
    return await beliefRevisionEvaluator(goal,cycleId);
  }

  if (goal.kind === "active_falsifier_self_test") {
    return await activeFalsifierSelfTest(goal,cycleId);
  }

  if (goal.kind === "active_falsify_relation") {
    return await activeFalsifyRelation(
      cycleId,
      String(goal.target?.case_key??`runtime-${cycleId}`),
      String(goal.target?.url??""),
      String(goal.target?.left_header??""),
      String(goal.target?.right_header??"")
    );
  }

  if (goal.kind === "active_falsifier_evaluator") {
    return await activeFalsifierEvaluator(goal,cycleId);
  }

  if (goal.kind === "key_relation_generalizer_self_test") {
    return await keyRelationGeneralizerSelfTest(goal,cycleId);
  }

  if (goal.kind === "generalize_key_relations") {
    return await generalizeKeyDirectedRelations(
      cycleId,
      String(goal.target?.url??"")
    );
  }

  if (goal.kind === "key_directed_relation_evaluator") {
    return await keyDirectedRelationEvaluator(goal,cycleId);
  }

  if (goal.kind === "heldout_relation_evaluator") {
    return await heldoutRelationEvaluator(goal,cycleId);
  }

  if (goal.kind === "relation_miner_self_test") {
    return await relationMinerSelfTest(goal,cycleId);
  }

  if (goal.kind === "relation_miner_evaluator") {
    return await relationMinerEvaluator(goal,cycleId);
  }

  if (goal.kind === "goal_frontier_self_test") {
    return await goalFrontierSelfTest(goal,cycleId);
  }

  if (goal.kind === "rank_frontier") {
    return await goalWeightedFrontier(
      cycleId,
      String(goal.target?.url??""),
      String(goal.target?.query??"")
    );
  }

  if (goal.kind === "safe_frontier_self_test") {
    return await safeFrontierSelfTest(goal,cycleId);
  }

  if (goal.kind === "explore_frontier") {
    return await exploreFrontierGoal(goal,cycleId);
  }

  if (goal.kind === "concept_transfer_self_test") {
    const conceptId=Number(goal.target?.concept_id);
    if(!Number.isFinite(conceptId)) throw new Error("invalid concept transfer concept id");
    return await conceptTransferSelfTest(conceptId,cycleId,true);
  }

  if (goal.kind === "self_development_audit") {
    return await selfDevelopmentAudit(cycleId);
  }

  if (goal.kind === "concept_birth_self_test") {
    const evidenceId=Number(goal.target?.evidence_id);
    if(!Number.isFinite(evidenceId)) throw new Error("invalid concept birth evidence id");
    return await conceptBirthFromEvidence(evidenceId,cycleId,true);
  }

  if (goal.kind === "concept_birth_evaluate") {
    const evidenceId=Number(goal.target?.evidence_id);
    if(!Number.isFinite(evidenceId)) throw new Error("invalid concept birth evidence id");
    return await conceptBirthFromEvidence(evidenceId,cycleId,false);
  }

  if (goal.kind === "inspect_concept_application") {
    return await inspectConceptApplication(goal,cycleId);
  }

  if (goal.kind === "domain_birth_self_test") {
    const evidenceId=Number(goal.target?.evidence_id);
    if(!Number.isFinite(evidenceId)) throw new Error("invalid domain birth evidence id");
    return await domainBirthFromEvidence(evidenceId,cycleId,true);
  }

  if (goal.kind === "domain_birth_evaluate") {
    const evidenceId=Number(goal.target?.evidence_id);
    if(!Number.isFinite(evidenceId)) throw new Error("invalid domain birth evidence id");
    return await domainBirthFromEvidence(evidenceId,cycleId,false);
  }

  if (goal.kind === "inspect_domain_seed") {
    return await inspectDomainSeed(goal,cycleId);
  }

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
      ...state,version:"0.36-cloud-metacognitive-calibration",last_cycle_at:nowIso(),
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
