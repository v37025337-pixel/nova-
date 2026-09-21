def solve(graph, genes):
    edges = {(e['src'], e['dst']) for e in graph['edges']}
    v2 = sum(x != y for x, y in edges)
    v1 = (genes['8a6bfca3bf3c55e25f659dbb11fd2b25550311cffff6e29948121d70405c0aa2'](graph, genes) - v2)
    return v1
