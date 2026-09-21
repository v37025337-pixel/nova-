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
    return any(encode(manifest) == encode(m) for m in (legacy_manifest(), v2_manifest(), v3_manifest(), v4_manifest(), v5_manifest(), v6_manifest(), v7_manifest(), v8_manifest()))


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


# Exact 0.6.0 runtime at main 7218a570; preserves all G22 decisions.
V6_MANIFEST = {'autonomy': 'bounded_failure_conditioned_relational_subgoals_with_external_io',
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
 'python_tools': 'pure_stdlib_composition_and_inherited_relation_transfer',
 'runtime': 'single_state_single_queue_single_journal',
 'schema': 'nova.kernel.v6',
 'search': {'attempts': 12000, 'depth': 3},
 'sources': {'__init__.py': '670a5872dcbc0058f7ea7318801f2300caec127c44cb6c4eff3be1a132c0180b',
             '__main__.py': '552e86184da846843b150a3d48628cd1026ea9990c863111dd6570d8560c86cb',
             'adaptation.py': '8da801804b347568ee64ca9549c0bd6708a90a2f8b7a39f8f11bdc0edfd5c796',
             'autonomy.py': '404737b667260a8c809b9a2e36413b7c05539012bea31528825a849dcd59a751',
             'capability.py': '367bc9041c83f57fc66bbe7b0f8c3cff50667aebedc9d70cb067a0eb42d170ce',
             'compatibility.py': 'd506270aaaaa98288b3da5a4978cf65061c2c60920288429ac33237548b12a1e',
             'contracts.py': '54068e5bd79c3a896fb904aae0d5ff5544e1a7c921b7774da36d9c73f05212fe',
             'evaluation.py': '06ca272237362407ea65a559ae222acf41a99fceb574b3f945e34e8726279cf2',
             'extensions.py': '7b048dda1d3efcc510be6af1162ecd52fb7dddfa53ff01b106a003a74cf6ded2',
             'genetics.py': 'e3711266beea5cf000107fd839c3d804b946f8eefba0fef69e6fc6af5e0365a0',
             'isolation.py': 'c42b8a1a390f3c667a6a925b3118e882218664da234ca22c7886a4fd732fe3e3',
             'kernel.py': '7bbe393a5370fd35e7df971f5154efb32d2a1b8446463937c4eb8c8963770466',
             'language.py': 'a541480da7093aaa401f82e1bf3aa7be5f4914ca57ac3222db0e7084af60e1a7',
             'library_evolution.py': '7328f2245389bfd7120ec2dbf70a0800a1397fefcadca4f254acb8e14370700a',
             'memory.py': '3e8397ac08f8e303e313cac519498d49f010045975453508ab14decd8047a777',
             'python_tools.py': '6e4ddb19f4897b470b0e94c547c7947a0925308af98af4f9178ae6dd2047a2eb',
             'sandbox_worker.py': '11482d41f951d639396b2a1e1412e2cb2f2afbab538db243a2f5e9889af59e96',
             'sequence.py': 'cd1ac5a145caeb9a4fa9c181aeb3bbbd021e4a59b37bbee5d2440b27081f06d2',
             'specifications.py': '3c34a078b8500dc1f9a13ea140c85fe9df7d4294986470989aafe128841b45c3',
             'synthesis.py': '7e61fe88d70eaf5485a82be3b98aba1e00dd2384847d635b80b04f8dbe014e19'}}


def v6_manifest():
    from copy import deepcopy
    manifest = deepcopy(V6_MANIFEST)
    manifest["python"] = list(sys.version_info[:2])
    return manifest


