/** Bounded, offline DM08 shadow kernel. No eval, network, shell, or registry writes. */
export const GENESIS_MECHANISM = "M0020:mechanism-genesis";
export const GENESIS_PROTOCOL = "bounded-rule-genesis-v1";
export type Decision = "accept" | "reject";
export type Condition = { feature: string; op: ">=" | "<="; threshold: number };
export type RuleArtifact = {
  language: "NOVA-RULE-1";
  conditions: readonly Condition[];
  combine: "AND";
  if_true: "accept";
  if_false: "reject";
};
export type TrainingExample = { id: string; features: Record<string, number>; expected: Decision };
export type EvaluationRequest = {
  candidateId: string; artifact: RuleArtifact; artifactHash: string; suiteId: string;
};
export type EvaluationReceipt = {
  candidateId: string; artifactHash: string; suiteId: string; suiteHash: string;
  passed: boolean; passedCount: number; totalCount: number;
};
export type Evaluator = {
  trainingInputHashes: readonly string[];
  manifest: readonly { suiteId: string; suiteHash: string; totalCount: number }[];
  evaluate(request: EvaluationRequest): Promise<EvaluationReceipt>;
};
export type Candidate = {
  candidateId: string; revision: number; parentHash: string | null;
  artifact: RuleArtifact; artifactHash: string; trainingHash: string;
  trainingAccuracy: number; baselineAccuracy: number; searched: number;
  status: "frozen" | "evaluating" | "rejected" | "shadow_admitted";
  receipt?: EvaluationReceipt; reason?: string;
};

const safeName = (s: unknown): s is string => typeof s === "string" &&
  /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(s) && !["constructor", "prototype", "__proto__"].includes(s);
function plain(x: unknown): x is Record<string, unknown> {
  return x !== null && typeof x === "object" && !Array.isArray(x) &&
    [Object.prototype, null].includes(Object.getPrototypeOf(x)) &&
    Reflect.ownKeys(x).every(k => typeof k === "string") &&
    Object.values(Object.getOwnPropertyDescriptors(x)).every(d => "value" in d && d.enumerable);
}
function exactKeys(x: Record<string, unknown>, expected: string[]) {
  return Object.keys(x).sort().join("|") === expected.sort().join("|");
}
export function validateArtifact(value: unknown): asserts value is RuleArtifact {
  if (!plain(value) || !exactKeys(value, ["language", "conditions", "combine", "if_true", "if_false"]) ||
    value.language !== "NOVA-RULE-1" || value.combine !== "AND" ||
    value.if_true !== "accept" || value.if_false !== "reject" ||
    !Array.isArray(value.conditions) || value.conditions.length < 1 || value.conditions.length > 3)
    throw new Error("invalid bounded rule artifact");
  const seen = new Set<string>();
  for (const c of value.conditions) {
    if (!plain(c) || !exactKeys(c, ["feature", "op", "threshold"]) || !safeName(c.feature) ||
      (c.op !== ">=" && c.op !== "<=") || typeof c.threshold !== "number" ||
      !Number.isFinite(c.threshold)) throw new Error("invalid bounded rule condition");
    const key = JSON.stringify([c.feature, c.op, c.threshold]);
    if (seen.has(key)) throw new Error("duplicate rule condition");
    seen.add(key);
  }
}
export function applyArtifact(artifact: unknown, features: unknown): Decision {
  validateArtifact(artifact);
  if (!plain(features) || Object.keys(features).length > 16 ||
    Object.entries(features).some(([k, v]) => !safeName(k) || typeof v !== "number" || !Number.isFinite(v)))
    throw new Error("features must be a bounded finite numeric record");
  // Validate every required input before evaluation; short-circuiting cannot hide missing fields.
  for (const c of artifact.conditions) {
    if (!Object.hasOwn(features, c.feature)) throw new Error("missing required feature");
  }
  return artifact.conditions.every(c => c.op === ">="
    ? (features[c.feature] as number) >= c.threshold
    : (features[c.feature] as number) <= c.threshold) ? "accept" : "reject";
}
export async function contentHash(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, "0")).join("");
}
export async function artifactHash(artifact: RuleArtifact): Promise<string> {
  validateArtifact(artifact);
  return await contentHash({ language: artifact.language, combine: artifact.combine,
    conditions: artifact.conditions.map(c => ({ feature: c.feature, op: c.op, threshold: c.threshold })),
    if_true: artifact.if_true, if_false: artifact.if_false });
}
function copy<T>(value: T): T { return structuredClone(value); }
function freeze<T>(value: T): T {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}
function trainingRows(rows: readonly TrainingExample[], names: readonly string[]) {
  if (!Array.isArray(rows) || rows.length < 2 || rows.length > 32) throw new Error("training row budget exceeded");
  const ids = new Set<string>(), inputs = new Set<string>();
  const ordered = names.slice().sort();
  const result = rows.map(row => {
    if (!plain(row) || !exactKeys(row, ["id", "features", "expected"]) ||
      typeof row.id !== "string" || !row.id || row.id.length > 128 || ids.has(row.id) ||
      !["accept", "reject"].includes(row.expected) || !plain(row.features) ||
      Object.keys(row.features).sort().join("|") !== ordered.join("|")) throw new Error("invalid training example");
    ids.add(row.id);
    const features: Record<string, number> = {};
    for (const name of ordered) {
      const v = row.features[name];
      if (typeof v !== "number" || !Number.isFinite(v) || Math.abs(v) > 1e6)
        throw new Error("training feature outside finite search bounds");
      features[name] = v;
    }
    const key = JSON.stringify(features);
    if (inputs.has(key)) throw new Error("duplicate or contradictory training input");
    inputs.add(key);
    return { id: row.id, features, expected: row.expected };
  });
  if (new Set(result.map(x => x.expected)).size !== 2) throw new Error("training requires both decision classes");
  return result;
}

