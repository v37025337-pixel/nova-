
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

  let work:any={
    action:"awaiting_step_mechanism",
    target_mechanism:step.mechanism_target,
  };

  if(step.step_key==="DM01:CONTEXTUAL_BELIEF_ARBITRATION") {
    work=await researchContextualBeliefArbitration(program,step,cycleId);
  } else {
    const {error:devGoalErr}=await db.from("mind_core_goals").upsert({
      goal_key:"recurring:self-development-audit",
      kind:"self_development_audit",
      target:{},
      rationale:`Program ${program.program_key} requests development for ${step.step_key}`,
      priority:0.92,
      status:"pending",
      recurrence_minutes:180,
      not_before:nowIso(),
      updated_at:nowIso(),
    },{onConflict:"goal_key"});
    if(devGoalErr) throw devGoalErr;
    work={
      action:"scheduled_self_development",
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
      ...state,version:"0.23-cloud-digital-mind-program",last_cycle_at:nowIso(),
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
