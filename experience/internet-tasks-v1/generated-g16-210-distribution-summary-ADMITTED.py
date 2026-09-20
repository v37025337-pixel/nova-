def solve(inputs, recall):
    return {'bytes': recall('ef0c699e5813737c0db6bdebdda7e7ebcc996a19c166bb08ec6e43b4b20d0750', inputs), 'files': primitive('length', inputs['values']), 'sizes': primitive('sort', inputs['values'])}
