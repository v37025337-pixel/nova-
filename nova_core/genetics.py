"""Immutable program genomes; variation has no state outside the runtime journal."""

from .contracts import ContractError, digest
from .language import check


def genome(bindings, parent=None, engine=None):
    body = {"schema": "nova.genome.v1", "parent": parent,
            "bindings": dict(sorted(bindings.items())), "genes": sorted(set(bindings.values()))}
    if engine is not None:
        from .synthesis import check_policy
        check_policy(engine)
        body.update(schema="nova.genome.v2", engine=engine)
    return {**body, "id": digest(body)}


def vary(parent, task_id, program, memory):
    """Construct a proposed genotype; admission is the only operation that activates it."""
    if genome(parent["bindings"], parent["parent"], parent.get("engine")) != parent:
        raise ContractError("parent genome identity mismatch")
    if set(parent["genes"]) != set(memory):
        raise ContractError("genome and executable gene memory disagree")
    check(program, memory)
    if any(pid not in parent["genes"] for pid in program["parents"]):
        raise ContractError("mutation references a non-inherited gene")
    child = genome({**parent["bindings"], task_id: program["id"]}, parent["id"], parent.get("engine"))
    added = sorted(set(child["genes"]) - set(parent["genes"]))
    kind = "BIND_EXISTING_GENE" if not added else "COMPOSE_AND_ADD_GENE" if program["parents"] else "ADD_GENE"
    return {"kind": kind, "parent_genome": parent["id"], "child_genome": child,
            "added_genes": added, "inherited_genes": parent["genes"],
            "expression_parents": program["parents"]}
