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
    {"move": 5, "screen": True, ...}                       a screen: the line ends in a T
    {"beat": 5, "t": (a, b)}                               5's defender is screened or
                                                           sealed: he's stuck, then catches up

"sag": 0.45 makes the defense play tighter on their men (under the basket on
inbounds plays) instead of sagging to the Pack Line. "reach": 4.5 keeps every
defender within that many feet of his man (sideline plays, far from the rim).

Out-of-bounds plays set "oob": 4.5 to show that many feet behind the
baseline (shaded), so the inbounder can stand off the court at y < 0.
Sideline plays set "oob_side": 4.5 instead: the strip runs down the left
sideline and the inbounder stands at x < 0. "depth": 53 shows more of the
floor (the hash marks at 28 feet, and the half-court line and center circle
at 47 once the view reaches them).

"clear": [5.3] wipes the arrows drawn so far at 5.3 seconds, so a long play
reads in phases. "diagram_from": 5.3 draws the still diagram from that
moment (players where they stand then, only the arrows that follow).
"diagram_until": 5.25 stops the still diagram's arrows there instead, so a
long play's card shows just its first phase.

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

# Layer 2 picks up where Pass and Cut ends: 2 dribbles at 3 (3 cuts, 4 fills
# the wing, 3 fills the open corner), then 2 passes to 5 and cuts.
DRIBBLE_AT = [
    {"dribble": 2, "t": (5.3, 6.9), "path": [(6.5, 19.5), (13, 25.5), (22.5, 28.6)]},
    {"move": 3, "t": (5.8, 7.3), "path": [(25, 29), (26.5, 18), (25.8, 9.5)]},
    {"move": 4, "t": (5.9, 7.3), "path": [(3, 8), (4, 14), (6.5, 19.5)]},
    {"pass": (2, 5), "t": (7.5, 8.1)},
    {"move": 3, "t": (7.6, 9.0), "path": [(25.8, 9.5), (17, 7.6), (9, 7.2), (3, 8)]},
]
DRIBBLE_AT_CAPTIONS = [
    (5.3, "2 dribbles at 3, so 3 cuts to the basket. 4 fills the wing"),
    (7.5, "2 passes to 5 and cuts. 3 fills the open corner"),
]

