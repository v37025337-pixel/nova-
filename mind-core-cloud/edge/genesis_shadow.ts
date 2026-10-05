/** Offline integration exercise. Synthetic fixtures are not a production admission. */
import { createGenesisSession } from "./genesis.ts";
import type { TrainingExample } from "./genesis.ts";
import { createHeldoutEvaluator } from "./genesis_evaluator.ts";
import { SHADOW_SUITES } from "./genesis_shadow_suites.ts";

const initial: TrainingExample[] = [
  { id: "public-1", features: { consistency: .2, coverage: .2 }, expected: "reject" },
  { id: "public-2", features: { consistency: .8, coverage: .8 }, expected: "accept" },
];
const redesigned: TrainingExample[] = [...initial,
  { id: "public-3", features: { consistency: .6, coverage: .6 }, expected: "accept" },
  { id: "public-4", features: { consistency: .8, coverage: .4 }, expected: "reject" },
  { id: "public-5", features: { consistency: .4, coverage: .8 }, expected: "reject" },
];

/** The learner receives public batches only. Trusted evaluator owns both fresh suites. */
export async function runMechanismGenesisShadow() {
  const evaluator = await createHeldoutEvaluator(SHADOW_SUITES, redesigned.map(r => r.features));
  const session = createGenesisSession({ deficitKey: "relation_gate", featureNames: ["consistency", "coverage"], evaluator });
  const first = await session.propose(initial, 1);
  const rejected = await session.evaluate(first.candidateId, "relation-v1");
  if (rejected.status !== "rejected") throw new Error("shadow control failed to reject the shortcut");
  const second = await session.propose(redesigned, 2);
  await session.evaluate(second.candidateId, "relation-v2");
  return {
    ...session.snapshot(),
    evidenceClass: "synthetic_local_shadow",
    task: "accept iff consistency >= 0.5 and coverage >= 0.5",
    independentEvaluator: "separate committed suites; no held-out rows supplied to synthesis",
    trainingAcquisition: "predeclared public batches supplied by harness; not autonomous research",
    remainingAdmission: "DM08 remains ACTIVE: three new mechanisms and real runtime independent admission still required",
  };
}
