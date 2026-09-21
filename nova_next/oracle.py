"""Independent specification oracle. Never uses UCR or candidate evaluation.

Bit-matrix Warshall closure is intentionally different from synthesized
relational composition/fixed-point programs. It specifies static graph queries,
not the dynamic behavior of downloaded Python.
"""

LAWS = {
    "reachable_pairs": "How many distinct downstream function pairs can be reached?",
    "indirect_pairs": "How many downstream pairs require more than a direct edge?",
    "maximum_impact": "How many other functions can the most influential function reach?",
}


def measure(graph):
    ids = [n["id"] for n in graph["nodes"]]
    index = {name: i for i, name in enumerate(ids)}
    bits = [0] * len(ids)
    direct = set()
    for edge in graph["edges"]:
        a, b = index[edge["src"]], index[edge["dst"]]
        bits[a] |= 1 << b
        if a != b:
            direct.add((a, b))
    for k in range(len(ids)):
        flag = 1 << k
        for i in range(len(ids)):
            if bits[i] & flag:
                bits[i] |= bits[k]
    counts = [(row & ~(1 << i)).bit_count() for i, row in enumerate(bits)]
    total = sum(counts)
    return {"reachable_pairs": total, "indirect_pairs": total - len(direct),
            "maximum_impact": max(counts, default=0)}
