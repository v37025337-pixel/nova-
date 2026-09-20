def solve(inputs, recall):
    return primitive('json', primitive('strip', primitive('upper', primitive('parse_json', inputs['payload']))))
