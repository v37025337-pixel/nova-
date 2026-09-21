def solve(graph, genes):
    edges = {(e['src'], e['dst']) for e in graph['edges']}
    v2 = edges
    for _ in range(len(graph['nodes']) + 1):
        v4_index = {}
        for x, y in v2:
            v4_index.setdefault(x, set()).add(y)
        v4 = {(x, z) for x, y in edges for z in v4_index.get(y, ())}
        v3 = (v2 | v4)
        if v3 == v2:
            break
        v2 = v3
    else:
        raise ValueError('fixed point budget')
    v1 = sum(x != y for x, y in v2)
    return v1
