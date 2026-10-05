import { runMechanismGenesisShadow } from "../edge/genesis_shadow.ts";
const result = await runMechanismGenesisShadow();
console.log(JSON.stringify(result, null, 2));
if (result.candidates.at(-1)?.status !== "shadow_admitted") process.exitCode = 1;
