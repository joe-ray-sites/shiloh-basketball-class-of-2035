#!/usr/bin/env python3
"""Draw every play in PLAYS as a looping GIF and a static clipboard diagram.

    python3 make-plays.py            # all plays
    python3 make-plays.py pass-and-cut

Writes assets/plays/<slug>.gif (the animation the Plays tab shows) and
assets/plays/<slug>.png (the still diagram used on the play list).

Court coordinates are in feet on a half court seen from above, basket at the
top: x runs 0-50 across, y runs 0 (baseline) to 33 (just past the top of the
key). Offense is circled numbers, defense is squares with an X, and the ball
moves on its own: it rides with whoever has it and travels on passes.

A play is a start position for 1-5, who has the ball, a list of timed events
and the captions shown under the court:

    {"pass": (1, 2), "t": (0.8, 1.5)}                      ball from 1 to 2
    {"move": 1, "t": (1.6, 3.2), "path": [(x, y), ...]}    1 runs a path
    {"dribble": 2, "t": (...), "path": [...]}              2 dribbles a path
    {"shot": 2, "t": (a, b)}                               2 shoots; the ball drops in

"clear": [5.3] wipes the arrows drawn so far at 5.3 seconds, so a long play
reads in phases. "diagram_from": 5.3 draws the still diagram from that
moment (players where they stand then, only the arrows that follow).

Defenders are placed automatically by Pack Line rules: tight on the ball,
sagged inside the line off the ball, and they shift while the pass is in
the air. Set "defense": False to draw offense only.
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

# ── Plays ────────────────────────────────────────────────────────────────────
# Our five-out spots: 1 top, 2 left wing, 3 right wing, 4 left corner, 5 right corner.
FIVE_OUT = {1: (25, 29), 2: (6.5, 19.5), 3: (43.5, 19.5), 4: (3, 8), 5: (47, 8)}

PASS_AND_CUT = [
    {"pass": (1, 2), "t": (0.8, 1.45)},
    {"move": 1, "t": (1.6, 3.2), "path": [(25, 29), (24, 17), (24.5, 9)]},
    {"move": 3, "t": (1.9, 3.3), "path": [(43.5, 19.5), (36, 26.5), (25, 29)]},
    {"move": 5, "t": (2.2, 3.5), "path": [(47, 8), (46.5, 14), (43.5, 19.5)]},
    {"move": 1, "t": (3.4, 4.9), "path": [(24.5, 9), (31, 8), (40, 7.4), (47, 8)]},
]
PASS_AND_CUT_CAPTIONS = [
    (0.0, "1 has the ball at the top"),
    (0.8, "1 passes to 2"),
    (1.6, "1 cuts hard to the basket. 3 fills the top, 5 fills the wing"),
    (3.4, "1 flows out and fills the open corner"),
]

PLAYS = [
    {
        "slug": "pass-and-cut",
        "title": "Pass and Cut",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 6.8,
        "events": PASS_AND_CUT,
        "captions": PASS_AND_CUT_CAPTIONS + [
            (5.0, "Every spot is filled. Pass and cut again!"),
        ],
    },
    {
        # Pass and Cut, then: 2 dribbles at 3 (3 cuts, 4 fills the wing, 3 fills
        # the open corner), 2 passes to 5 and cuts, 5 dribbles up and hits 2
        # for the layup.
        "slug": "pass-and-cut-extended",
        "title": "Pass and Cut - Extended",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 12.6,
        "clear": [5.3],
        "diagram_from": 5.3,
        "events": PASS_AND_CUT + [
            {"dribble": 2, "t": (5.3, 6.9), "path": [(6.5, 19.5), (13, 25.5), (22.5, 28.6)]},
            {"move": 3, "t": (5.8, 7.3), "path": [(25, 29), (26.5, 18), (25.8, 9.5)]},
            {"move": 4, "t": (5.9, 7.3), "path": [(3, 8), (4, 14), (6.5, 19.5)]},
            {"pass": (2, 5), "t": (7.5, 8.1)},
            {"move": 3, "t": (7.6, 9.0), "path": [(25.8, 9.5), (17, 7.6), (9, 7.2), (3, 8)]},
            {"move": 2, "t": (8.2, 10.0), "path": [(22.5, 28.6), (21.5, 19), (22.5, 13), (24, 10)]},
            {"dribble": 5, "t": (8.4, 9.6), "path": [(43.5, 19.5), (37, 25), (31, 27.5)]},
            {"pass": (5, 2), "t": (9.6, 10.1)},
            {"move": 2, "t": (10.1, 10.5), "path": [(24, 10), (24.6, 7.8)]},
            {"shot": 2, "t": (10.4, 10.9)},
        ],
        "captions": PASS_AND_CUT_CAPTIONS + [
            (5.3, "2 dribbles at 3, so 3 cuts to the basket. 4 fills the wing"),
            (7.5, "2 passes to 5 and cuts. 3 fills the open corner"),
            (8.4, "5 dribbles up. 2 keeps cutting to the rim"),
            (9.6, "5 hits 2 for the layup!"),
        ],
    },
]

# ── Look ────────────────────────────────────────────────────────────────────
NAVY, ACCENT, RED = (7, 26, 46), (37, 150, 190), (216, 85, 63)
BOARD, BALL, SEAM = (255, 255, 255), (232, 121, 43), (110, 45, 10)
TRAIL = (7, 26, 46)
FPS = 20
SS = 2                      # draw at 2x, then shrink for smooth edges
PX = 12.8 * SS              # pixels per foot
PAD = 16 * SS
DEPTH = 33                  # feet of court shown below the baseline
CAP_H = 58 * SS
W = int(50 * PX + 2 * PAD)
COURT_H = int(DEPTH * PX + 2 * PAD)
H = COURT_H + CAP_H
BASKET = (25, 5.25)
PACK = 16                   # pack line, feet from the rim


def font(size, narrow=False):
    names = (["Arial Narrow Bold.ttf", "Arial Bold.ttf"] if narrow else ["Arial Bold.ttf"])
    for d in ["/System/Library/Fonts/Supplemental", "/Library/Fonts", "/usr/share/fonts/truetype/msttcorefonts"]:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_NUM = font(int(17 * SS))
F_CAP = font(int(21 * SS), narrow=True)
F_TAG = font(int(12 * SS), narrow=True)


def P(x, y):
    return (PAD + x * PX, PAD + y * PX)


# ── Geometry helpers ─────────────────────────────────────────────────────────
def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def smooth_path(pts, n=40):
    """Catmull-Rom through the points, so cuts curve like real runs."""
    if len(pts) < 3:
        return [lerp(pts[0], pts[-1], i / n) for i in range(n + 1)]
    out = []
    ext = [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t
                                     + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                     + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    out.append(pts[-1])
    return out


def along(path, t):
    """Point at fraction t of the path's length."""
    if t <= 0:
        return path[0]
    segs = [dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    total = sum(segs) or 1
    goal, run = t * total, 0
    for i, s in enumerate(segs):
        if run + s >= goal:
            return lerp(path[i], path[i + 1], (goal - run) / (s or 1))
        run += s
    return path[-1]


def upto(path, t):
    """The traveled part of the path, for drawing the trail."""
    if t >= 1:
        return list(path)
    segs = [dist(path[i], path[i + 1]) for i in range(len(path) - 1)]
    goal, run, out = t * (sum(segs) or 1), 0, [path[0]]
    for i, s in enumerate(segs):
        if run + s >= goal:
            out.append(lerp(path[i], path[i + 1], (goal - run) / (s or 1)))
            return out
        out.append(path[i + 1])
        run += s
    return out


# ── State at time t ──────────────────────────────────────────────────────────
def prepare(play):
    for e in play["events"]:
        if "path" in e:
            e["_path"] = smooth_path(e["path"])
    return play


def state_at(play, t):
    pos = dict(play["start"])
    holder, ball, air = play["ball"], None, 0.0
    trails = []                                   # (kind, points, done)
    cleared = max([c for c in play.get("clear", []) if c <= t], default=-1)
    shot = None
    bounce = 0.0
    for e in sorted(play["events"], key=lambda e: e["t"][0]):
        a, b = e["t"]
        if t < a:
            continue
        f = ease((t - a) / (b - a))
        done = t >= b
        if b <= cleared:                          # an earlier phase: apply it, don't draw it
            if "pass" in e:
                holder = e["pass"][1]
            elif "shot" in e:
                holder = None
            else:
                pos[e.get("move") or e.get("dribble")] = e["_path"][-1]
            continue
        if "shot" in e:
            src = hold_spot(pos[e["shot"]], BASKET)
            holder = None
            shot = BASKET if done else lerp(src, BASKET, f)
            air = 0.0 if done else 1.25 * math.sin(math.pi * f)
            continue
        if "dribble" in e and not done:
            bounce = 0.22 * abs(math.sin((t - a) * math.pi * 5))
        if "pass" in e:
            src, dst = e["pass"]
            s, d = hold_spot(pos[src], pos[dst]), hold_spot(pos[dst], pos[src])
            if done:
                holder = dst
                trails.append(("pass", [pos[src], pos[dst]], True))
            else:
                holder, ball, air = None, lerp(s, d, f), math.sin(math.pi * f)
                trails.append(("pass", [pos[src], lerp(pos[src], pos[dst], f)], False))
        else:
            who = e.get("move") or e.get("dribble")
            pos[who] = along(e["_path"], f)
            trails.append(("dribble" if "dribble" in e else "move", upto(e["_path"], f), done))
    if holder is not None:
        ball = hold_spot(pos[holder], BASKET)
        air = max(air, bounce)
    elif shot is not None:
        ball = shot
    return pos, ball, holder, air, trails


def hold_spot(me, toward):
    """Where the ball sits in a player's hands: on the side facing the play."""
    dx, dy = toward[0] - me[0], toward[1] - me[1]
    d = math.hypot(dx, dy) or 1
    return (me[0] + dx / d * 1.25 + 0.9, me[1] + dy / d * 1.25 + 0.4)


def defense_at(pos, ball):
    """Pack Line: pressure the ball, everyone else sags inside the line toward
    the ball. Weighted by distance to the ball so nothing jumps."""
    spots = {}
    for n, man in pos.items():
        w = max(0.0, 1 - dist(man, ball) / 7)            # 1 = he has it
        k = 0.36 - 0.22 * w                                # how far to sag
        tgt = lerp(man, BASKET, k)
        tgt = lerp(tgt, ball, 0.14 * (1 - w))              # shade to the ball
        if dist(tgt, BASKET) > PACK and w < 0.5:           # stay inside the pack line
            d = dist(tgt, BASKET)
            tgt = lerp(BASKET, tgt, (PACK + (d - PACK) * 0.35) / d)
        if dist(tgt, BASKET) < 2.6:                        # don't park on the rim: trail beside him
            side = 1 if man[0] <= BASKET[0] else -1
            tgt = (man[0] + 3.2 * side, man[1] + 1.2)
        v = (tgt[0] - man[0], tgt[1] - man[1])
        L = math.hypot(*v)
        if L < 3.2:                                        # never sit on top of him
            v = (ball[0] - man[0], ball[1] - man[1]) if L < 0.2 else v
            L2 = math.hypot(*v) or 1
            tgt = (man[0] + v[0] / L2 * 3.2, man[1] + v[1] / L2 * 3.2)
        spots[n] = tgt
    return spots


# ── Drawing ──────────────────────────────────────────────────────────────────
def dashed(d, pts, fill, width, dash=0.9, gap=0.7):
    pts = [P(*p) for p in pts]
    on, left = True, dash * PX
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = dist(a, b)
        pos = 0
        while pos < seg:
            step = min(left, seg - pos)
            p1, p2 = lerp(a, b, pos / seg), lerp(a, b, (pos + step) / seg)
            if on:
                d.line([p1, p2], fill=fill, width=width)
            pos += step
            left -= step
            if left <= 0:
                on = not on
                left = (dash if on else gap) * PX
    return


def arrowhead(d, a, b, fill, size=1.1):
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    tip = P(*b)
    s = size * PX
    pts = [tip,
           (tip[0] - s * math.cos(ang - 0.45), tip[1] - s * math.sin(ang - 0.45)),
           (tip[0] - s * math.cos(ang + 0.45), tip[1] - s * math.sin(ang + 0.45))]
    d.polygon(pts, fill=fill)


def trim(pts, start=0.0, end=0.0):
    """Shorten a path so arrows stop at the edge of a player, not his middle."""
    def cut(points, amount):
        out = list(points)
        while len(out) > 1 and amount > 0:
            seg = dist(out[0], out[1])
            if seg <= amount:
                amount -= seg
                out.pop(0)
            else:
                out[0] = lerp(out[0], out[1], amount / seg)
                amount = 0
        return out
    pts = cut(pts, start)
    return list(reversed(cut(list(reversed(pts)), end)))


def court(d):
    lw = int(2.2 * SS)
    d.rectangle([P(0, 0), P(50, DEPTH)], outline=NAVY, width=lw)
    d.rectangle([P(19, 0), P(31, 19)], outline=NAVY, width=lw)            # lane
    # free-throw circle: solid outside the lane, dashed inside
    cx, cy = P(25, 19)
    r = 6 * PX
    d.arc([cx - r, cy - r, cx + r, cy + r], 0, 180, fill=NAVY, width=lw)
    for k in range(9):
        a0, a1 = 180 + k * 20, 180 + k * 20 + 11
        d.arc([cx - r, cy - r, cx + r, cy + r], a0, a1, fill=NAVY, width=lw)
    # three-point line: straight corners, then the arc
    R = 19.75
    d.line([P(25 - R, 0), P(25 - R, BASKET[1])], fill=NAVY, width=lw)
    d.line([P(25 + R, 0), P(25 + R, BASKET[1])], fill=NAVY, width=lw)
    bx, by = P(*BASKET)
    rr = R * PX
    d.arc([bx - rr, by - rr, bx + rr, by + rr], 0, 180, fill=NAVY, width=lw)
    # backboard and rim
    d.line([P(22, 4), P(28, 4)], fill=NAVY, width=int(3 * SS))
    d.line([P(25, 4), P(25, 4.5)], fill=NAVY, width=lw)
    rim = 0.75 * PX
    d.ellipse([bx - rim, by - rim, bx + rim, by + rim], outline=NAVY, width=lw)


def offense(d, n, p, has_ball):
    x, y = P(*p)
    r = 1.55 * PX
    d.ellipse([x - r, y - r, x + r, y + r], fill=BOARD, outline=NAVY, width=int(3 * SS))
    if has_ball:
        r2 = r + 3 * SS
        d.ellipse([x - r2, y - r2, x + r2, y + r2], outline=ACCENT, width=int(2 * SS))
    d.text((x, y + SS), str(n), font=F_NUM, fill=NAVY, anchor="mm")


def defender(d, p):
    x, y = P(*p)
    s = 1.2 * PX
    d.rectangle([x - s, y - s, x + s, y + s], fill=BOARD, outline=RED, width=int(2.6 * SS))
    k = s * 0.55
    d.line([x - k, y - k, x + k, y + k], fill=RED, width=int(2.6 * SS))
    d.line([x - k, y + k, x + k, y - k], fill=RED, width=int(2.6 * SS))


def ball(d, p, air=0.0):
    x, y = P(*p)
    r = (0.78 + 0.22 * air) * PX
    if air > 0.05:                                     # a shadow while it's in the air
        sh = r * 0.9
        d.ellipse([x - sh + 4 * SS * air, y - sh + 6 * SS * air, x + sh + 4 * SS * air, y + sh + 6 * SS * air],
                  fill=(205, 212, 220))
    d.ellipse([x - r, y - r, x + r, y + r], fill=BALL, outline=SEAM, width=int(1.6 * SS))
    w = max(1, int(1.3 * SS))
    d.line([x - r, y, x + r, y], fill=SEAM, width=w)
    d.line([x, y - r, x, y + r], fill=SEAM, width=w)
    d.arc([x - r * 1.9, y - r, x - r * 0.1, y + r], -60, 60, fill=SEAM, width=w)
    d.arc([x + r * 0.1, y - r, x + r * 1.9, y + r], 120, 240, fill=SEAM, width=w)


def trail(d, kind, pts, done):
    if len(pts) < 2:
        return
    w = int(2.6 * SS)
    if kind == "pass":
        pts = trim(pts, 1.9, 2.2 if done else 0)
        if len(pts) < 2:
            return
        dashed(d, pts, ACCENT, w)
        if done:
            arrowhead(d, pts[-2], pts[-1], ACCENT)
        return
    pts = trim(pts, 1.8, 1.9 if done else 0)
    if len(pts) < 2:
        return
    if kind == "dribble":                              # zig-zag, the usual dribble mark
        total = sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        n = max(2, int(total / 0.85))
        zig = [pts[0]]
        for i in range(1, n):
            a, b = along(pts, (i - 0.01) / n), along(pts, i / n)
            ang = math.atan2(b[1] - a[1], b[0] - a[0]) + math.pi / 2
            o = 0.5 * (1 if i % 2 else -1)
            zig.append((b[0] + math.cos(ang) * o, b[1] + math.sin(ang) * o))
        zig.append(pts[-1])
        pts = zig
    d.line([P(*q) for q in pts], fill=TRAIL, width=w, joint="curve")
    if done:
        arrowhead(d, pts[-2], pts[-1], TRAIL)


def caption(d, play, t, total):
    top = COURT_H
    d.rectangle([0, top, W, H], fill=NAVY)
    caps = play["captions"]
    i = max(k for k, (start, _) in enumerate(caps) if t >= start)
    step = f"{i + 1}/{len(caps)}"
    sx = PAD
    bw = d.textlength(step, font=F_TAG) + 16 * SS
    d.rounded_rectangle([sx, top + 17 * SS, sx + bw, top + 41 * SS], radius=8 * SS, fill=ACCENT)
    d.text((sx + bw / 2, top + 29.5 * SS), step, font=F_TAG, fill=(255, 255, 255), anchor="mm")
    d.text((sx + bw + 12 * SS, top + 29 * SS), caps[i][1], font=F_CAP, fill=(255, 255, 255), anchor="lm")


def frame(play, t, diagram=False):
    img = Image.new("RGB", (W, H if not diagram else COURT_H), BOARD)
    d = ImageDraw.Draw(img)
    court(d)
    if diagram:                                        # everything at once, players at the start
        t0 = play.get("diagram_from", 0)
        pos, _, holder, _, _ = state_at(play, t0)
        holder = holder or play["ball"]
        late = dict(play, clear=list(play.get("clear", [])) + ([t0] if t0 else []))
        _, _, _, _, trails = state_at(late, play["length"])
        for tr in trails:
            trail(d, tr[0], tr[1], True)
        if play.get("defense", True):
            for p in defense_at(pos, hold_spot(pos[holder], BASKET)).values():
                defender(d, p)
        for n, p in pos.items():
            offense(d, n, p, n == holder)
        ball(d, hold_spot(pos[holder], BASKET))
    else:
        pos, bp, holder, air, trails = state_at(play, t)
        for tr in trails:
            trail(d, *tr)
        if play.get("defense", True):
            for p in defense_at(pos, bp).values():
                defender(d, p)
        for n, p in pos.items():
            offense(d, n, p, n == holder)
        ball(d, bp, air)
        caption(d, play, t, play["length"])
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


def build(play, out_dir):
    prepare(play)
    fps = play.get("fps", FPS)
    n = int(play["length"] * fps)
    frames = [frame(play, i / fps) for i in range(n)]
    # one shared palette so colors don't flicker from frame to frame
    sample = Image.new("RGB", (frames[0].width, frames[0].height * 4))
    for k, f in enumerate([frames[0], frames[n // 3], frames[2 * n // 3], frames[-1]]):
        sample.paste(f, (0, k * frames[0].height))
    pal = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    gif = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    path = os.path.join(out_dir, play["slug"] + ".gif")
    gif[0].save(path, save_all=True, append_images=gif[1:], duration=1000 // fps, loop=0, optimize=False)
    png = os.path.join(out_dir, play["slug"] + ".png")
    frame(play, 0, diagram=True).save(png, optimize=True)
    print(f"{play['slug']}: {n} frames, {os.path.getsize(path) // 1024} KB gif, {os.path.getsize(png) // 1024} KB png")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "plays")
    os.makedirs(out, exist_ok=True)
    want = set(sys.argv[1:])
    for p in PLAYS:
        if not want or p["slug"] in want:
            build(p, out)
