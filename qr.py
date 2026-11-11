"""A small, self-contained QR Code generator (byte mode, error correction L or M, versions 1-40).

Standard library only. Used to show the wallet link as a scannable code, so a phone wallet can open the trade.
The algorithm follows the QR Code Model 2 specification (ISO/IEC 18004).
"""

_ECC_FORMAT_BITS = {"L": 1, "M": 0}
_ECC_CODEWORDS_PER_BLOCK = {
    "L": (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "M": (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28,
          28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
}
_NUM_ERROR_CORRECTION_BLOCKS = {
    "L": (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17,
          18, 19, 19, 20, 21, 22, 24, 25),
    "M": (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29,
          31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
}


def _raw_modules(ver):
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2
        result -= (25 * n - 10) * n - 55
        if ver >= 7:
            result -= 36
    return result


def _data_codewords(ver, ecl):
    return (_raw_modules(ver) // 8
            - _ECC_CODEWORDS_PER_BLOCK[ecl][ver] * _NUM_ERROR_CORRECTION_BLOCKS[ecl][ver])


# ------------------------------------------------------------ Reed-Solomon

def _gf_mul(x, y):
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree):
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data, divisor):
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _add_ecc_and_interleave(data, ver, ecl):
    num_blocks = _NUM_ERROR_CORRECTION_BLOCKS[ecl][ver]
    block_ecc_len = _ECC_CODEWORDS_PER_BLOCK[ecl][ver]
    raw_codewords = _raw_modules(ver) // 8
    num_short = num_blocks - raw_codewords % num_blocks
    short_len = raw_codewords // num_blocks
    blocks, divisor, k = [], _rs_divisor(block_ecc_len), 0
    for i in range(num_blocks):
        dat = data[k:k + short_len - block_ecc_len + (0 if i < num_short else 1)]
        k += len(dat)
        ecc = _rs_remainder(dat, divisor)
        if i < num_short:
            dat = dat + [0]
        blocks.append(dat + ecc)
    result = []
    for i in range(len(blocks[0])):
        for j, block in enumerate(blocks):
            if i != short_len - block_ecc_len or j >= num_short:
                result.append(block[i])
    return result


# ----------------------------------------------------------------- matrix

class _Grid:
    def __init__(self, ver, ecl):
        self.ver, self.ecl = ver, ecl
        self.size = ver * 4 + 17
        self.mod = [[False] * self.size for _ in range(self.size)]
        self.fn = [[False] * self.size for _ in range(self.size)]

    def setf(self, x, y, dark):
        self.mod[y][x] = bool(dark)
        self.fn[y][x] = True

    def draw_function_patterns(self):
        n = self.size
        for i in range(n):
            self.setf(6, i, i % 2 == 0)
            self.setf(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self.setf(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = self._alignment_positions()
        count = len(pos)
        for i in range(count):
            for j in range(count):
                if not ((i == 0 and j == 0) or (i == 0 and j == count - 1) or (i == count - 1 and j == 0)):
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            self.setf(pos[i] + dx, pos[j] + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format_bits(0)  # reserve the area; rewritten once the mask is chosen
        self.draw_version()

    def _alignment_positions(self):
        if self.ver == 1:
            return []
        n = self.ver // 7 + 2
        step = 26 if self.ver == 32 else (self.ver * 4 + n * 2 + 1) // (n * 2 - 2) * 2
        result = [self.size - 7 - i * step for i in range(n - 1)] + [6]
        return list(reversed(result))

    def draw_format_bits(self, mask):
        data = _ECC_FORMAT_BITS[self.ecl] << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        bit = lambda i: ((bits >> i) & 1) != 0
        n = self.size
        for i in range(0, 6):
            self.setf(8, i, bit(i))
        self.setf(8, 7, bit(6))
        self.setf(8, 8, bit(7))
        self.setf(7, 8, bit(8))
        for i in range(9, 15):
            self.setf(14 - i, 8, bit(i))
        for i in range(0, 8):
            self.setf(n - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.setf(8, n - 15 + i, bit(i))
        self.setf(8, n - 8, True)

    def draw_version(self):
        if self.ver < 7:
            return
        rem = self.ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self.ver << 12 | rem
        for i in range(18):
            bit = ((bits >> i) & 1) != 0
            a, b = self.size - 11 + i % 3, i // 3
            self.setf(a, b, bit)
            self.setf(b, a, bit)

    def draw_codewords(self, data):
        n, i = self.size, 0
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(n):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = n - 1 - vert if upward else vert
                    if not self.fn[y][x] and i < len(data) * 8:
                        self.mod[y][x] = ((data[i >> 3] >> (7 - (i & 7))) & 1) != 0
                        i += 1
            right -= 2

    def apply_mask(self, mask):
        for y in range(self.size):
            for x in range(self.size):
                if self.fn[y][x]:
                    continue
                if mask == 0:
                    inv = (x + y) % 2 == 0
                elif mask == 1:
                    inv = y % 2 == 0
                elif mask == 2:
                    inv = x % 3 == 0
                elif mask == 3:
                    inv = (x + y) % 3 == 0
                elif mask == 4:
                    inv = (x // 3 + y // 2) % 2 == 0
                elif mask == 5:
                    inv = x * y % 2 + x * y % 3 == 0
                elif mask == 6:
                    inv = (x * y % 2 + x * y % 3) % 2 == 0
                else:
                    inv = ((x + y) % 2 + x * y % 3) % 2 == 0
                self.mod[y][x] ^= inv

    def penalty(self):
        n = self.size
        rows = ["".join("1" if v else "0" for v in r) for r in self.mod]
        cols = ["".join("1" if self.mod[y][x] else "0" for y in range(n)) for x in range(n)]
        score = 0
        for line in rows + cols:  # long runs of one colour
            run = 1
            for i in range(1, n):
                if line[i] == line[i - 1]:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + run - 5
                    run = 1
            if run >= 5:
                score += 3 + run - 5
        for y in range(n - 1):  # 2x2 blocks
            for x in range(n - 1):
                if self.mod[y][x] == self.mod[y][x + 1] == self.mod[y + 1][x] == self.mod[y + 1][x + 1]:
                    score += 3
        for line in rows + cols:  # finder-like patterns
            for pat in ("00001011101", "10111010000"):
                start = 0
                while True:
                    k = line.find(pat, start)
                    if k < 0:
                        break
                    score += 40
                    start = k + 1
        dark = sum(r.count("1") for r in rows)
        total = n * n
        score += ((abs(dark * 20 - total * 10) + total - 1) // total - 1) * 10
        return score


def encode(text, ecl="M"):
    """Return the QR code for `text` as a list of strings of '0'/'1' (no quiet zone)."""
    data = text.encode("utf-8")
    ver = None
    for v in range(1, 41):
        cc_bits = 8 if v <= 9 else 16
        if 4 + cc_bits + 8 * len(data) <= _data_codewords(v, ecl) * 8:
            ver = v
            break
    if ver is None:
        raise ValueError("text is too long for a QR code")
    cc_bits = 8 if ver <= 9 else 16
    bits = "0100" + format(len(data), "0%db" % cc_bits) + "".join(format(b, "08b") for b in data)
    capacity = _data_codewords(ver, ecl) * 8
    bits += "0" * min(4, capacity - len(bits))
    bits += "0" * (-len(bits) % 8)
    codewords = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(codewords) < capacity // 8:
        codewords.append(pad)
        pad ^= 0xEC ^ 0x11
    all_words = _add_ecc_and_interleave(codewords, ver, ecl)

    grid = _Grid(ver, ecl)
    grid.draw_function_patterns()
    grid.draw_codewords(all_words)
    best_mask, best_score = 0, None
    for mask in range(8):
        grid.apply_mask(mask)
        grid.draw_format_bits(mask)
        score = grid.penalty()
        if best_score is None or score < best_score:
            best_mask, best_score = mask, score
        grid.apply_mask(mask)  # undo
    grid.apply_mask(best_mask)
    grid.draw_format_bits(best_mask)
    return ["".join("1" if v else "0" for v in row) for row in grid.mod]