PLAYS = [
    {
        # Pass and Cut around the horn: 2 passes to 3, 3 to 5, and 5 to 4,
        # cutting each time while the open spots fill; 4 hits 5 on his cut.
        "slug": "pass-and-cut",
        "title": "Layer 1: Pass and Cut",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 17.6,
        "clear": [5.3, 9.2, 13.1],
        "diagram_until": 5.25,
        "events": PASS_AND_CUT + [
            {"pass": (2, 3), "t": (5.3, 5.9)},
            {"move": 2, "t": (6.0, 7.4), "path": [(6.5, 19.5), (13, 15), (20.5, 10.6), (24, 9)]},
            {"move": 4, "t": (6.3, 7.6), "path": [(3, 8), (4, 14), (6.5, 19.5)]},
            {"move": 2, "t": (7.4, 8.8), "path": [(24, 9), (17, 7.6), (9, 7.2), (3, 8)]},
            {"pass": (3, 5), "t": (9.2, 9.8)},
            {"move": 3, "t": (9.9, 11.3), "path": [(25, 29), (25.5, 17), (25, 9)]},
            {"move": 4, "t": (10.2, 11.6), "path": [(6.5, 19.5), (14, 26.5), (25, 29)]},
            {"move": 2, "t": (10.5, 11.8), "path": [(3, 8), (4, 14), (6.5, 19.5)]},
            {"move": 3, "t": (11.3, 12.7), "path": [(25, 9), (17, 7.6), (9, 7.2), (3, 8)]},
            {"pass": (5, 4), "t": (13.1, 13.7)},
            {"move": 5, "t": (13.8, 15.2), "path": [(43.5, 19.5), (37, 14.5), (29.5, 10.2), (25.6, 8.8)]},
            {"beat": 5, "t": (13.8, 16.4)},
            {"pass": (4, 5), "t": (14.5, 14.9)},              # hit him in stride
            {"move": 5, "t": (15.2, 15.5), "path": [(25.6, 8.8), (24.8, 7.6)]},
            {"shot": 5, "t": (15.4, 15.9)},
        ],
        "captions": PASS_AND_CUT_CAPTIONS + [
            (5.3, "2 passes to 3 and cuts. 4 fills the wing"),
            (7.4, "2 flows out and fills the open corner"),
            (9.2, "3 passes to 5 and cuts. 4 fills the top, 2 fills the wing"),
            (11.3, "3 flows out and fills the open corner"),
            (13.1, "5 passes to 4 and cuts to the basket"),
            (14.5, "4 hits 5 in stride"),
            (15.4, "5 makes the layup!"),
        ],
    },
    {
        # Pass and Cut, then the dribble at; 5 dribbles up and hits 2 for the
        # layup.
        "slug": "pass-and-cut-extended",
        "title": "Layer 2: Pass and Cut + Dribble At",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 12.6,
        "clear": [5.3],
        "diagram_from": 5.3,
        "events": PASS_AND_CUT + DRIBBLE_AT + [
            {"move": 2, "t": (8.2, 10.0), "path": [(22.5, 28.6), (21.5, 19), (22.5, 13), (24, 10)]},
            {"dribble": 5, "t": (8.4, 9.6), "path": [(43.5, 19.5), (37, 25), (31, 27.5)]},
            {"pass": (5, 2), "t": (9.6, 10.1)},
            {"move": 2, "t": (10.1, 10.5), "path": [(24, 10), (24.6, 7.8)]},
            {"shot": 2, "t": (10.4, 10.9)},
        ],
        "captions": PASS_AND_CUT_CAPTIONS + DRIBBLE_AT_CAPTIONS + [
            (8.4, "5 dribbles up. 2 keeps cutting to the rim"),
            (9.6, "5 hits 2 for the layup!"),
        ],
    },
    {
        # Layer 2, but 2's cut ends on the low block: 5 passes in to him, makes
        # a Laker cut and gets it back for the layup.
        "slug": "pass-and-cut-layer-3",
        "title": "Layer 3: Pass and Cut + Dribble At + Laker Cut",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 14.8,
        "clear": [5.3, 10.4],
        "diagram_from": 10.35,                        # 5 still has it (the pass leaves at 10.4)
        "events": PASS_AND_CUT + DRIBBLE_AT + [
            {"move": 2, "t": (8.2, 10.2), "path": [(22.5, 28.6), (21.5, 19), (23.5, 12.5), (27.8, 9.6), (31.3, 8.6)]},
            {"dribble": 5, "t": (8.4, 9.6), "path": [(43.5, 19.5), (37, 25), (31, 27.5)]},
            {"pass": (5, 2), "t": (10.4, 10.9)},
            {"move": 5, "t": (11.1, 12.3), "path": [(31, 27.5), (27.8, 19), (25.6, 12.2), (24.8, 9.6)]},
            {"beat": 5, "t": (11.1, 13.4)},
            {"pass": (2, 5), "t": (11.7, 12.1)},              # hit him in stride
            {"move": 5, "t": (12.3, 12.6), "path": [(24.8, 9.6), (24.6, 7.8)]},
            {"shot": 5, "t": (12.5, 13.0)},
        ],
        "captions": PASS_AND_CUT_CAPTIONS + DRIBBLE_AT_CAPTIONS + [
            (8.4, "5 dribbles up. 2 cuts through to the low block"),
            (10.4, "5 passes in to 2 on the block"),
            (11.1, "5 makes a Laker cut. 2 hits him in stride"),
            (12.3, "5 makes the layup!"),
        ],
    },
    {
        # Pass and Cut start, but 1 stops his cut in the paint and flashes to
        # the ball-side elbow (left end of the free-throw line); 2 passes to
        # him, makes the Laker cut (4 fills his wing spot) and gets it back
        # for the layup.
        "slug": "laker-cut",
        "title": "Laker Cut",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 8.6,
        "events": [
            PASS_AND_CUT[0],                                   # 1 passes to 2
            {"move": 1, "t": (1.6, 3.0), "path": [(25, 29), (23.8, 18.5), (23.5, 12.5)]},
            PASS_AND_CUT[2],                                   # 3 fills the top
            PASS_AND_CUT[3],                                   # 5 fills the wing
            {"move": 1, "t": (3.0, 3.9), "path": [(23.5, 12.5), (19.8, 14.8), (19.3, 19.8)]},
            {"pass": (2, 1), "t": (4.0, 4.6)},
            {"move": 2, "t": (4.9, 6.1), "path": [(6.5, 19.5), (12, 13.5), (19, 9.6), (23.8, 9.2)]},
            {"move": 4, "t": (5.1, 6.4), "path": [(3, 8), (4, 14), (6.5, 19.5)]},
            {"pass": (1, 2), "t": (5.2, 5.6)},                # hit him in stride, mid-cut
            {"move": 2, "t": (6.1, 6.4), "path": [(23.8, 9.2), (24.5, 7.8)]},
            {"shot": 2, "t": (6.3, 6.8)},
        ],
        "captions": [
            (0.0, "1 has the ball at the top"),
            (0.8, "1 passes to 2"),
            (1.6, "1 cuts into the paint. 3 fills the top, 5 fills the wing"),
            (3.0, "1 flashes up to the elbow"),
            (4.0, "2 passes to 1 at the elbow"),
            (4.9, "2 cuts, 1 hits him in stride. 4 fills the wing"),
            (6.1, "2 makes the layup!"),
        ],
    },
    # ── Baseline out of bounds (BLOB) ───────────────────────────────────────
    {
        # Don Kelbick's "Line Under" (Breakthrough Basketball): 4 cuts up the
        # lane and catches over the top, 5 seals and ducks in, 4 hits 5.
        "slug": "line-under",
        "title": "Line Under",
        "oob": 4.5,
        "sag": 0.45,
        "start": {2: (33, -2.2), 4: (32, 7.5), 5: (18, 7.5), 1: (3, 3.5), 3: (47, 3.5)},
        "ball": 2,
        "length": 6.8,
        "events": [
            {"move": 4, "t": (1.0, 2.3), "path": [(32, 7.5), (29.5, 13), (26.5, 18.5)]},
            {"pass": (2, 4), "t": (2.1, 2.7)},
            {"move": 5, "t": (2.9, 3.6), "path": [(18, 7.5), (20.5, 7.2), (22.8, 8.2)]},
            {"beat": 5, "t": (2.9, 5.0)},
            {"move": 2, "t": (2.9, 3.7), "path": [(33, -2.2), (34.5, 2), (36, 4.2)]},
            {"pass": (4, 5), "t": (3.7, 4.2)},
            {"move": 5, "t": (4.2, 4.5), "path": [(22.8, 8.2), (23.8, 7.1)]},
            {"shot": 5, "t": (4.4, 4.9)},
        ],
        "captions": [
            (0.0, "2 takes it out. 4 and 5 on the blocks, 1 and 3 deep in the corners"),
            (1.0, "4 cuts straight up the lane"),
            (2.1, "2 passes over the top to 4"),
            (2.9, "5 seals his man and ducks in. 2 steps in"),
            (3.7, "4 hits 5 for the layup!"),
        ],
    },
    {
        # Breakthrough Basketball's Box Set 4 ("Up Screener"), the classic
        # screen the screener: 5 up-screens for 3, 4 screens for 5, 5 dives.
        "slug": "box-up-screener",
        "title": "Box: Screen the Screener",
        "oob": 4.5,
        "sag": 0.45,
        "start": {2: (33, -2.2), 5: (31.8, 8), 4: (18.2, 8), 3: (31.5, 19), 1: (18.5, 19)},
        "ball": 2,
        "length": 7.6,
        "events": [
            {"move": 5, "screen": True, "t": (1.0, 1.8), "path": [(31.8, 8), (31.3, 12), (30.8, 15.2)]},
            {"move": 3, "t": (1.8, 2.9), "path": [(31.5, 19), (28.6, 12.5), (26, 8.8)]},
            {"move": 3, "t": (2.9, 4.0), "path": [(26, 8.8), (30.5, 5.2), (40, 4.5), (46.5, 5.5)]},
            {"move": 4, "screen": True, "t": (2.4, 3.2), "path": [(18.2, 8), (23, 10.8), (28, 13.4)]},
            {"move": 5, "t": (3.1, 4.4), "path": [(30.8, 15.2), (27.2, 17.6), (23.2, 12.6), (24.2, 8.2)]},
            {"beat": 5, "t": (3.1, 5.7)},
            {"move": 1, "t": (3.4, 4.6), "path": [(18.5, 19), (27, 24.5), (36, 22.5)]},
            {"move": 4, "t": (3.6, 4.7), "path": [(28, 13.4), (30.8, 10.4), (32, 8)]},
            {"pass": (2, 5), "t": (4.4, 4.9)},
            {"move": 5, "t": (4.9, 5.2), "path": [(24.2, 8.2), (24.6, 7.2)]},
            {"shot": 5, "t": (5.1, 5.6)},
        ],
        "captions": [
            (0.0, "2 takes it out. Box: 4 and 5 on the blocks, 1 and 3 on the elbows"),
            (1.0, "5 sets an up screen for 3"),
            (1.8, "3 cuts to the rim. If he's covered, he clears to the corner"),
            (2.6, "4 screens the screener. 5 cuts to the basket"),
            (3.6, "1 is the safety outlet. 4 dives to the block"),
            (4.4, "2 hits 5 for the layup!"),
        ],
    },
    # ── Sideline out of bounds (SLOB) ───────────────────────────────────────
    {
        # Breakthrough Basketball's Stack SLOB, flipped to the left sideline:
        # 1 pops to the ball, dribbles away while 5 posts the open side, and 4
        # and 2 screen down for 3 as the second option.
        "slug": "slob-stack",
        "title": "Stack",
        "oob_side": 4.5,
        "depth": 38,
        "sag": 0.45,
        "reach": 4.5,
        "start": {4: (-2.2, 28), 3: (11.5, 28), 1: (15.3, 28), 2: (19.1, 28), 5: (22.9, 28)},
        "ball": 4,
        "length": 8.0,
        "events": [
            {"move": 1, "t": (1.0, 1.9), "path": [(15.3, 28), (12, 31), (6.5, 33.5)]},
            {"beat": 1, "t": (1.0, 2.6)},
            {"move": 3, "t": (1.0, 2.0), "path": [(11.5, 28), (8, 24), (5, 19.5)]},
            {"move": 2, "t": (1.2, 2.1), "path": [(19.1, 28), (16.5, 31), (13, 32.5)]},
            {"move": 5, "t": (1.1, 2.2), "path": [(22.9, 28), (30, 24.5), (37, 22.5)]},
            {"pass": (4, 1), "t": (2.0, 2.5)},
            {"dribble": 1, "t": (2.8, 4.6), "path": [(6.5, 33.5), (18, 33), (29, 30.5), (36.5, 26.5)]},
            {"move": 4, "screen": True, "t": (2.8, 3.7), "path": [(-2.2, 28), (2.5, 28), (6, 24.6)]},
            {"move": 2, "screen": True, "t": (2.8, 3.7), "path": [(13, 32.5), (11.5, 28), (9.6, 24.6)]},
            {"move": 5, "t": (3.7, 4.6), "path": [(37, 22.5), (35.5, 15), (31.8, 8.6)]},
            {"beat": 5, "t": (3.7, 6.6)},
            {"move": 3, "t": (3.8, 4.8), "path": [(5, 19.5), (9.5, 20.8), (13.5, 24.5), (15.5, 29.5)]},
            {"beat": 3, "t": (3.8, 5.6)},
            {"pass": (1, 5), "t": (4.8, 5.3)},
            {"move": 5, "t": (5.3, 5.6), "path": [(31.8, 8.6), (29.6, 7.0)]},
            {"shot": 5, "t": (5.5, 6.0)},
        ],
        "captions": [
            (0.0, "4 takes it out. 3, 1, 2 and 5 stack across from him"),
            (1.0, "1 cuts hard to the ball. 3 breaks to the wing"),
            (2.0, "4 passes in to 1. 5 floats away"),
            (2.8, "1 dribbles away. 4 and 2 screen down for 3"),
            (3.7, "5 cuts hard to the block. 3 comes off the screens"),
            (4.8, "1 hits 5 on the block for the layup!"),
        ],
    },
    {
        # Coach's Clipboard "Pairs": two screening pairs. 4 screens for 2,
        # who comes over the top for the catch; 5 screens for 1, the safety.
        # 4 seals after his screen and 2 hits him on the block.
        "slug": "slob-pairs",
        "title": "Pairs",
        "oob_side": 4.5,
        "depth": 53,
        "sag": 0.45,
        "reach": 4.5,
        "start": {3: (-2.2, 46), 4: (16.5, 12.5), 2: (33, 8), 1: (18, 39), 5: (20, 44)},
        "ball": 3,
        "length": 7.6,
        "events": [
            {"move": 4, "screen": True, "t": (1.0, 1.8), "path": [(16.5, 12.5), (22, 12.3), (27.4, 11.6)]},
            {"move": 5, "screen": True, "t": (1.0, 1.6), "path": [(20, 44), (20.3, 42.6), (20.6, 41.5)]},
            {"move": 2, "t": (1.8, 3.0), "path": [(33, 8), (31.2, 13.8), (23, 16.4), (12, 18.2), (5.5, 20.5)]},
            {"beat": 2, "t": (1.8, 3.8)},
            {"move": 1, "t": (1.8, 2.9), "path": [(18, 39), (23, 41.5), (23.5, 46), (22, 50.5)]},
            {"pass": (3, 2), "t": (3.0, 3.7)},
            {"move": 4, "t": (3.4, 4.3), "path": [(27.4, 11.6), (23, 8.8), (18.2, 8)]},
            {"beat": 4, "t": (3.4, 6.6)},
            {"move": 3, "t": (3.7, 4.6), "path": [(-2.2, 46), (3, 42), (7, 38)]},
            {"move": 5, "t": (3.7, 4.7), "path": [(20.6, 41.5), (22, 36), (24, 31)]},
            {"move": 1, "t": (3.7, 4.7), "path": [(22, 50.5), (28, 47), (33, 42)]},
            {"pass": (2, 4), "t": (4.6, 5.1)},
            {"move": 4, "t": (5.1, 5.4), "path": [(18.2, 8), (21, 6.6)]},
            {"shot": 4, "t": (5.3, 5.8)},
        ],
        "captions": [
            (0.0, "3 takes it out at half court. 4 and 2 low, 5 and 1 high"),
            (1.0, "4 screens for 2. 5 screens for 1"),
            (1.8, "2 comes over the top to the wing. 1 is the safety"),
            (3.0, "3 passes in to 2"),
            (3.7, "4 seals his man and posts up. 5 pops to the top"),
            (4.6, "2 hits 4 on the block for the layup!"),
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
VIEW = DEPTH                # feet shown for this play (set per play)
TOP_FT = 0                  # feet shown behind the baseline (set per play)
LEFT_FT = 0                 # feet shown outside the left sideline (set per play)
W = int(50 * PX + 2 * PAD)
COURT_H = int(DEPTH * PX + 2 * PAD)
H = COURT_H + CAP_H


def set_view(play):
    global VIEW, TOP_FT, LEFT_FT, W, COURT_H, H
    VIEW = play.get("depth", DEPTH)
    TOP_FT = play.get("oob", 0)
    LEFT_FT = play.get("oob_side", 0)
    W = int((50 + LEFT_FT) * PX + 2 * PAD)
    COURT_H = int((VIEW + TOP_FT) * PX + 2 * PAD)
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
    return (PAD + (x + LEFT_FT) * PX, PAD + (y + TOP_FT) * PX)


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
        if "beat" in e:
            continue
        if b <= cleared:                          # an earlier phase: apply it, don't draw it
            if "pass" in e:
                holder = e["pass"][1]
            elif "shot" in e:
                holder = None
            else:
                pos[e.get("move") or e.get("dribble")] = e["_path"][-1]
            continue
        if "beat" in e:
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
            kind = "dribble" if "dribble" in e else "screen" if e.get("screen") else "move"
            trails.append((kind, upto(e["_path"], f), done))
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


def defense_for(play, t, pos, ball):
    """Pack Line spots, then hold back any defender who's been screened."""
    sag = play.get("sag", 1.0)
    spots = defense_at(pos, ball, sag, play.get("reach"))
    for e in play["events"]:
        if "beat" not in e:
            continue
        a, b = e["t"]
        if a <= t < b:
            p0, b0, _, _, _ = state_at(play, a)
            stuck = defense_at(p0, b0, sag, play.get("reach"))[e["beat"]]
            g = ((t - a) / (b - a)) ** 3
            spots[e["beat"]] = lerp(stuck, spots[e["beat"]], g)
    return keep_apart(spots, pos)


def defense_at(pos, ball, sag=1.0, reach=None):
    """Pack Line: pressure the ball, everyone else sags inside the line toward
    the ball. Weighted by distance to the ball so nothing jumps."""
    spots = {}
    for n, man in pos.items():
        w = max(0.0, 1 - dist(man, ball) / 7)            # 1 = he has it
        k = (0.36 - 0.22 * w) * sag                        # how far to sag
        tgt = lerp(man, BASKET, k)
        tgt = lerp(tgt, ball, 0.14 * (1 - w))              # shade to the ball
        if reach and dist(tgt, man) > reach:               # don't play off him too far
            tgt = lerp(man, tgt, reach / dist(tgt, man))
        if sag >= 1 and dist(tgt, BASKET) > PACK and w < 0.5:   # stay inside the pack line
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
    return keep_apart(spots, pos)


def keep_apart(spots, pos, gap_off=3.1, gap_def=2.7):
    """Nudge defenders so no square sits on a circle or on another square."""
    spots = dict(spots)
    for _ in range(4):
        for n, d in spots.items():
            x, y = d
            for p in pos.values():
                dd = dist((x, y), p)
                if dd < gap_off:
                    vx, vy = (x - p[0], y - p[1]) if dd > 0.05 else (BASKET[0] - p[0], BASKET[1] - p[1])
                    L = math.hypot(vx, vy) or 1
                    x, y = p[0] + vx / L * gap_off, p[1] + vy / L * gap_off
            for m, o in spots.items():
                if m == n:
                    continue
                dd = dist((x, y), o)
                if dd < gap_def:
                    vx, vy = (x - o[0], y - o[1]) if dd > 0.05 else (1, 0)
                    L = math.hypot(vx, vy) or 1
                    push = (gap_def - dd) / 2
                    x, y = x + vx / L * push, y + vy / L * push
            spots[n] = (min(48.6, max(1.4, x)), min(VIEW - 1.4, max(1.0, y)))
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
    if TOP_FT:                                         # out of bounds behind the baseline
        d.rectangle([P(0, -TOP_FT), P(50, 0)], fill=(236, 240, 244))
        d.text((P(1.2, -TOP_FT / 2)[0], P(0, -TOP_FT / 2)[1]), "OUT OF BOUNDS", font=F_TAG,
               fill=(140, 152, 166), anchor="lm")
    if LEFT_FT:                                        # out of bounds past the left sideline
        d.rectangle([P(-LEFT_FT, 0), P(0, VIEW)], fill=(236, 240, 244))
        tag = Image.new("L", (int(d.textlength("OUT OF BOUNDS", font=F_TAG)) + 4, int(16 * SS)), 0)
        ImageDraw.Draw(tag).text((2, tag.height / 2), "OUT OF BOUNDS", font=F_TAG, fill=255, anchor="lm")
        tag = tag.rotate(90, expand=True)
        x0, _ = P(-LEFT_FT / 2, 0)
        d.bitmap((int(x0 - tag.width / 2), int(P(0, VIEW)[1] - tag.height - 1.2 * PX)), tag, fill=(140, 152, 166))
    d.rectangle([P(0, 0), P(50, VIEW)], outline=NAVY, width=lw)
    if VIEW > DEPTH:                                   # hash marks, 28 feet from the baseline
        for x0, x1 in ((0, 3), (47, 50)):
            d.line([P(x0, 28), P(x1, 28)], fill=NAVY, width=lw)
    if VIEW > 47:                                      # half-court line and the center circle
        d.line([P(0, 47), P(50, 47)], fill=NAVY, width=lw)
        cx, cy = P(25, 47)
        r = 6 * PX
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=NAVY, width=lw)
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
    if done and kind == "screen":                      # the screen mark: a T across the end
        a, b = pts[-2], pts[-1]
        ang = math.atan2(b[1] - a[1], b[0] - a[0]) + math.pi / 2
        k = 1.0
        d.line([P(b[0] + math.cos(ang) * k, b[1] + math.sin(ang) * k),
                P(b[0] - math.cos(ang) * k, b[1] - math.sin(ang) * k)], fill=TRAIL, width=int(3.4 * SS))
    elif done:
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
        _, _, _, _, trails = state_at(late, play.get("diagram_until", play["length"]))
        for tr in trails:
            trail(d, tr[0], tr[1], True)
        if play.get("defense", True):
            for p in defense_at(pos, hold_spot(pos[holder], BASKET), play.get("sag", 1.0), play.get("reach")).values():
                defender(d, p)
        for n, p in pos.items():
            offense(d, n, p, n == holder)
        ball(d, hold_spot(pos[holder], BASKET))
    else:
        pos, bp, holder, air, trails = state_at(play, t)
        for tr in trails:
            trail(d, *tr)
        if play.get("defense", True):
            for p in defense_for(play, t, pos, bp).values():
                defender(d, p)
        for n, p in pos.items():
            offense(d, n, p, n == holder)
        ball(d, bp, air)
        caption(d, play, t, play["length"])
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


def build(play, out_dir):
    set_view(play)
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
