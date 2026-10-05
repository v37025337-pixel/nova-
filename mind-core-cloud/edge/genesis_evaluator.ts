/**
 * Trusted, in-process admission boundary for NOVA-RULE-1 artifacts.
 *
 * The evaluator owner supplies independently authored, private cases. A candidate
 * receives only a frozen manifest and a single aggregate verdict per suite. This
 * module does not establish process isolation or authenticate the evaluator owner.
 */
import { applyArtifact, artifactHash, type RuleArtifact } from "./genesis.ts";

export type HeldoutCase = {
  readonly id: string;
  readonly features: Readonly<Record<string, number>>;
  readonly expected: "accept" | "reject";
};

export type HeldoutSuite = {
  readonly suiteId: string;
  readonly cases: readonly HeldoutCase[];
};

export type SuiteManifest = {
  readonly suiteId: string;
  readonly suiteHash: string;
  readonly totalCount: number;
};

export type EvaluationRequest = {
  readonly candidateId: string;
  readonly artifact: RuleArtifact;
  readonly artifactHash: string;
  readonly suiteId: string;
};

export type EvaluationVerdict = SuiteManifest & {
  readonly candidateId: string;
  readonly artifactHash: string;
  readonly passed: boolean;
  readonly passedCount: number;
};

export type HeldoutEvaluator = {
  readonly manifest: readonly SuiteManifest[];
  /** Commitments to the complete public training pool, fixed before admission. */
  readonly trainingInputHashes: readonly string[];
  readonly evaluate: (request: EvaluationRequest) => Promise<EvaluationVerdict>;
};

// Error strings deliberately contain no hidden case IDs, feature values, labels,
// or candidate-provided strings. Do not forward interpreter errors to candidates.
function invalidConfiguration(): never {
  throw new Error("Invalid held-out evaluator configuration");
}

function invalidRequest(): never {
  throw new Error("Invalid held-out evaluation request");
}

type Fail = () => never;

/** Admit inert JSON records only, without invoking accessors during validation. */
function record(value: unknown, fail: Fail): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) fail();
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) fail();
  const descriptors = Object.getOwnPropertyDescriptors(value);
  if (Reflect.ownKeys(value).some((key) => typeof key !== "string")) fail();
  for (const descriptor of Object.values(descriptors)) {
    if (!("value" in descriptor) || !descriptor.enumerable) fail();
  }
  return value as Record<string, unknown>;
}

function keys(value: Record<string, unknown>, expected: readonly string[], fail: Fail): void {
  const actual = Object.keys(value);
  if (actual.length !== expected.length || expected.some((key) => !Object.hasOwn(value, key))) fail();
}

/** A dense data-only array prevents sparse cases from silently skipping checks. */
function array(value: unknown, fail: Fail): readonly unknown[] {
  if (!Array.isArray(value)) fail();
  const descriptors = Object.getOwnPropertyDescriptors(value);
  const ownKeys = Reflect.ownKeys(value);
  if (ownKeys.length !== value.length + 1) fail();
  for (let index = 0; index < value.length; index += 1) {
    const descriptor = descriptors[String(index)];
    if (!descriptor || !("value" in descriptor) || !descriptor.enumerable) fail();
  }
  return value;
}

function identifier(value: unknown, fail: Fail): string {
  if (typeof value !== "string" || value.length === 0 || value.trim() !== value) fail();
  return value;
}

function featureName(value: unknown, fail: Fail): string {
  if (typeof value !== "string" || !/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(value) ||
      ["constructor", "prototype", "__proto__"].includes(value)) fail();
  return value;
}

function featureSnapshot(value: unknown, fail: Fail): Readonly<Record<string, number>> {
  const input = record(value, fail);
  const result: Record<string, number> = Object.create(null);
  const names = Object.keys(input).sort();
  if (names.length === 0 || names.length > 16) fail();
  for (const name of names) {
    featureName(name, fail);
    const number = input[name];
    if (typeof number !== "number" || !Number.isFinite(number)) fail();
    // Normalizing signed zero matches the interpreter's numeric comparisons.
    result[name] = Object.is(number, -0) ? 0 : number;
  }
  return Object.freeze(result);
}

function artifactSnapshot(value: unknown): RuleArtifact {
  const input = record(value, invalidRequest);
  keys(input, ["language", "conditions", "combine", "if_true", "if_false"], invalidRequest);
  if (input.language !== "NOVA-RULE-1" || input.combine !== "AND" ||
      input.if_true !== "accept" || input.if_false !== "reject") invalidRequest();
  const inputConditions = array(input.conditions, invalidRequest);
  if (inputConditions.length === 0 || inputConditions.length > 3) invalidRequest();
  const seen = new Set<string>();
  const conditions = inputConditions.map((value) => {
    const condition = record(value, invalidRequest);
    keys(condition, ["feature", "op", "threshold"], invalidRequest);
    const feature = featureName(condition.feature, invalidRequest);
    if (condition.op !== ">=" && condition.op !== "<=") invalidRequest();
    if (typeof condition.threshold !== "number" || !Number.isFinite(condition.threshold)) invalidRequest();
    const fingerprint = JSON.stringify([feature, condition.op, condition.threshold]);
    if (seen.has(fingerprint)) invalidRequest();
    seen.add(fingerprint);
    return Object.freeze({ feature, op: condition.op, threshold: condition.threshold });
  });
  return Object.freeze({
    language: "NOVA-RULE-1", conditions: Object.freeze(conditions),
    combine: "AND", if_true: "accept", if_false: "reject",
  });
}

