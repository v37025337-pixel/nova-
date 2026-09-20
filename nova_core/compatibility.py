"""Explicit v0.1 compatibility contract; no arbitrary source-pin bypass."""

import sys

from .contracts import encode

# Exact release c233ff5c984dba5a411b484d8f401bcc4c11392f, also used by G8.
V1_SOURCES = {
    "__init__.py": "987d369b712971bb85be2a6f8c365486b18b284b41f52efaff3ed651514613a1",
    "__main__.py": "8ff1419e8c37c34b1338a17c3f1ab7e693045c54963fdd7647ddc4e1b9eebc1b",
    "contracts.py": "54068e5bd79c3a896fb904aae0d5ff5544e1a7c921b7774da36d9c73f05212fe",
    "evaluation.py": "06ca272237362407ea65a559ae222acf41a99fceb574b3f945e34e8726279cf2",
    "genetics.py": "f492111a5c3bd501d82cf2f3de15619cc98d2df680c9ba9b5624bd91dd02ee7a",
    "kernel.py": "d1ee42c7f3e8c78013e708dede6d9471261c2be7bbe5540b914bf47cb261a1a6",
    "language.py": "1368b722cb49acee05dc422b5fd8adff9de4fb9fdb2aeb2e7990d87e344f7487",
    "memory.py": "3e8397ac08f8e303e313cac519498d49f010045975453508ab14decd8047a777",
    "synthesis.py": "50a2bff3701aaa48bd06d316114583a20c0775939ca0dfda5aca321b94b81feb"}


def legacy_manifest():
    return {"schema": "nova.kernel.v1", "python": list(sys.version_info[:2]), "sources": dict(V1_SOURCES),
            "search": {"attempts": 12000, "depth": 3}, "runtime": "single_state_single_queue_single_journal",
            "faculties": {"CODE": "native_expression_synthesis_and_ast_execution",
                          "LOGIC": "contracts_deficits_and_admission_evidence",
                          "THINKING": "causal_goal_selection_and_continuation",
                          "INTELLIGENCE": "experience_conditioned_verified_gene_selection"},
            "program_author": "kernel_training_only", "engine_author": "maintainer"}


def recognized_legacy(manifest):
    return any(encode(manifest) == encode(m) for m in (legacy_manifest(), v2_manifest()))


# Exact 0.2.0 release (872d8cda); G12 embeds this manifest after the v1 upgrade.
V2_SOURCES = {
    "__init__.py": "b0c750095a311217132e95b6f6f494a6050ea879ec1b674ee6d8bfda853b3214",
    "__main__.py": "4298caa0bbb8ff5dc3393eca97e38a42bb104360da27d86d686caab16ed21e0a",
    "adaptation.py": "50a64f921a3b7c65da6529142a440ec1ea3029faef5b5a28db5c776955fc8e99",
    "compatibility.py": "fabd482115df5ae2a19188e695e3b80e9df2e1516bae68fe442764df02e2a89a",
    "contracts.py": V1_SOURCES["contracts.py"],
    "evaluation.py": V1_SOURCES["evaluation.py"],
    "genetics.py": "bb96c69030adcffd7ea4642918c3a18e091a1860dfb6021d13d5d98073016d0a",
    "kernel.py": "56d84a0290d95a230c4c5a02489521870057669fc4c10d1857c5d8eb423742e6",
    "language.py": V1_SOURCES["language.py"],
    "memory.py": V1_SOURCES["memory.py"],
    "synthesis.py": "a7e36bc9ca027d126578668bfc9bb6997c7542ce6e4426baec5ae6e92f1a533c"}


def v2_manifest():
    return {**legacy_manifest(), "schema": "nova.kernel.v2", "sources": dict(V2_SOURCES),
            "engine_policy_author": "kernel_bounded_experience_conditioned_mutation"}
