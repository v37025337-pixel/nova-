import test from "node:test";
import assert from "node:assert/strict";
import { applyArtifact, artifactHash, contentHash, createGenesisSession, synthesizeRule, validateArtifact } from "../edge/genesis.ts";
import type { RuleArtifact, TrainingExample, Evaluator } from "../edge/genesis.ts";
const initial: TrainingExample[] = [
  { id: "t1", features: { consistency: .2, coverage: .2 }, expected: "reject" },
  { id: "t2", features: { consistency: .8, coverage: .8 }, expected: "accept" },
];
const repair: TrainingExample[] = [...initial,
  { id: "r0", features: { consistency: .6, coverage: .6 }, expected: "accept" },
  { id: "r1", features: { consistency: .8, coverage: .4 }, expected: "reject" },
  { id: "r2", features: { consistency: .4, coverage: .8 }, expected: "reject" },
];
const features = ["consistency", "coverage"];
async function fakeEvaluator(overrides: Partial<Evaluator> = {}): Promise<Evaluator> {
  return {
    trainingInputHashes: await Promise.all(repair.map(r => contentHash(r.features))),
    manifest: [{ suiteId: "s1", suiteHash: "a".repeat(64), totalCount: 2 }, { suiteId: "s2", suiteHash: "b".repeat(64), totalCount: 2 }],
    async evaluate(r) { return { ...r, suiteHash: r.suiteId === "s1" ? "a".repeat(64) : "b".repeat(64), totalCount: 2, passedCount: 0, passed: false }; },
    ...overrides,
  };
}

test("bounded synthesis fits data but shortcut fails independent counterexample", () => {
  const before = JSON.stringify(initial);
  const { artifact } = synthesizeRule(initial, features, 1);
  assert.equal(artifact.conditions.length, 1);
  assert.equal(applyArtifact(artifact, { consistency: .9, coverage: .1 }), "accept");
  assert.equal(JSON.stringify(initial), before);
  const redesigned = synthesizeRule(repair, features, 2).artifact;
  assert.equal(redesigned.conditions.length, 2);
  for (const [consistency, coverage, expected] of [[.9,.1,"reject"],[.1,.9,"reject"],[.9,.9,"accept"],[.1,.1,"reject"]] as const)
    assert.equal(applyArtifact(redesigned, { consistency, coverage }), expected);
});

test("artifact boundaries reject code, nonfinite values, missing features and vacuous rules", () => {
  const rule = synthesizeRule(repair, features).artifact;
  assert.throws(() => validateArtifact({ ...rule, code: "fetch('https://example.com')" }));
  assert.throws(() => validateArtifact({ ...rule, conditions: [] }));
  assert.throws(() => validateArtifact({ ...rule, conditions: [{ feature: "x", op: ">=", threshold: NaN }] }));
  assert.throws(() => applyArtifact(rule, { consistency: 0 }));
  assert.throws(() => applyArtifact(rule, { consistency: 0, coverage: Infinity }));
  assert.throws(() => applyArtifact(rule, { consistency: "1", coverage: 1 }));
  let invoked = false;
  assert.throws(() => validateArtifact({ ...rule, get language() { invoked = true; return "NOVA-RULE-1"; } }));
  assert.equal(invoked, false);
});

test("training contract rejects duplicate, one-class, unsafe and unbounded data", () => {
  assert.throws(() => synthesizeRule([initial[0], { ...initial[0], id: "other" }], features));
  assert.throws(() => synthesizeRule(initial, ["constructor"]));
  assert.throws(() => synthesizeRule(initial, features, 4));
  assert.throws(() => synthesizeRule(repair, features, 1), /no rule fits/);
});

test("hash binds exact rule content and is stable across object key insertion order", async () => {
  const rule = synthesizeRule(repair, features).artifact;
  assert.equal(await artifactHash(rule), await artifactHash({ if_false: rule.if_false, if_true: rule.if_true,
    combine: rule.combine, conditions: rule.conditions, language: rule.language }));
  const changed = structuredClone(rule); changed.conditions[0].threshold += .01;
  assert.notEqual(await artifactHash(rule), await artifactHash(changed));
});

test("session retains immutable reject/redesign lineage and never admits production", async () => {
  const session = createGenesisSession({ deficitKey: "relation_gate", featureNames: features, evaluator: await fakeEvaluator() });
  const first = await session.propose(initial, 1);
  assert.equal(first.baselineAccuracy, .5);
  assert.throws(() => { first.artifact.conditions[0].threshold = -100; });
  assert.equal((await session.evaluate(first.candidateId, "s1")).status, "rejected");
  const second = await session.propose(repair);
  assert.equal(second.parentHash, first.artifactHash);
  assert.equal(session.snapshot().candidates[0].status, "rejected");
  assert.equal(session.snapshot().productionAdmitted, false);
  assert.deepEqual(session.snapshot().events.map(e => e.event), ["DETECT_GAP", "FREEZE", "REJECT", "REDESIGN", "FREEZE"]);
  await assert.rejects(() => session.evaluate(second.candidateId, "s1"), /reused/);
});

test("receipt forgery and exception fail closed without exposing hidden answers", async () => {
  for (const evaluate of [async () => { throw new Error("SECRET expected=accept"); },
    async (r: any) => ({ ...r, suiteHash: "c".repeat(64), totalCount: 2, passedCount: 2, passed: true })]) {
    const session = createGenesisSession({ deficitKey: "gate", featureNames: features, evaluator: await fakeEvaluator({ evaluate }) });
    const first = await session.propose(initial);
    assert.equal((await session.evaluate(first.candidateId, "s1")).status, "rejected");
    assert.equal(JSON.stringify(session.snapshot()).includes("SECRET"), false);
  }
});

test("redesign cannot reuse same artifact, invent training rows, or race another proposal", async () => {
  const session = createGenesisSession({ deficitKey: "gate", featureNames: features, evaluator: await fakeEvaluator() });
  const firstPromise = session.propose(initial);
  await assert.rejects(() => session.propose(initial), /already running/);
  const first = await firstPromise;
  await session.evaluate(first.candidateId, "s1");
  await assert.rejects(() => session.propose(initial), /must change/);
  await assert.rejects(() => session.propose([...initial, { id: "leak", features: { consistency: .9, coverage: .1 }, expected: "reject" }]), /frozen public pool/);
});

test("receipt counts must agree with pass and evaluated request cannot be replayed", async () => {
  const evaluator = await fakeEvaluator({ async evaluate(r) { return { ...r, suiteHash: "a".repeat(64), totalCount: 2, passedCount: 1, passed: true }; } });
  const session = createGenesisSession({ deficitKey: "gate", featureNames: features, evaluator });
  const first = await session.propose(initial);
  const checks = await Promise.allSettled([session.evaluate(first.candidateId, "s1"), session.evaluate(first.candidateId, "s1")]);
  assert.equal(checks.filter(c => c.status === "rejected").length, 1);
  assert.equal(session.snapshot().candidates[0].status, "rejected");
});

test("floating-point midpoint rounding cannot abort a valid bounded conjunction", () => {
  const next = 1 + Number.EPSILON;
  const rows: TrainingExample[] = [
    { id: "a", features: { x: 1, y: 1 }, expected: "accept" },
    { id: "b", features: { x: 1, y: 0 }, expected: "reject" },
    { id: "c", features: { x: next, y: 1 }, expected: "reject" },
    { id: "d", features: { x: next, y: 0 }, expected: "reject" },
  ];
  const rule = synthesizeRule(rows, ["x", "y"], 2).artifact;
  for (const row of rows) assert.equal(applyArtifact(rule, row.features), row.expected);
});