/** Enumerates conjunctions over training-derived thresholds only; no evaluator access. */
export function synthesizeRule(rows: readonly TrainingExample[], featureNames: readonly string[], maxConditions = 2) {
  if (!Array.isArray(featureNames) || featureNames.length < 1 || featureNames.length > 6 ||
    featureNames.some(n => !safeName(n)) || new Set(featureNames).size !== featureNames.length ||
    !Number.isInteger(maxConditions) || maxConditions < 1 || maxConditions > 3)
    throw new Error("invalid synthesis bounds");
  const train = trainingRows(rows, featureNames);
  const atoms: Condition[] = [];
  for (const feature of featureNames.slice().sort()) {
    const values = [...new Set(train.map(r => r.features[feature]))].sort((a, b) => a - b);
    const midpoints = values.slice(1).map((v, i) => values[i] + (v - values[i]) / 2);
    // Prefer a separating midpoint to memorizing a training endpoint.
    // Adjacent floats can round a midpoint to an endpoint: never enumerate duplicate atoms.
    for (const threshold of new Set([...midpoints, ...values]))
      for (const op of [">=", "<="] as const) atoms.push({ feature, op, threshold });
  }
  let searched = 0, found: RuleArtifact | null = null;
  function search(start: number, conditions: Condition[], size: number) {
    if (found) return;
    if (conditions.length === size) {
      if (++searched > 50_000) throw new Error("synthesis search budget exhausted");
      const artifact: RuleArtifact = { language: "NOVA-RULE-1", conditions: copy(conditions),
        combine: "AND", if_true: "accept", if_false: "reject" };
      if (train.every(row => applyArtifact(artifact, row.features) === row.expected)) found = artifact;
      return;
    }
    for (let i = start; i < atoms.length && !found; i++) search(i + 1, [...conditions, atoms[i]], size);
  }
  for (let size = 1; size <= maxConditions && !found; size++) search(0, [], size);
  if (!found) throw new Error("no rule fits training within the bounded grammar");
  return { artifact: freeze(found as RuleArtifact), searched, training: train };
}

