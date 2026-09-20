def fn_Ch(v_x, v_y, v_z):
    return word('xor', 32, word('and', 32, v_x, v_y), word('and', 32, word('not', 32, v_x), v_z))

def fn_Maj(v_x, v_y, v_z):
    return word('xor', 32, word('xor', 32, word('and', 32, v_x, v_y), word('and', 32, v_x, v_z)), word('and', 32, v_y, v_z))

def fn_Sigma_256_0(v_x):
    return word('xor', 32, word('xor', 32, word('rotr', 32, v_x, 2), word('rotr', 32, v_x, 13)), word('rotr', 32, v_x, 22))

def fn_Sigma_256_1(v_x):
    return word('xor', 32, word('xor', 32, word('rotr', 32, v_x, 6), word('rotr', 32, v_x, 11)), word('rotr', 32, v_x, 25))

def fn_sigma_256_0(v_x):
    return word('xor', 32, word('xor', 32, word('rotr', 32, v_x, 7), word('rotr', 32, v_x, 18)), word('shr', 32, v_x, 3))

def fn_sigma_256_1(v_x):
    return word('xor', 32, word('xor', 32, word('rotr', 32, v_x, 17), word('rotr', 32, v_x, 19)), word('shr', 32, v_x, 10))

def solve(inputs):
    budget = [20000]
    v_novaBytes = s_utf8(inputs['message'])
    v_novaBlocks = s_chunks(s_pad(v_novaBytes, 1, 448, 512, 64, 'big'), 64)
    v_K = [1116352408, 1899447441, 3049323471, 3921009573, 961987163, 1508970993, 2453635748, 2870763221, 3624381080, 310598401, 607225278, 1426881987, 1925078388, 2162078206, 2614888103, 3248222580, 3835390401, 4022224774, 264347078, 604807628, 770255983, 1249150122, 1555081692, 1996064986, 2554220882, 2821834349, 2952996808, 3210313671, 3336571891, 3584528711, 113926993, 338241895, 666307205, 773529912, 1294757372, 1396182291, 1695183700, 1986661051, 2177026350, 2456956037, 2730485921, 2820302411, 3259730800, 3345764771, 3516065817, 3600352804, 4094571909, 275423344, 430227734, 506948616, 659060556, 883997877, 958139571, 1322822218, 1537002063, 1747873779, 1955562222, 2024104815, 2227730452, 2361852424, 2428436474, 2756734187, 3204031479, 3329325298]
    v_H = [1779033703, 3144134277, 1013904242, 2773480762, 1359893119, 2600822924, 528734635, 1541459225]
    for v_i in s_range(1, s_size(v_novaBlocks), budget):
        v_previous_H = s_copy(v_H)
        v_M = s_words(s_at(v_novaBlocks, word('sub', 32, v_i, 1)), 32, 'big')
        v_W = s_zeros(64)
        for v_t in s_range(0, 15, budget):
            s_put(v_W, v_t, s_at(v_M, v_t))
        for v_t in s_range(16, 63, budget):
            s_put(v_W, v_t, word('add', 32, word('add', 32, word('add', 32, fn_sigma_256_1(s_at(v_W, word('sub', 32, v_t, 2))), s_at(v_W, word('sub', 32, v_t, 7))), fn_sigma_256_0(s_at(v_W, word('sub', 32, v_t, 15)))), s_at(v_W, word('sub', 32, v_t, 16))))
        v_a = s_at(v_previous_H, 0)
        v_b = s_at(v_previous_H, 1)
        v_c = s_at(v_previous_H, 2)
        v_d = s_at(v_previous_H, 3)
        v_e = s_at(v_previous_H, 4)
        v_f = s_at(v_previous_H, 5)
        v_g = s_at(v_previous_H, 6)
        v_h = s_at(v_previous_H, 7)
        for v_t in s_range(0, 63, budget):
            v_T1 = word('add', 32, word('add', 32, word('add', 32, word('add', 32, v_h, fn_Sigma_256_1(v_e)), fn_Ch(v_e, v_f, v_g)), s_at(v_K, v_t)), s_at(v_W, v_t))
            v_T2 = word('add', 32, fn_Sigma_256_0(v_a), fn_Maj(v_a, v_b, v_c))
            v_h = v_g
            v_g = v_f
            v_f = v_e
            v_e = word('add', 32, v_d, v_T1)
            v_d = v_c
            v_c = v_b
            v_b = v_a
            v_a = word('add', 32, v_T1, v_T2)
        s_put(v_H, 0, word('add', 32, v_a, s_at(v_previous_H, 0)))
        s_put(v_H, 1, word('add', 32, v_b, s_at(v_previous_H, 1)))
        s_put(v_H, 2, word('add', 32, v_c, s_at(v_previous_H, 2)))
        s_put(v_H, 3, word('add', 32, v_d, s_at(v_previous_H, 3)))
        s_put(v_H, 4, word('add', 32, v_e, s_at(v_previous_H, 4)))
        s_put(v_H, 5, word('add', 32, v_f, s_at(v_previous_H, 5)))
        s_put(v_H, 6, word('add', 32, v_g, s_at(v_previous_H, 6)))
        s_put(v_H, 7, word('add', 32, v_h, s_at(v_previous_H, 7)))
    return s_hex([s_at(v_H, 0), s_at(v_H, 1), s_at(v_H, 2), s_at(v_H, 3), s_at(v_H, 4), s_at(v_H, 5), s_at(v_H, 6), s_at(v_H, 7)], 32, 'big')