# Exact 0.7.0 runtime at 5c47fe7; retained by the UCR 16 integration at bf975f7.
V7_MANIFEST = {'autonomy': 'bounded_failure_conditioned_relational_subgoals_with_external_io',
 'capability_author': 'kernel_specification_conditioned_document_compiler',
 'capability_dialect': 'bounded_word_equations_and_typeset_block_recurrences',
 'engine_author': 'maintainer',
 'engine_policy_author': 'kernel_bounded_experience_conditioned_mutation',
 'faculties': {'CODE': 'native_expression_synthesis_and_ast_execution',
               'INTELLIGENCE': 'experience_conditioned_verified_gene_selection',
               'LOGIC': 'contracts_deficits_and_admission_evidence',
               'THINKING': 'causal_goal_selection_and_continuation'},
 'observations': {'author': 'maintainer',
                  'config': {'diagnostic_rows': 8,
                             'document_bytes': 262144,
                             'fields_per_record': 16,
                             'minimum_error_sources': 2,
                             'minimum_errors': 3,
                             'pairs_per_decision': 64,
                             'records_per_document': 128,
                             'training_rows': 8,
                             'tree_nodes': 8192,
                             'window_documents': 32},
                  'mechanism': 'measured_scalar_field_prediction_errors_v1'},
 'program_author': 'kernel_training_only',
 'python': [3, 12],
 'python_tools': 'pure_stdlib_composition_and_inherited_relation_transfer',
 'runtime': 'single_state_single_queue_single_journal',
 'schema': 'nova.kernel.v7',
 'search': {'attempts': 12000, 'depth': 3},
 'sources': {'__init__.py': '08bda2768122b12d64e2990afa22cd11cb102b64b6e7a7b2e04214ef2ff83cf4',
             '__main__.py': '1a65c967f8eb2fcf5b656932f22838f82ba0c4ae048e8cb5518234902e11947f',
             'adaptation.py': '8da801804b347568ee64ca9549c0bd6708a90a2f8b7a39f8f11bdc0edfd5c796',
             'autonomy.py': '0826a9dcbfaeae4374961f052d194c65d8da0774679e228e3cd55c51496e007a',
             'capability.py': '7c779e900c1f2774e660900128b431ee74b693198c589ecb4640de559afcaad1',
             'compatibility.py': 'd89210b6a27bbb5104995a1927cad67581d57eea602fd736658dabb730e2d254',
             'contracts.py': '54068e5bd79c3a896fb904aae0d5ff5544e1a7c921b7774da36d9c73f05212fe',
             'evaluation.py': '06ca272237362407ea65a559ae222acf41a99fceb574b3f945e34e8726279cf2',
             'extensions.py': '7b048dda1d3efcc510be6af1162ecd52fb7dddfa53ff01b106a003a74cf6ded2',
             'genetics.py': 'e3711266beea5cf000107fd839c3d804b946f8eefba0fef69e6fc6af5e0365a0',
             'isolation.py': 'c42b8a1a390f3c667a6a925b3118e882218664da234ca22c7886a4fd732fe3e3',
             'kernel.py': 'ce3c9fee131fbbdf2934fa7f8fec495bc88290fd6355eec41df93e06dd772d6a',
             'language.py': 'a541480da7093aaa401f82e1bf3aa7be5f4914ca57ac3222db0e7084af60e1a7',
             'library_evolution.py': 'db8b6f35af2a13cd84663cf03ba4ac8950593944f657011c8fa1ceeaf6d5074e',
             'memory.py': '3e8397ac08f8e303e313cac519498d49f010045975453508ab14decd8047a777',
             'observations.py': 'aa41a8e88f055da75ddeb2263de0384f969a8b3390cbe57ce48376dc16b1a020',
             'python_tools.py': '6e4ddb19f4897b470b0e94c547c7947a0925308af98af4f9178ae6dd2047a2eb',
             'sandbox_worker.py': '11482d41f951d639396b2a1e1412e2cb2f2afbab538db243a2f5e9889af59e96',
             'sequence.py': 'cd1ac5a145caeb9a4fa9c181aeb3bbbd021e4a59b37bbee5d2440b27081f06d2',
             'specifications.py': '3c34a078b8500dc1f9a13ea140c85fe9df7d4294986470989aafe128841b45c3',
             'synthesis.py': '7e61fe88d70eaf5485a82be3b98aba1e00dd2384847d635b80b04f8dbe014e19'}}


def v7_manifest():
    from copy import deepcopy
    manifest = deepcopy(V7_MANIFEST)
    manifest["python"] = list(sys.version_info[:2])
    return manifest


