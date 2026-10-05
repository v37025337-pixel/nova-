import test from "node:test";
import assert from "node:assert/strict";
import { runMechanismGenesisShadow } from "../edge/genesis_shadow.ts";
import { artifactHash, applyArtifact } from "../edge/genesis.ts";

test("real synthesizer and held-out evaluator close reject -> redesign -> shadow admission", async () => {
  const run = await runMechanismGenesisShadow();
  assert.equal(run.productionAdmitted, false);
  assert.equal(run.evidenceClass, "synthetic_local_shadow");
  assert.deepEqual(run.events.map(e => e.event), ["DETECT_GAP", "FREEZE", "REJECT", "REDESIGN", "FREEZE", "ADMIT_SHADOW"]);
  const [first, second] = run.candidates;
  assert.equal(first.status, "rejected");
  assert.equal(second.status, "shadow_admitted");
  assert.equal(first.trainingAccuracy, 1);
  assert.equal(second.trainingAccuracy, 1);
  assert.ok(first.receipt!.passedCount < first.receipt!.totalCount);
  assert.equal(second.receipt!.passedCount, second.receipt!.totalCount);
  assert.notEqual(first.receipt!.suiteHash, second.receipt!.suiteHash);
  assert.notEqual(first.trainingHash, second.trainingHash);
  assert.equal(second.parentHash, first.artifactHash);
  assert.equal(second.artifactHash, await artifactHash(second.artifact));
  assert.equal(second.artifact.conditions.length, 2);
  assert.equal(JSON.stringify(run).includes('"expected"'), false);
});

test("admitted shadow artifact generalizes on additional fresh grid with independent specification", async () => {
  const run = await runMechanismGenesisShadow();
  const rule = run.candidates.at(-1)!.artifact;
  // Expected values come from the specification, not candidate conditions or evaluator fixtures.
  for (const consistency of [-1, 0, .13, .49, .5, .5001, .73, 1, 2])
    for (const coverage of [-1, 0, .23, .49, .5, .5001, .83, 1, 2])
      assert.equal(applyArtifact(rule, { consistency, coverage }),
        consistency >= .5 && coverage >= .5 ? "accept" : "reject");
});

test("offline replay is deterministic and each run gets fresh isolated evaluator state", async () => {
  assert.deepEqual(await runMechanismGenesisShadow(), await runMechanismGenesisShadow());
});