/** Receipts are accepted only from the caller's trusted evaluator capability, never a goal payload. */
export function createGenesisSession(options: {
  deficitKey: string; featureNames: readonly string[]; evaluator: Evaluator; maxAttempts?: number;
  incumbent?: RuleArtifact;
}) {
  if (!safeName(options.deficitKey)) throw new Error("invalid deficit key");
  const maxAttempts = options.maxAttempts ?? 3;
  if (!Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 3) throw new Error("invalid attempt budget");
  const deficitKey = options.deficitKey;
  const trainingInputHashes = new Set(options.evaluator.trainingInputHashes);
  if (!trainingInputHashes.size || [...trainingInputHashes].some(h => !/^[a-f0-9]{64}$/.test(h)))
    throw new Error("invalid public training pool commitment");
  const names = copy(options.featureNames), incumbent = options.incumbent && copy(options.incumbent);
  if (incumbent) validateArtifact(incumbent);
  const manifest = copy(options.evaluator.manifest);
  if (!manifest.length || manifest.some(m => !m.suiteId || !/^[a-f0-9]{64}$/.test(m.suiteHash) ||
    !Number.isInteger(m.totalCount) || m.totalCount < 1) || new Set(manifest.map(m => m.suiteId)).size !== manifest.length)
    throw new Error("invalid independent evaluator manifest");
  const evaluate = options.evaluator.evaluate.bind(options.evaluator);
  const candidates: Candidate[] = [], events: { event: string; candidateId: string }[] = [];
  const usedSuites = new Set<string>();
  let proposing = false;
  return Object.freeze({
    async propose(rows: readonly TrainingExample[], maxConditions = 2): Promise<Candidate> {
      if (proposing) throw new Error("candidate proposal already running");
      proposing = true;
      try {
        const last = candidates.at(-1);
        if (last && last.status !== "rejected") throw new Error("redesign requires a rejected parent");
        if (candidates.length >= maxAttempts) throw new Error("attempt budget exhausted");
        const publicRows = copy(rows);
        for (const row of publicRows) {
          if (!plain(row.features)) throw new Error("invalid training features");
          const canonical = Object.fromEntries(Object.keys(row.features).sort().map(k => [k, row.features[k]]));
          if (!trainingInputHashes.has(await contentHash(canonical)))
            throw new Error("training input outside the frozen public pool");
        }
        const result = synthesizeRule(publicRows, names, maxConditions);
        const correct = result.training.filter(r => (incumbent ? applyArtifact(incumbent, r.features) : "reject") === r.expected).length;
        const baselineAccuracy = correct / result.training.length;
        if (baselineAccuracy === 1) throw new Error("no measured training deficit");
        const hash = await artifactHash(result.artifact);
        if (candidates.some(c => c.artifactHash === hash)) throw new Error("redesign must change the artifact");
        const trainingHash = await contentHash(result.training);
        const candidate: Candidate = { candidateId: `${deficitKey}:r${candidates.length + 1}:${hash}`,
          revision: candidates.length + 1, parentHash: last?.artifactHash ?? null,
          artifact: result.artifact, artifactHash: hash, trainingHash, trainingAccuracy: 1,
          baselineAccuracy, searched: result.searched, status: "frozen" };
        candidates.push(candidate);
        events.push({ event: last ? "REDESIGN" : "DETECT_GAP", candidateId: candidate.candidateId });
        events.push({ event: "FREEZE", candidateId: candidate.candidateId });
        return freeze(copy(candidate));
      } finally { proposing = false; }
    },
    async evaluate(candidateId: string, suiteId: string): Promise<Candidate> {
      const candidate = candidates.find(c => c.candidateId === candidateId);
      const suite = manifest.find(m => m.suiteId === suiteId);
      if (!candidate || candidate.status !== "frozen" || !suite || usedSuites.has(suiteId))
        throw new Error("invalid or reused evaluation request");
      usedSuites.add(suiteId); candidate.status = "evaluating";
      try {
        const receipt = await evaluate(freeze({ candidateId, suiteId,
          artifact: copy(candidate.artifact), artifactHash: candidate.artifactHash }));
        if (!receipt || receipt.candidateId !== candidateId || receipt.artifactHash !== candidate.artifactHash ||
          receipt.suiteId !== suiteId || receipt.suiteHash !== suite.suiteHash ||
          receipt.totalCount !== suite.totalCount || !Number.isInteger(receipt.passedCount) ||
          receipt.passedCount < 0 || receipt.passedCount > receipt.totalCount ||
          typeof receipt.passed !== "boolean" || receipt.passed !== (receipt.passedCount === receipt.totalCount))
          throw new Error("invalid independent evaluation receipt");
        candidate.receipt = { candidateId, artifactHash: receipt.artifactHash, suiteId,
          suiteHash: receipt.suiteHash, passed: receipt.passed, passedCount: receipt.passedCount, totalCount: receipt.totalCount };
        candidate.status = receipt.passed ? "shadow_admitted" : "rejected";
        candidate.reason = receipt.passed ? "all fresh held-out cases passed; production admission still required" : "held-out rejection";
      } catch {
        candidate.status = "rejected";
        // An evaluator exception may contain hidden data. Do not expose it to the learner.
        candidate.reason = "independent evaluation unavailable or invalid";
      }
      events.push({ event: candidate.status === "shadow_admitted" ? "ADMIT_SHADOW" : "REJECT", candidateId });
      return freeze(copy(candidate));
    },
    snapshot() {
      return freeze(copy({ protocol: GENESIS_PROTOCOL, mechanism: GENESIS_MECHANISM,
        productionAdmitted: false, candidates, events }));
    },
  });
}
