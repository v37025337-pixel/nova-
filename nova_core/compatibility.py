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
    return encode(manifest) == encode(legacy_manifest())