async function sha256(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/**
 * Snapshot and validate ALL trusted inputs before the first asynchronous step.
 * Identical numeric feature rows cannot cross the training/admission boundary,
 * even if their IDs or property insertion order differ.
 */
export async function createHeldoutEvaluator(
  suites: readonly HeldoutSuite[],
  publicTrainingRows: readonly Readonly<Record<string, number>>[],
): Promise<HeldoutEvaluator> {
  const trainingSnapshots = array(publicTrainingRows, invalidConfiguration)
    .map((row) => featureSnapshot(row, invalidConfiguration));
  const trainingFingerprints = new Set(trainingSnapshots.map((row) => JSON.stringify(row)));
  const suiteIds = new Set<string>();
  const caseIds = new Set<string>();
  const heldoutFingerprints = new Set<string>();
  const inputs = array(suites, invalidConfiguration);
  if (inputs.length === 0) invalidConfiguration();
  const snapshots = inputs.map((value) => {
    const suite = record(value, invalidConfiguration);
    keys(suite, ["suiteId", "cases"], invalidConfiguration);
    const suiteId = identifier(suite.suiteId, invalidConfiguration);
    if (suiteIds.has(suiteId)) invalidConfiguration();
    suiteIds.add(suiteId);
    const inputCases = array(suite.cases, invalidConfiguration);
    if (inputCases.length === 0) invalidConfiguration();
    const cases = inputCases.map((value) => {
      const test = record(value, invalidConfiguration);
      keys(test, ["id", "features", "expected"], invalidConfiguration);
      const id = identifier(test.id, invalidConfiguration);
      if (caseIds.has(id)) invalidConfiguration();
      caseIds.add(id);
      if (test.expected !== "accept" && test.expected !== "reject") invalidConfiguration();
      const features = featureSnapshot(test.features, invalidConfiguration);
      const fingerprint = JSON.stringify(features);
      if (trainingFingerprints.has(fingerprint) || heldoutFingerprints.has(fingerprint)) invalidConfiguration();
      heldoutFingerprints.add(fingerprint);
      return Object.freeze({ id, features, expected: test.expected });
    });
    return Object.freeze({ suiteId, cases: Object.freeze(cases) });
  });

  const manifests = await Promise.all(snapshots.map(async (suite) => Object.freeze({
    suiteId: suite.suiteId,
    suiteHash: await sha256({ format: "NOVA-HELDOUT-1", ...suite }),
    totalCount: suite.cases.length,
  })));
  const manifest = Object.freeze(manifests);
  const trainingInputHashes = Object.freeze([...new Set(await Promise.all(trainingSnapshots.map(sha256)))].sort());
  const privateSuites = new Map(snapshots.map((suite, index) => [suite.suiteId, {
    cases: suite.cases, manifest: manifest[index], used: false,
  }]));

  async function evaluate(request: EvaluationRequest): Promise<EvaluationVerdict> {
    // Resolve the named suite without invoking user-supplied getters. Reserve it
    // before any await, including before artifact validation or hash comparison.
    const input = record(request, invalidRequest);
    const suiteId = identifier(input.suiteId, invalidRequest);
    const suite = privateSuites.get(suiteId);
    if (!suite || suite.used) throw new Error("Held-out suite is unavailable");
    suite.used = true;
    try {
      keys(input, ["candidateId", "artifact", "artifactHash", "suiteId"], invalidRequest);
      const candidateId = identifier(input.candidateId, invalidRequest);
      const requestedHash = input.artifactHash;
      if (typeof requestedHash !== "string" || !/^[a-f0-9]{64}$/.test(requestedHash)) invalidRequest();
      const artifact = artifactSnapshot(input.artifact);
      const actualHash = await artifactHash(artifact);
      if (actualHash !== requestedHash) invalidRequest();
      let passedCount = 0;
      for (const test of suite.cases) {
        const actual = applyArtifact(artifact, test.features);
        if (actual !== "accept" && actual !== "reject") invalidRequest();
        if (actual === test.expected) passedCount += 1;
      }
      return Object.freeze({
        candidateId, artifactHash: actualHash, ...suite.manifest,
        passed: passedCount === suite.cases.length, passedCount,
      });
    } catch {
      // Neither an interpreter exception nor malformed private data can expose
      // hidden information or yield a partially successful admission result.
      invalidRequest();
    }
  }

  return Object.freeze({ manifest, trainingInputHashes, evaluate });
}
