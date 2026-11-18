#!/usr/bin/env python3
"""THE WORLD IN ONE DAY - Wednesday 18 November 2026.

A program that draws one newspaper-style infographic of the day's world
news and writes it to entry.png.  Python standard library only: the PNG is
encoded by hand (zlib + struct + binascii), all art is drawn procedurally,
and the text uses an embedded 5x7 bitmap font.  No network, no randomness,
no time: two runs produce byte-identical output.

Layout (1024 x 1024), a broadsheet with one dominant hero:
  masthead -> one giant hero (Gulf strikes) -> two sub-heroes
  (Kerch Bridge, Shenzhen summit) -> world map with numbered pins ->
  BY THE NUMBERS strip -> THE DAY IN BRIEF (12 stories) ->
  ALSO ON THIS DAY index (33 more) -> sources footer.
48 stories in total, six continents.
"""

import binascii
import os
import struct
import sys
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
INK = (16, 24, 40)          # near-black navy
PAPER = (250, 247, 238)     # warm newsprint
PAPER2 = (242, 236, 222)    # slightly darker newsprint
NAVY = (13, 32, 61)         # masthead
NAVY2 = (23, 52, 92)
GOLD = (201, 162, 39)
RED = (178, 34, 34)
RED2 = (214, 69, 55)
TEAL = (18, 74, 78)         # map band
TEAL2 = (27, 105, 110)
SAND = (226, 205, 160)      # land on map
SEA = (16, 58, 66)
GREY = (90, 96, 108)
LGREY = (200, 204, 210)
WHITE = (255, 255, 255)
SKY = (52, 96, 138)
SKY2 = (30, 64, 96)
SEA2 = (24, 68, 92)
ORANGE = (232, 126, 32)
YELLOW = (244, 196, 66)
SMOKE = (120, 124, 132)

# ------------------------------------------------------------------- canvas


