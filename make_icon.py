#!/usr/bin/env python3
"""Generate a simple PNG icon (power bolt) for the PSU monitor, stdlib only."""
import struct
import zlib

W, H = 256, 256

# Palette: 0 = transparent, 1 = dark bg, 2 = green bolt, 3 = accent
# Simple RGB triples
PALETTE = [
    (0, 0, 0, 0),        # 0 transparent
    (13, 17, 23),        # 1 dark bg (#0d1117)
    (68, 210, 139),      # 2 green (#44d28b)
    (255, 255, 255),     # 3 white
]

def in_circle(x, y, cx, cy, r):
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

def in_rounded_rect(x, y, x0, y0, x1, y1, r):
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    # corner checks
    corners = [(x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)]
    cx, cy = min(max(x, x0 + r), x1 - r), min(max(y, y0 + r), y1 - r)
    if (x < x0 + r and y < y0 + r) or (x > x1 - r and y < y0 + r) or \
       (x < x0 + r and y > y1 - r) or (x > x1 - r and y > y1 - r):
        return in_circle(x, y, x0 + r, y0 + r, r) or in_circle(x, y, x1 - r, y0 + r, r) or \
               in_circle(x, y, x0 + r, y1 - r, r) or in_circle(x, y, x1 - r, y1 - r, r)
    return True

def point_in_poly(x, y, poly):
    """Ray casting."""
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside

# Lightning bolt polygon (drawn in 256x256 space, centered)
bolt = [
    (128, 30), (70, 140), (112, 140), (88, 226),
    (186, 110), (140, 110), (172, 30),
]

rows = []
for y in range(H):
    row = bytearray([0])
    for x in range(W):
        idx = 0
        if in_rounded_rect(x, y, 16, 16, 240, 240, 40):
            idx = 1
        if point_in_poly(x, y, bolt):
            idx = 2
        row.append(idx)
    rows.append(bytes(row))

raw = b"".join(rows)

def chunk(tag, data):
    c = struct.pack(">I", len(data)) + tag + data
    c += struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    return c

ihdr = struct.pack(">IIBBBBB", W, H, 8, 3, 0, 0, 0)  # 8-bit, palette
plte = b"".join(struct.pack("BBB", *c[:3]) for c in PALETTE)

png = b"\x89PNG\r\n\x1a\n"
png += chunk(b"IHDR", ihdr)
png += chunk(b"PLTE", plte)
png += chunk(b"tRNS", bytes([0]))  # palette index 0 fully transparent
png += chunk(b"IDAT", zlib.compress(raw, 9))
png += chunk(b"IEND", b"")

with open("icon.png", "wb") as f:
    f.write(png)
print("icon.png written:", len(png), "bytes")
