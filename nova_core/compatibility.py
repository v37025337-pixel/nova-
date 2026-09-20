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
    return any(encode(manifest) == encode(m) for m in (legacy_manifest(), v2_manifest(), v3_manifest(), v4_manifest(), v5_manifest()))


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


# Exact 0.3.0 release (473ed1d4), including its generated-gene journals.
V3_SOURCES = {'__init__.py': '8838a49211c4f67d00c1991641e90a398fe73e987b4d9344c70d4be3c24a8f65',
 '__main__.py': 'b5f9eebcbbfa9021a02046975e7ba1e66e071430630d4ed2b877257267c8707d',
 'adaptation.py': 'd3ae9a32d3114e0fd9d1e09af66d95fcb0a0c58cf1d14b5ec8619c45643bcaae',
 'capability.py': '958b67d38066e99c6724b0fab8bfd81dbf977ea2f38bef1bc7b9a158c27963e5',
 'compatibility.py': '8bf37d4842d4e3a44eb25198c0b1514551301550f85a5b403f7ad4ab04b2168c',
 'contracts.py': '54068e5bd79c3a896fb904aae0d5ff5544e1a7c921b7774da36d9c73f05212fe',
 'evaluation.py': '06ca272237362407ea65a559ae222acf41a99fceb574b3f945e34e8726279cf2',
 'extensions.py': '10b1d37e6d6c29c46115e57e00dba433408414716dea141287afdd4af892ce0b',
 'genetics.py': 'e3711266beea5cf000107fd839c3d804b946f8eefba0fef69e6fc6af5e0365a0',
 'isolation.py': 'c42b8a1a390f3c667a6a925b3118e882218664da234ca22c7886a4fd732fe3e3',
 'kernel.py': '1b48f47a4379b7eebd6f1b8e5f3afea11ebf9b1e8e7aee0ddc2c8b2ae547ca83',
 'language.py': '1f9d77224b5e14ac35f06d92e6417211cd6aa8f1de544d2d8a9b1a5ab5e1237b',
 'memory.py': '3e8397ac08f8e303e313cac519498d49f010045975453508ab14decd8047a777',
 'sandbox_worker.py': '11482d41f951d639396b2a1e1412e2cb2f2afbab538db243a2f5e9889af59e96',
 'synthesis.py': 'dc21ae933680c1440aec1c232fb973e93c23933b4206c9e727bacd3de3a15379'}


def v3_manifest():
    return {**v2_manifest(), "schema": "nova.kernel.v3", "sources": dict(V3_SOURCES),
            "capability_author": "kernel_specification_conditioned_equation_compiler",
            "capability_dialect": "bounded_word_equations_not_arbitrary_algorithm_prose"}


# Exact runtime 0.4 used by G14 and G20; source pins are not relaxed.
V4_MANIFEST = {'capability_author': 'kernel_specification_conditioned_document_compiler',
 'capability_dialect': 'bounded_word_equations_and_typeset_block_recurrences',
 'engine_author': 'maintainer',
 'engine_policy_author': 'kernel_bounded_experience_conditioned_mutation',
 'faculties': {'CODE': 'native_expression_synthesis_and_ast_execution',
               'INTELLIGENCE': 'experience_conditioned_verified_gene_selection',
               'LOGIC': 'contracts_deficits_and_admission_evidence',
               'THINKING': 'causal_goal_selection_and_continuation'},
 'program_author': 'kernel_training_only',
 'python': [3, 12],
 'runtime': 'single_state_single_queue_single_journal',
 'schema': 'nova.kernel.v4',
 'search': {'attempts': 12000, 'depth': 3},
 'sources': {'__init__.py': '8ae5a78e10c88e838e9958ec0c9fb54aab14dbdeaefb92cced12b70eabe0fa2e',
             '__main__.py': 'b5f9eebcbbfa9021a02046975e7ba1e66e071430630d4ed2b877257267c8707d',
             'adaptation.py': '8da801804b347568ee64ca9549c0bd6708a90a2f8b7a39f8f11bdc0edfd5c796',
             'capability.py': '2a3bfbf8444e988a5fb1713a4ac59b3915ebb36f55c9e676b15e0b97e733f7ad',
             'compatibility.py': '1ac090eb3ec20a521614459b26e556a6dad29f587c2430cf84e58c4272947596',
             'contracts.py': '54068e5bd79c3a896fb904aae0d5ff5544e1a7c921b7774da36d9c73f05212fe',
             'evaluation.py': '06ca272237362407ea65a559ae222acf41a99fceb574b3f945e34e8726279cf2',
             'extensions.py': '181a8cdc13dce717d25cc345c92036a9a8fe14b9a436dfed954e79435f8d574b',
             'genetics.py': 'e3711266beea5cf000107fd839c3d804b946f8eefba0fef69e6fc6af5e0365a0',
             'isolation.py': 'c42b8a1a390f3c667a6a925b3118e882218664da234ca22c7886a4fd732fe3e3',
             'kernel.py': '2dd6757aa4cae810ae818a4e6b10ee41c33e41c685b8a6bb7a5a6440d5b0b3b5',
             'language.py': '3b955d15dde177d50644593eaf2365f8a15e4b09c43bc44c0790d4025b33c781',
             'memory.py': '3e8397ac08f8e303e313cac519498d49f010045975453508ab14decd8047a777',
             'sandbox_worker.py': '11482d41f951d639396b2a1e1412e2cb2f2afbab538db243a2f5e9889af59e96',
             'sequence.py': 'cd1ac5a145caeb9a4fa9c181aeb3bbbd021e4a59b37bbee5d2440b27081f06d2',
             'specifications.py': '3c34a078b8500dc1f9a13ea140c85fe9df7d4294986470989aafe128841b45c3',
             'synthesis.py': '6a61f72491c514ec8706ff52913c679a0cee126189bc4cf3b692cf6a0a5016f7'}}