class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bg) * (w * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c, fill=True):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d = (xx - cx) ** 2 + (yy - cy) ** 2
                if fill:
                    if d <= r * r:
                        self.set(xx, yy, c)
                else:
                    if r * r - 2 * r <= d <= r * r:
                        self.set(xx, yy, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            for xx in range(cx - rx, cx + rx + 1):
                if ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0:
                    self.set(xx, yy, c)

    def poly(self, pts, c):
        """Scanline fill of a polygon (list of (x, y))."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(int(x0 + t * (x1 - x0)))
            xs.sort()
            for j in range(0, len(xs) - 1, 2):
                self.rect(xs[j], y, xs[j + 1] - xs[j] + 1, 1, c)

    def tri(self, a, b, c, col):
        self.poly([a, b, c], col)

    def burst(self, cx, cy, r, c1, c2):
        """Starburst: alternating long/short spikes, like an explosion."""
        import math
        pts = []
        for k in range(24):
            ang = k * math.pi / 12.0
            rr = r if k % 2 == 0 else r * 0.45
            pts.append((int(cx + rr * math.cos(ang)),
                        int(cy + rr * math.sin(ang))))
        self.poly(pts, c1)
        self.circle(cx, cy, max(2, r // 3), c2)


# ---------------------------------------------------------------- PNG encode


def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        row = bytes(cv.px[y * stride:(y + 1) * stride])
        # Try filter 0 (None) and filter 1 (Sub); keep the smaller row.
        sub = bytearray(row)
        for i in range(3, len(sub)):
            sub[i] = (sub[i] - sub[i - 3]) & 0xFF
        if len(zlib.compress(bytes(sub), 1)) < len(zlib.compress(row, 1)):
            raw.append(1)
            raw.extend(sub)
        else:
            raw.append(0)
            raw.extend(row)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", binascii.crc32(typ + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ------------------------------------------------------------- bitmap font
# 5x7 glyphs, rows top to bottom, '#' = pixel on.  One dict, all glyphs the
# page needs.  Lowercase uses the same 7-row cell (x-height rows 2..6).
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    'D': ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    'a': ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    'b': ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    'c': ("00000", "00000", "01110", "10000", "10000", "10001", "01110"),
    'd': ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    'e': ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    'f': ("00110", "01001", "01000", "11110", "01000", "01000", "01000"),
    'g': ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    'h': ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    'i': ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    'j': ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    'k': ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    'l': ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    'm': ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    'n': ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    'o': ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    'p': ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    'q': ("00000", "00000", "01111", "10001", "10001", "01111", "00001"),
    'r': ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    's': ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    't': ("01000", "01000", "11110", "01000", "01000", "01000", "00110"),
    'u': ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    'v': ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    'w': ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    'x': ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    'y': ("00000", "00000", "10001", "10001", "01111", "00001", "01110"),
    'z': ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    '3': ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ':': ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ';': ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    '-': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '\u2013': ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    '\u2014': ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    '(': ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ')': ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    '/': ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    '%': ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '$': ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    '&': ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    '+': ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    '=': ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '*': ("00000", "00100", "10101", "01110", "10101", "00100", "00000"),
    '#': ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    '@': ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    '[': ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    ']': ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    '_': ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    '<': ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    '>': ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    '\u2022': ("00000", "00000", "01100", "01100", "01100", "00000", "00000"),
    '\u00b0': ("01100", "10010", "01100", "00000", "00000", "00000", "00000"),
    '\u00d7': ("00000", "10001", "01010", "00100", "01010", "10001", "00000"),
    '\u25b2': ("00100", "01110", "11111", "11111", "11111", "00000", "00000"),
    '\u25bc': ("00000", "11111", "11111", "11111", "01110", "00100", "00000"),
    '\u201c': ("01010", "01010", "00100", "00000", "00000", "00000", "00000"),
    '\u201d': ("01010", "01010", "00100", "00000", "00000", "00000", "00000"),
    '\u2019': ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
}

CHAR_W = 6  # 5 px glyph + 1 px gap, times scale


def text_w(s, scale):
    return len(s) * CHAR_W * scale - scale


def draw_text(cv, x, y, s, scale, col, bold=False):
    """Draw text at top-left (x, y). Returns width used."""
    cx = x
    for ch in s:
        g = FONT.get(ch, FONT['?'])
        for r, row in enumerate(g):
            for c, bit in enumerate(row):
                if bit == '1':
                    cv.rect(cx + c * scale, y + r * scale, scale, scale, col)
                    if bold and scale >= 2:
                        cv.rect(cx + c * scale + 1, y + r * scale,
                                scale, scale, col)
        cx += CHAR_W * scale
    return cx - x


def draw_centered(cv, cx, y, s, scale, col, bold=False):
    draw_text(cv, cx - text_w(s, scale) // 2, y, s, scale, col, bold)


def wrap(s, max_chars):
    """Greedy word wrap to lines of at most max_chars characters."""
    words = s.split(' ')
    lines, cur = [], ''
    for wd in words:
        if cur and len(cur) + 1 + len(wd) > max_chars:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + ' ' + wd) if cur else wd
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, y, s, scale, col, max_chars, lh=None, bold=False):
    """Draw wrapped paragraph; returns y after last line."""
    lh = lh if lh is not None else 9 * scale
    for ln in wrap(s, max_chars):
        draw_text(cv, x, y, ln, scale, col, bold)
        y += lh
    return y

# ------------------------------------------------------------ illustrations
# Every scene is drawn from primitives: no photos, no external art.


def draw_gulf(cv, x, y, w, h):
    """Hero: night sea in the Gulf, Qeshm Island, jets, blasts, tankers."""
    cv.rect(x, y, w, h, SKY2)
    # dusk sky bands
    cv.rect(x, y, w, h // 3, (44, 78, 110))
    cv.rect(x, y + h // 3, w, h // 6, (96, 74, 72))
    cv.rect(x, y + h // 2, w, h // 6, (150, 96, 60))
    # sun glow low on the horizon
    cv.circle(x + w - 130, y + h // 2 - 6, 26, (244, 170, 80))
    cv.circle(x + w - 130, y + h // 2 - 6, 16, (250, 210, 130))
    # sea
    sea_y = y + int(h * 0.58)
    cv.rect(x, sea_y, w, h - int(h * 0.58), SEA2)
    for k in range(7):
        yy = sea_y + 8 + k * 12
        cv.hline(x + (k * 97) % 200, yy, w - ((k * 97) % 200) - 40,
                 (52, 110, 138))
    # Qeshm island silhouette, left
    isl = [(x + 20, sea_y), (x + 60, sea_y - 46), (x + 120, sea_y - 58),
           (x + 190, sea_y - 40), (x + 250, sea_y - 52), (x + 300, sea_y - 18),
           (x + 320, sea_y), (x + 20, sea_y)]
    cv.poly(isl, (28, 34, 44))
    # missile site on the island: launcher + blast
    cv.rect(x + 150, sea_y - 78, 4, 22, (200, 200, 200))
    cv.line(x + 152, sea_y - 78, x + 138, sea_y - 108, (230, 230, 230))
    cv.burst(x + 132, sea_y - 88, 22, ORANGE, YELLOW)
    cv.burst(x + 168, sea_y - 78, 14, RED2, ORANGE)
    # smoke columns (kept inside the panel)
    cv.ellipse(x + 120, sea_y - 92, 12, 14, (90, 90, 96))
    cv.ellipse(x + 132, sea_y - 84, 9, 11, (110, 110, 116))
    # tanker on the right, burning
    tx, ty = x + w - 330, sea_y + 26
    cv.rect(tx, ty, 220, 26, (40, 40, 46))
    cv.rect(tx + 150, ty - 22, 34, 22, (52, 52, 58))
    cv.rect(tx + 10, ty - 14, 26, 14, (60, 60, 66))
    cv.burst(tx + 60, ty - 8, 22, ORANGE, YELLOW)
    cv.burst(tx + 190, ty - 2, 14, RED2, ORANGE)
    # carrier silhouette, centre-right on the water
    cx0, cy0 = x + w // 2 + 60, sea_y + 30
    cv.rect(cx0, cy0, 190, 16, (24, 28, 36))
    cv.rect(cx0 + 130, cy0 - 26, 26, 26, (24, 28, 36))
    cv.line(cx0 + 143, cy0 - 26, cx0 + 143, cy0 - 44, (24, 28, 36))
    # jets: two swept silhouettes with contrails
    for jx, jy in ((x + 120, y + 44), (x + 300, y + 26)):
        cv.tri((jx, jy), (jx + 46, jy + 8), (jx + 8, jy + 12), (210, 214, 220))
        cv.tri((jx + 10, jy + 4), (jx + 30, jy - 12), (jx + 34, jy + 6),
               (210, 214, 220))
        cv.line(jx - 90, jy + 10, jx - 4, jy + 8, (220, 220, 220))
    # drones: small dots with trails, heading left
    for dx, dy in ((x + w - 90, y + 90), (x + w - 160, y + 120),
                   (x + w - 60, y + 150)):
        cv.circle(dx, dy, 3, (255, 255, 255))
        cv.line(dx + 4, dy, dx + 44, dy - 6, (200, 200, 200))
    # radar arcs from a small base on the far shore
    bx, by = x + w - 60, sea_y - 4
    cv.rect(bx, by, 26, 8, (70, 76, 84))
    for r in (18, 30, 42):
        for a in range(-70, 71, 6):
            import math
            px = int(bx + 13 + r * math.cos(math.radians(a - 90)))
            py = int(by - r * math.sin(math.radians(a - 90)) * 0.9)
            cv.set(px, py, (150, 200, 210))


def draw_kerch(cv, x, y, w, h):
    """Sub-hero: the Kerch Bridge over the strait, one span down."""
    cv.rect(x, y, w, h, (168, 196, 214))
    cv.rect(x, y, w, h // 2, (120, 158, 190))
    # strait
    wy = y + int(h * 0.55)
    cv.rect(x, wy, w, h - int(h * 0.55), (64, 110, 150))
    for k in range(3):
        cv.hline(x + (k * 53) % 90, wy + 8 + k * 10, w - 60, (120, 170, 205))
    # bridge deck: left part intact, middle span collapsed into water
    dy = y + 26
    cv.rect(x, dy, w // 2 - 30, 7, (240, 240, 240))
    cv.rect(x + w // 2 + 60, dy, w - (w // 2 + 60), 7, (240, 240, 240))
    # fallen span, tilted into the strait
    cv.line(x + w // 2 - 30, dy + 4, x + w // 2 + 58, wy + 16, (225, 225, 225))
    cv.line(x + w // 2 - 30, dy + 7, x + w // 2 + 58, wy + 19, (200, 200, 200))
    # arch over the intact half
    for k in range(0, 181, 6):
        import math
        ax = x + 10 + int((w // 2 - 60) * k / 180.0)
        ay = dy - int(26 * math.sin(math.radians(k)))
        cv.set(ax, ay, (250, 250, 250))
        cv.set(ax, ay + 1, (250, 250, 250))
    # pylons
    for px in (x + 30, x + w // 2 - 60, x + w // 2 + 90, x + w - 40):
        cv.rect(px, dy + 7, 6, wy - dy - 4, (210, 214, 218))
    # smoke + splash at the break
    cv.ellipse(x + w // 2 + 14, dy - 8, 12, 10, SMOKE)
    cv.ellipse(x + w // 2 + 30, dy - 20, 9, 8, (140, 142, 146))
    cv.burst(x + w // 2 + 20, wy + 8, 12, (220, 230, 235), WHITE)
    # drone dots above
    for dx, dyy in ((x + w - 70, y + 10), (x + w - 110, y + 22),
                    (x + 60, y + 8)):
        cv.circle(dx, dyy, 2, INK)
        cv.line(dx + 3, dyy, dx + 18, dyy - 3, (90, 96, 108))


def draw_shenzhen(cv, x, y, w, h):
    """Sub-hero: Shenzhen skyline at dusk, three flags, summit table."""
    cv.rect(x, y, w, h, (24, 38, 66))
    base = y + h - 26  # skyline sits on this line; table row below it
    cv.rect(x, base, w, 26, (16, 26, 46))
    # skyline silhouettes (heights fit the art strip above the table row)
    towers = [(0, 18), (34, 24), (74, 20), (112, 26), (152, 21),
              (196, 25), (236, 19), (276, 23), (316, 26), (356, 20),
              (396, 24), (430, 18)]
    for tx, th in towers:
        cv.rect(x + tx, base - th, 30, th, (38, 56, 88))
        for wy in range(base - th + 4, base - 2, 7):
            for wx in range(x + tx + 5, x + tx + 26, 9):
                cv.set(wx, wy, YELLOW)
    # one tall tapered tower
    cv.poly([(x + 150, base), (x + 158, y + 4), (x + 168, y + 4),
             (x + 176, base)], (52, 76, 116))
    cv.circle(x + 163, y + 3, 2, YELLOW)
    # three flags on poles above the skyline
    flag_cols = [(178, 34, 34), (255, 255, 255), (201, 162, 39)]
    for i, fc in enumerate(flag_cols):
        fx = x + 30 + i * 46
        cv.vline(fx, y + 6, 18, (220, 220, 220))
        cv.rect(fx, y + 6, 30, 13, fc)
        if i == 1:
            cv.rect(fx + 6, y + 9, 4, 4, RED)
    # summit table + three chairs, foreground row
    cv.rect(x + w // 2 - 70, base + 8, 140, 4, (120, 84, 40))
    for cxp in (x + w // 2 - 56, x + w // 2, x + w // 2 + 56):
        cv.rect(cxp - 8, base + 14, 16, 10, (70, 52, 30))
        cv.circle(cxp, base + 11, 5, (226, 205, 170))


# ---------------------------------------------------------------- world map
# Coarse continent outlines as (lon, lat) points, equirectangular.

N_AMERICA = [(-168, 66), (-140, 70), (-125, 72), (-110, 73), (-95, 80),
             (-85, 80), (-75, 73), (-65, 60), (-55, 52), (-60, 47),
             (-70, 42), (-75, 35), (-80, 26), (-85, 30), (-90, 21),
             (-97, 16), (-105, 20), (-115, 28), (-125, 40), (-125, 49),
             (-140, 60), (-155, 58), (-165, 60), (-168, 66)]
S_AMERICA = [(-80, 10), (-75, 5), (-80, -3), (-80, -10), (-70, -18),
             (-70, -30), (-65, -40), (-65, -52), (-70, -55), (-60, -50),
             (-55, -35), (-48, -28), (-40, -20), (-35, -8), (-40, -3),
             (-50, 0), (-55, 5), (-60, 8), (-70, 11), (-77, 8), (-80, 10)]
AFRICA = [(-17, 15), (-17, 21), (-10, 31), (-5, 35), (10, 37), (20, 32),
          (32, 31), (35, 28), (38, 22), (43, 12), (48, 11), (51, 12),
          (44, 0), (40, -10), (35, -20), (32, -28), (26, -34), (19, -35),
          (15, -27), (12, -18), (9, -1), (9, 4), (-8, 4), (-13, 8),
          (-17, 15)]
EURASIA = [(-10, 36), (-9, 43), (-2, 48), (-5, 50), (0, 51), (5, 53),
           (8, 57), (10, 59), (18, 56), (21, 55), (24, 58), (28, 60),
           (30, 62), (40, 68), (55, 68), (70, 72), (80, 73), (100, 76),
           (120, 73), (140, 72), (160, 70), (178, 66), (170, 60),
           (162, 56), (158, 52), (142, 50), (140, 40), (135, 35),
           (130, 33), (127, 35), (122, 38), (120, 32), (122, 28),
           (115, 23), (108, 20), (105, 10), (100, 8), (98, 12), (95, 16),
           (92, 21), (88, 22), (85, 19), (80, 15), (77, 8), (75, 12),
           (72, 20), (68, 23), (62, 25), (58, 26), (54, 27), (50, 29),
           (48, 30), (44, 29), (40, 32), (36, 36), (30, 36), (27, 37),
           (23, 36), (22, 39), (18, 40), (15, 44), (12, 44), (8, 44),
           (3, 43), (0, 40), (-2, 37), (-6, 36), (-9, 37), (-10, 36)]
AUSTRALIA = [(113, -22), (114, -30), (115, -35), (120, -34), (125, -32),
             (130, -32), (135, -35), (140, -38), (145, -38), (150, -37),
             (153, -32), (153, -27), (150, -23), (146, -19), (142, -15),
             (142, -11), (137, -12), (135, -15), (132, -12), (130, -13),
             (126, -14), (122, -17), (118, -20), (113, -22)]
UK = [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (1, 51),
      (-5, 50)]
JAPAN = [(130, 31), (132, 33), (135, 34), (138, 35), (140, 38), (141, 41),
         (143, 43), (141, 45), (139, 42), (136, 37), (132, 34), (130, 31)]
MADAGASCAR = [(44, -16), (47, -20), (45, -25), (43, -22), (44, -16)]
NEW_ZEALAND = [(167, -45), (170, -43), (173, -41), (175, -38), (178, -37),
               (176, -40), (172, -43), (168, -46), (167, -45)]
INDONESIA = [(95, 5), (100, 0), (105, -6), (110, -7), (115, -8), (120, -9),
             (125, -9), (130, -4), (135, -3), (140, -4), (141, -1),
             (136, 0), (130, 1), (125, 2), (120, 1), (115, 2), (110, 1),
             (105, 2), (100, 4), (95, 5)]

CONTINENTS = [N_AMERICA, S_AMERICA, AFRICA, EURASIA, AUSTRALIA, UK, JAPAN,
              MADAGASCAR, NEW_ZEALAND, INDONESIA]


def draw_map(cv, x, y, w, h, pins):
    """World map band. pins: list of (number, lon, lat, colour)."""
    cv.rect(x, y, w, h, TEAL)
    # faint graticule
    for k in range(1, 8):
        gx = x + w * k // 8
        for yy in range(y + 4, y + h - 4, 6):
            cv.set(gx, yy, (36, 96, 100))
    for k in range(1, 4):
        gy = y + h * k // 4
        for xx in range(x + 4, x + w - 4, 6):
            cv.set(xx, gy, (36, 96, 100))

    def proj(lon, lat):
        px = x + int((lon + 180.0) / 360.0 * w)
        py = y + int((75.0 - lat) / 135.0 * h)
        return (px, py)

    for cont in CONTINENTS:
        cv.poly([proj(lo, la) for lo, la in cont], SAND)
    # pin markers with numbers
    for num, lon, lat, col in pins:
        px, py = proj(lon, lat)
        cv.circle(px, py - 4, 9, col)
        cv.circle(px, py - 4, 9, WHITE, fill=False)
        draw_centered(cv, px, py - 8, str(num), 1, WHITE, bold=True)
        cv.line(px, py + 5, px, py + 9, col)

# ------------------------------------------------------------------ content
# 48 stories, verified 18 Nov 2026 from oneturn.news, openchronicle.org
# and earnings/market reporting the same day.

BRIEF = [  # (number, one-line headline, max 39 chars)
    (4, "Peltola wins Alaska; Senate 56-44 Dem"),
    (5, "Nvidia: $115.8bn revenue, up 103%"),
    (6, "Stocks fall; S&P 500 down 1.03%"),
    (7, "Ebola in DR Congo doubles: 11,000+"),
    (8, "Cyclone Xavier, Cat 5, hits Cooks"),
    (9, "NSA outage was maintenance, not hack"),
    (10, "Trump weighs Iran 'dirty bomb' report"),
    (11, "World Court to rule on Rohingya case"),
    (12, "Five EU states plan Rwanda return hubs"),
    (13, "27 years for Iran-linked Trump plot"),
    (14, "Russian military plane crashes; 19 dead"),
    (15, "140,000 join French pay protests"),
]

ALSO = [  # (number, one-line item, max 50 chars)
    (16, "Houthis press toward Aden"),
    (17, "US faults Ukraine strikes; Berlin objects"),
    (18, "Board of Peace: Gaza truce may collapse"),
    (19, "Turkey takes over Sozcu TV"),
    (20, "Serbia parliament opens, students in charge"),
    (21, "Eritrea border clashes raise war fears"),
    (22, "South Korea lifts 2027 growth to 3.9%"),
    (23, "France-Malaysia pact on rare earths"),
    (24, "Real falls as Lula fiscal plan disappoints"),
    (25, "Europe pays up for LNG, stocks low"),
    (26, "Pakistan solar share hits 28%"),
    (27, "US boosts funds for Palau, FSM, Marshalls"),
    (28, "US tightens chip-access rules for China"),
    (29, "Anthropic to list on Nasdaq Nov 19"),
    (30, "Fiji declares disaster over El Nino drought"),
    (31, "NASA contest on nuclear power for students"),
    (32, "New daisy genus honours Canterbury botanist"),
    (33, "WHO warns on antimicrobial resistance"),
    (34, "Olive ridley hatchlings freed in California"),
    (35, "Cricket Australia opens sandpapergate forum"),
    (36, "Noguchi: Japan's first sake living treasure"),
    (37, "Fela Kuti first African in Rock Hall"),
    (38, "Zverev reaches ATP Finals knockouts"),
    (39, "N. Ireland promoted in Nations League"),
    (40, "Tiger Woods to return in December"),
    (41, 'Word of the year: "human"'),
    (42, "Earthshot winners celebrated in Mumbai"),
    (43, "Robert Pattinson named new James Bond"),
    (44, "Pope Leo reveals cancer surgery"),
    (45, "Isolated Awa group emerges in Amazon"),
    (46, "Eisenkot ally elected Knesset speaker"),
    (47, "US soldier in UK spy case moved to US"),
    (48, "ADNOC ship hit in Hormuz; 11 hurt, 1 lost"),
]

NUMBERS = [  # (label, value, down?)
    ("S&P 500", "7,341", True),
    ("BRENT CRUDE", "$92.47", True),
    ("GOLD", "-2.05%", True),
    ("NVIDIA REV.", "$115.8BN", False),
    ("US SENATE", "56-44 DEM", False),
    ("CYCLONE XAVIER", "315 KM/H", False),
]

PINS = [  # (story number, lon, lat, colour)
    (1, 56.0, 26.5, RED),
    (2, 36.5, 45.3, RED),
    (3, 114.0, 22.5, GOLD),
    (4, 121.0, 14.6, NAVY2),
    (5, -152.0, 64.0, NAVY2),
    (6, -122.0, 37.0, NAVY2),
    (7, 23.0, -2.0, RED2),
    (8, -160.0, -21.0, RED2),
    (9, 2.3, 48.8, NAVY2),
    (10, 87.0, 55.0, NAVY2),
    (11, 178.0, -18.0, NAVY2),
    (12, 34.5, 31.5, RED),
]

MX = 24            # side margin
CW = W - 2 * MX    # content width = 976


def render():
    cv = Canvas(W, H, PAPER)

    # ---- top gold rule + masthead -------------------------------------
    cv.rect(0, 0, W, 6, GOLD)
    cv.rect(0, 6, W, 100, NAVY)
    cv.rect(0, 106, W, 2, GOLD)
    draw_text(cv, MX, 22, "THE WORLD IN ONE DAY", 4, WHITE, bold=True)
    draw_text(cv, MX, 66, "WEDNESDAY 18 NOVEMBER 2026", 2, GOLD, bold=True)
    draw_text(cv, MX, 88, "48 STORIES FROM SIX CONTINENTS, ON ONE PAGE",
              1, (190, 200, 215))
    # right block: big story count
    cv.vline(W - MX - 190, 22, 68, GOLD)
    draw_text(cv, W - MX - 168, 20, "48", 5, WHITE, bold=True)
    draw_text(cv, W - MX - 96, 34, "STORIES", 2, GOLD, bold=True)
    draw_text(cv, W - MX - 96, 58, "6 CONTINENTS", 1, (190, 200, 215))

    # ---- hero: the Gulf ----------------------------------------------
    hy, hh = 114, 188
    draw_gulf(cv, MX, hy, CW, hh)
    # kicker chip on the art
    cv.rect(MX + 10, hy + 10, 250, 20, RED)
    draw_text(cv, MX + 18, hy + 15, "1  THE GULF - CONFLICT", 1, WHITE,
              bold=True)
    # headline band under the art
    by = hy + hh
    cv.rect(MX, by, CW, 94, WHITE)
    cv.rect(MX, by, CW, 3, RED)
    draw_text(cv, MX + 12, by + 12,
              "U.S. JETS STRIKE IRAN MISSILE SITE ON QESHM", 3, INK,
              bold=True)
    draw_text(cv, MX + 12, by + 40,
              "TEHRAN'S DRONES HIT BAHRAIN AND KUWAIT", 3, RED, bold=True)
    draw_text(cv, MX + 12, by + 72,
              "Third U.S. carrier arrives as tankers burn off Hormuz; "
              "Qatar urges talks.", 2, GREY)

    # ---- two sub-heroes ----------------------------------------------
    sy, sh = 404, 116
    pw = (CW - 16) // 2
    for i, (num, kick, head, deck, fn) in enumerate([
        (2, "2  UKRAINE - WAR",
         "UKRAINE HITS KERCH BRIDGE FOR 2ND DAY - ROAD SPAN FALLS INTO STRAIT",
         "Zelenskyy calls the strike unprecedented; Kyiv seeks 12 more jets.",
         draw_kerch),
        (3, "3  SHENZHEN - SUMMIT",
         "XI AND PUTIN MEET IN SHENZHEN - TRUMP JOINS THEM ON THURSDAY",
         "Quad leaders gather in Manila as APEC turns three-power.",
         draw_shenzhen),
    ]):
        px = MX + i * (pw + 16)
        cv.rect(px, sy, pw, sh, PAPER2)
        cv.rect(px, sy, pw, 2, NAVY2)
        fn(cv, px, sy + 2, pw, 56)
        draw_text(cv, px + 8, sy + 64, kick, 1, RED, bold=True)
        y = draw_para(cv, px + 8, sy + 76, head, 2, INK, 40, lh=17,
                      bold=True)
        draw_text(cv, px + 8, sy + 76 + 34, deck, 1, GREY)

    # ---- world map ----------------------------------------------------
    my, mh = 528, 120
    draw_map(cv, MX, my, CW, mh, PINS)
    cv.rect(MX + 8, my + mh - 26, 330, 18, NAVY)
    draw_text(cv, MX + 16, my + mh - 22, "WHERE THE DAY HAPPENED - 12 PLACES",
              1, WHITE, bold=True)

    # ---- by the numbers ----------------------------------------------
    ny, nh = 656, 56
    bw = CW // 6
    for i, (lab, val, down) in enumerate(NUMBERS):
        bx = MX + i * bw
        cv.rect(bx + 2, ny, bw - 4, nh, WHITE)
        cv.rect(bx + 2, ny, bw - 4, 3, GOLD if i % 2 == 0 else RED)
        draw_text(cv, bx + 12, ny + 10, lab, 1, GREY, bold=True)
        arrow = "\u25bc" if down else "\u25b2"
        acol = RED if down else (32, 120, 60)
        draw_text(cv, bx + 12, ny + 26, arrow, 2, acol)
        draw_text(cv, bx + 12 + 26, ny + 26, val, 2, INK, bold=True)

    # ---- the day in brief --------------------------------------------
    byy = 720
    draw_text(cv, MX, byy, "THE DAY IN BRIEF", 2, NAVY, bold=True)
    cv.rect(MX, byy + 22, CW, 2, NAVY)
    colw = (CW - 24) // 2
    for idx, (num, head) in enumerate(BRIEF):
        col = idx // 6
        row = idx % 6
        ix = MX + col * (colw + 24)
        iy = byy + 30 + row * 20
        draw_text(cv, ix, iy, "%2d" % num, 2, RED, bold=True)
        draw_text(cv, ix + 30, iy, head, 2, INK)

    # ---- also on this day --------------------------------------------
    ay = 868
    draw_text(cv, MX, ay, "ALSO ON THIS DAY", 2, NAVY, bold=True)
    draw_text(cv, MX + 250, ay + 2, "16 TO 48 - IN BRIEF", 1, GREY)
    cv.rect(MX, ay + 22, CW, 2, NAVY)
    acolw = CW // 3
    for idx, (num, item) in enumerate(ALSO):
        col = idx // 11
        row = idx % 11
        ix = MX + col * acolw
        iy = ay + 28 + row * 8
        draw_text(cv, ix, iy, "%d." % num, 1, RED, bold=True)
        draw_text(cv, ix + 24, iy, item, 1, INK)

    # ---- footer --------------------------------------------------------
    draw_centered(
        cv, W // 2, 998,
        "Sources: AP - Reuters - AFP - Al Jazeera - CBS News - Japan Times "
        "- OCHA - WHO - UN  |  All pictures drawn by this program  |  "
        "make.fun news-image-20261118",
        1, GREY)
    return cv


def main():
    cv = render()
    out = sys.argv[1] if len(sys.argv) > 1 else "entry.png"
    n = write_png(cv, out)
    print("wrote %s (%d bytes)" % (out, n))
    if os.path.isdir("/output"):
        n2 = write_png(cv, "/output/entry.png")
        print("wrote /output/entry.png (%d bytes)" % n2)


if __name__ == "__main__":
    main()