# Exact 0.8.0 runtime at main 1ec16e8, including pinned UCR 16 sources.
V8_MANIFEST = {'autonomy': 'bounded_failure_conditioned_relational_subgoals_with_external_io',
 'capability_author': 'kernel_specification_conditioned_document_compiler',
 'capability_dialect': 'bounded_word_equations_and_typeset_block_recurrences',
 'engine_author': 'maintainer',
 'engine_policy_author': 'kernel_bounded_experience_conditioned_mutation',
 'faculties': {'CODE': 'native_expression_synthesis_and_ast_execution',
               'INTELLIGENCE': 'experience_conditioned_verified_gene_selection',
               'LOGIC': 'contracts_deficits_and_admission_evidence',
               'THINKING': 'causal_goal_selection_and_continuation'},
 'observations': {'author': 'maintainer',
                  'config': {'diagnostic_rows': 8,
                             'document_bytes': 262144,
                             'fields_per_record': 16,
                             'minimum_error_sources': 2,
                             'minimum_errors': 3,
                             'pairs_per_decision': 64,
                             'records_per_document': 128,
                             'training_rows': 8,
                             'tree_nodes': 8192,
                             'window_documents': 32},
                  'mechanism': 'measured_scalar_field_prediction_errors_v1'},
 'program_author': 'kernel_training_only',
 'python': [3, 12],
 'python_tools': 'pure_stdlib_composition_and_inherited_relation_transfer',
 'runtime': 'single_state_single_queue_single_journal',
 'schema': 'nova.kernel.v8',
 'search': {'attempts': 12000, 'depth': 3},
 'sources': {'__init__.py': '4bba29bdb13279dc9d619cb9c3c2ff4bcb452195d96b72c4dfd7176ba383ca9d',
             '__main__.py': '1a65c967f8eb2fcf5b656932f22838f82ba0c4ae048e8cb5518234902e11947f',
             'adaptation.py': '8da801804b347568ee64ca9549c0bd6708a90a2f8b7a39f8f11bdc0edfd5c796',
             'autonomy.py': 'dc81e32746716dc3ab9b6d65b43ea75f48cb6589d9684ae3b6cf755ca9c57f80',
             'capability.py': 'eb8e8c51e1234b4121c10e1d6d53f1717d58aee0821861b1dd180878eec48f8f',
             'compatibility.py': '0321d7fcf6a453164049670fb40f5ade6397ea5b1a50b57fcbbde035b71cc446',
             'contracts.py': '54068e5bd79c3a896fb904aae0d5ff5544e1a7c921b7774da36d9c73f05212fe',
             'evaluation.py': '06ca272237362407ea65a559ae222acf41a99fceb574b3f945e34e8726279cf2',
             'extensions.py': '7b048dda1d3efcc510be6af1162ecd52fb7dddfa53ff01b106a003a74cf6ded2',
             'genetics.py': 'e3711266beea5cf000107fd839c3d804b946f8eefba0fef69e6fc6af5e0365a0',
             'isolation.py': 'c42b8a1a390f3c667a6a925b3118e882218664da234ca22c7886a4fd732fe3e3',
             'kernel.py': 'a1c4f93429796c2cb4047056fbdc57a99f21cd519951f73c674eb87eb6c0b111',
             'language.py': 'a541480da7093aaa401f82e1bf3aa7be5f4914ca57ac3222db0e7084af60e1a7',
             'library_evolution.py': '03974e74f665368e35fd7be26f49ba9ba3b82b187764b787c21a043eaef2fb27',
             'memory.py': '3e8397ac08f8e303e313cac519498d49f010045975453508ab14decd8047a777',
             'observations.py': 'cb2c17166ab93ca1dcdcda3bc36abbf332b677afba1cfa94e460a90087d38fad',
             'python_tools.py': '6e4ddb19f4897b470b0e94c547c7947a0925308af98af4f9178ae6dd2047a2eb',
             'sandbox_worker.py': '11482d41f951d639396b2a1e1412e2cb2f2afbab538db243a2f5e9889af59e96',
             'sequence.py': 'cd1ac5a145caeb9a4fa9c181aeb3bbbd021e4a59b37bbee5d2440b27081f06d2',
             'specifications.py': '3c34a078b8500dc1f9a13ea140c85fe9df7d4294986470989aafe128841b45c3',
             'synthesis.py': '7e61fe88d70eaf5485a82be3b98aba1e00dd2384847d635b80b04f8dbe014e19',
             'ucr_development.py': '00e1f84914097adf66aa20af418ed2ab58963c8028afdd87f147ed6eb93b7912'},
 'ucr_development': {'author': 'maintainer',
                     'config': {'candidates_per_round': 12,
                                'generated_per_round': 2048,
                                'input_fields': 1,
                                'max_depth': 3,
                                'native_fallback': True,
                                'training_rows': 8},
                     'mechanism': 'ucr_training_only_native_expression_proposals_v1',
                     'reader_version': '16.0',
                     'sources': {'nova_tools/__init__.py': 'e981bab21ded1efd6adeecb57930c3d639797507bb9e2ae4dfc605e727abdd17',
                                 'nova_tools/universal_code_reader.py': '19b6406ce896e20d7066cbcf52830c990c990640503068d43b4ccfcc17e30b36'}}}


def v8_manifest():
    from copy import deepcopy
    manifest = deepcopy(V8_MANIFEST)
    manifest["python"] = list(sys.version_info[:2])
    return manifest