def v4_manifest():
    from copy import deepcopy
    manifest = deepcopy(V4_MANIFEST)
    manifest["python"] = list(sys.version_info[:2])
    return manifest


# Exact 0.5.1 main runtime, including the retained failed autonomous search.
V5_MANIFEST = {'autonomy': 'bounded_failure_conditioned_relational_subgoals_with_external_io',
 'capability_author': 'kernel_specification_conditioned_document_compiler',
 'capability_dialect': 'bounded_word_equations_and_typeset_block_recurrences',
 'engine_author': 'maintainer',
 'engine_policy_author': 'kernel_bounded_experience_conditioned_mutation',
 'faculties': {'CODE': 'native_expression_synthesis_and_ast_execution',
               'INTELLIGENCE': 'experience_conditioned_verified_gene_selection',
               'LOGIC': 'contracts_deficits_and_admission_evidence',
               'THINKING': 'causal_goal_selection_and_continuation'},
 'program_author': 'kernel_training_only',
 'python': [3, 12],
 'runtime': 'single_state_single_queue_single_journal',
 'schema': 'nova.kernel.v5',
 'search': {'attempts': 12000, 'depth': 3},
 'sources': {'__init__.py': '51e9c1497229a4ddb22578321681397bf4940044ec7f1febc80fd06290218572',
             '__main__.py': '552e86184da846843b150a3d48628cd1026ea9990c863111dd6570d8560c86cb',
             'adaptation.py': '8da801804b347568ee64ca9549c0bd6708a90a2f8b7a39f8f11bdc0edfd5c796',
             'autonomy.py': '55031be1f2f5f87920f19635c39e6aa1e2af8087b6bff5f3d41e7976d7db4c54',
             'capability.py': '462414002f61dea8eb38a48029fae283f023bc4a0f92fad76c07ca5467304d21',
             'compatibility.py': 'fd3affe8f7207abebafa7a35c9bbc8df7b51eef1cba6df0984595ec9f42cc1b7',
             'contracts.py': '54068e5bd79c3a896fb904aae0d5ff5544e1a7c921b7774da36d9c73f05212fe',
             'evaluation.py': '06ca272237362407ea65a559ae222acf41a99fceb574b3f945e34e8726279cf2',
             'extensions.py': '181a8cdc13dce717d25cc345c92036a9a8fe14b9a436dfed954e79435f8d574b',
             'genetics.py': 'e3711266beea5cf000107fd839c3d804b946f8eefba0fef69e6fc6af5e0365a0',
             'isolation.py': 'c42b8a1a390f3c667a6a925b3118e882218664da234ca22c7886a4fd732fe3e3',
             'kernel.py': '9df0546b3901ff515de95be8cf5ff4b16866837daeb91847dfb7e988a73e3da4',
             'language.py': '3b955d15dde177d50644593eaf2365f8a15e4b09c43bc44c0790d4025b33c781',
             'memory.py': '3e8397ac08f8e303e313cac519498d49f010045975453508ab14decd8047a777',
             'sandbox_worker.py': '11482d41f951d639396b2a1e1412e2cb2f2afbab538db243a2f5e9889af59e96',
             'sequence.py': 'cd1ac5a145caeb9a4fa9c181aeb3bbbd021e4a59b37bbee5d2440b27081f06d2',
             'specifications.py': '3c34a078b8500dc1f9a13ea140c85fe9df7d4294986470989aafe128841b45c3',
             'synthesis.py': '7e61fe88d70eaf5485a82be3b98aba1e00dd2384847d635b80b04f8dbe014e19'}}

def v5_manifest():
    from copy import deepcopy
    manifest = deepcopy(V5_MANIFEST)
    manifest["python"] = list(sys.version_info[:2])
    return manifest
