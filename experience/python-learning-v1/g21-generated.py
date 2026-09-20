def solve(inputs, recall):
    return invoke('operator.lt', lift('builtins.float', invoke('str.split', inputs['left'], '.')), lift('builtins.float', invoke('str.split', inputs['right'], '.')))
