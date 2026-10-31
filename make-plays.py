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
    {"guard": 3, "t": (a, b), "at": (x, y)}                3's defender leaves to help (or
                                                           sinks into the lane) at (x, y), then
                                                           recovers late ("recover": seconds)

"sag": 0.45 makes the defense play tighter on their men (under the basket on
inbounds plays) instead of sagging to the Pack Line. "reach": 4.5 keeps every
defender within that many feet of his man (sideline plays, far from the rim).

Out-of-bounds plays set "oob": 4.5 to show that many feet behind the
baseline (shaded), so the inbounder can stand off the court at y < 0.
Sideline plays set "oob_side": 4.5 instead: the strip runs down the left
sideline and the inbounder stands at x < 0. "depth": 53 shows more of the
floor (the hash marks at 28 feet, and the half-court line and center circle
at 47 once the view reaches them).

"press": True plays full-court man pressure instead (deny every pass, the
ball handler's man in front of him until he gets by), and "toward": (x, y)
is where players hold the ball facing (default: the basket).

Full-court transition plays set "depth": 94 and "hoop": (25, 88.75) to attack
the far basket, and "chase": {"from": {1: (x, y), ...}, "speed": 14} to start
the defenders where they were and let them run back at that many feet per
second, so our runners can beat them down the floor. "delay": 0.8 (or
{5: 0.3, ...} per defender) is how long they stand watching the shot first.

"pack": True places the defense by our Pack Line rules instead, by how many
passes away each man is: pressure the ball and force it to the side, one
pass away sit in the gap inside the line, two passes away sink to the
middle, and stay between a cutter and the ball. "us_on_defense": True draws
it from our side: we're the numbered circles on defense (tagged with the
job each has right now) and the offense is the squares; "show_pack" draws
the pack line, and "trail" colors the offense's arrows.

"slow": 1.15 plays the GIF 15% slower, and "hold_after_pass": 1.0 freezes the
picture for that many seconds just after every catch, so players can study
where everyone is.

"parts": [{...}, {...}] plays several short possessions back to back in one
GIF, each with its own start, ball, length, events and captions (anything
not given comes from the play). The card diagram shows the first part.

"clear": [5.3] wipes the arrows drawn so far at 5.3 seconds, so a long play
reads in phases. "diagram_from": 5.3 draws the still diagram from that
moment (players where they stand then, only the arrows that follow).
"diagram_until": 5.25 stops the still diagram's arrows there instead, so a
long play's card shows just its first phase.

Defenders are placed automatically by Pack Line rules: tight on the ball,
sagged inside the line off the ball, and they shift while the pass is in
the air. Set "defense": False to draw offense only.
"""
import io
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageSequence

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

# Layer 3 (Dribble At) picks up where Pass and Cut ends: 2 dribbles at 3 (3 cuts, 4 fills
# the wing, 3 fills the open corner), then 2 passes to 5 and cuts.
DRIBBLE_AT = [
    {"dribble": 2, "t": (5.3, 6.9), "path": [(6.5, 19.5), (13, 25.5), (22.5, 28.6)]},
    {"move": 3, "t": (5.8, 7.3), "path": [(25, 29), (26.5, 18), (25.8, 9.5)]},
    {"move": 4, "t": (5.9, 7.3), "path": [(3, 8), (4, 14), (6.5, 19.5)]},
    {"pass": (2, 5), "t": (7.5, 8.1)},
    {"move": 3, "t": (7.6, 9.0), "path": [(25.8, 9.5), (17, 7.6), (9, 7.2), (3, 8)]},
]
# Layer 3's finish: 2 cuts, 5 dribbles up and hits him.
LAYER_2_HIT = [
    {"move": 2, "t": (8.2, 10.0), "path": [(22.5, 28.6), (21.5, 19), (22.5, 13), (24, 10)]},
    {"dribble": 5, "t": (8.4, 9.6), "path": [(43.5, 19.5), (37, 25), (31, 27.5)]},
    {"pass": (5, 2), "t": (9.6, 10.1)},
]
# Layers 1-3's middle: 2 cuts through to the block and 5 passes in to him.
LAYER_3_POST = [
    {"move": 2, "t": (8.2, 10.2), "path": [(22.5, 28.6), (21.5, 19), (23.5, 12.5), (27.8, 9.6), (31.3, 8.6)]},
    {"dribble": 5, "t": (8.4, 9.6), "path": [(43.5, 19.5), (37, 25), (31, 27.5)]},
    {"pass": (5, 2), "t": (10.4, 10.9)},
]
LAYER_3_CAPTIONS = [
    (8.4, "5 dribbles up. 2 cuts through to the low block"),
    (10.4, "5 passes in to 2 on the block"),
]
DRIBBLE_AT_CAPTIONS = [
    (5.3, "2 dribbles at 3, so 3 cuts to the basket. 4 fills the wing"),
    (7.5, "2 passes to 5 and cuts. 3 fills the open corner"),
]

# Press break opening, shared by both press breaks: 2 screens for 3, 3 cuts
# left, 2 pops right, and 1 inbounds to 2 on the wide side.
PRESS_START = {1: (30, -2.2), 2: (19.5, 16), 3: (26, 22.5), 4: (5, 42), 5: (45, 42)}
PRESS_INBOUND = [
    {"move": 2, "screen": True, "t": (0.8, 1.5), "path": [(19.5, 16), (22, 18.2), (24, 19.5)]},
    {"move": 3, "t": (1.5, 2.7), "path": [(26, 22.5), (21, 22.8), (13, 17.5), (6.5, 12)]},
    {"beat": 3, "t": (1.5, 3.4)},
    {"move": 2, "t": (1.7, 2.8), "path": [(24, 19.5), (32, 17), (44, 12)]},
    {"pass": (1, 2), "t": (2.8, 3.4)},
]
PRESS_CAPTIONS = [
    (0.0, "We're pressed. 1 takes it out, 2 and 3 stack, 4 and 5 deep"),
    (0.8, "2 screens for 3. 3 cuts left, 2 pops to the right"),
    (2.8, "1 inbounds to 2, to the wide side"),
]

# Race & Space off a miss: the opening both rebound plays share. 4 rebounds
# and outlets to 1, everyone races, and 1 throws it ahead to 3.
RS_REBOUND_START = {4: (22, 6.5), 5: (29.5, 8.5), 1: (31, 24), 2: (10, 17), 3: (40, 17)}
RS_REBOUND_CHASE = {"from": {4: (20.5, 10.5), 5: (27, 44), 1: (26, 27), 2: (8, 21), 3: (43, 21.5)},
                    "speed": 11, "delay": {4: 0.8, 1: 0.7, 2: 0.7, 3: 0.7, 5: 0.3}}
RS_REBOUND = [
    {"move": 1, "t": (0.3, 1.0), "path": [(31, 24), (37, 23), (42, 24)]},
    {"pass": (4, 1), "t": (0.9, 1.4)},
    {"move": 5, "t": (0.5, 4.4), "path": [(29.5, 8.5), (27, 30), (24, 60), (21, 82), (19.5, 86.5)]},
    {"move": 3, "t": (0.6, 3.3), "path": [(40, 17), (45, 38), (46, 58), (44.5, 71)]},
    {"move": 2, "t": (0.6, 4.4), "path": [(10, 17), (5, 45), (4, 74), (3, 86)]},
    {"dribble": 1, "t": (1.5, 3.0), "path": [(42, 24), (37, 38), (32.5, 51)]},
    {"pass": (1, 3), "t": (3.0, 3.6)},
    {"move": 1, "t": (3.6, 5.2), "path": [(32.5, 51), (35, 56), (38.5, 60)]},
]
RS_REBOUND_CAPTIONS = [
    (0.0, "Off a miss: 4 grabs the rebound. Everybody races"),
    (0.9, "4 outlets to 1, quick. 5 sprints rim to rim"),
    (1.6, "2 and 3 sprint the lanes to the corners. 4 trails"),
    (3.0, "1 throws it ahead to 3, up the street"),
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
        "title": "Layer 3: Pass and Cut + Dribble At",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 12.6,
        "clear": [5.3],
        "diagram_from": 5.3,
        "events": PASS_AND_CUT + DRIBBLE_AT + LAYER_2_HIT + [
            {"move": 2, "t": (10.1, 10.5), "path": [(24, 10), (24.6, 7.8)]},
            {"shot": 2, "t": (10.4, 10.9)},
        ],
        "captions": PASS_AND_CUT_CAPTIONS + DRIBBLE_AT_CAPTIONS + [
            (8.4, "5 dribbles up. 2 keeps cutting to the rim"),
            (9.6, "5 hits 2 for the layup!"),
        ],
    },
    {
        # Layer 3, but 1's man steps in to stop 2's layup, so 2 kicks it out
        # to 1 in the corner for the 3.
        "slug": "layer-2-alt-3",
        "title": "Layer 3 Alternate: 3 Point Shot",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 13.8,
        "clear": [5.3],
        "diagram_from": 5.3,
        "events": PASS_AND_CUT + DRIBBLE_AT + LAYER_2_HIT + [
            {"guard": 1, "t": (9.4, 10.6), "at": (29, 6.3), "recover": 1.4},
            {"pass": (2, 1), "t": (10.6, 11.2)},
            {"shot": 1, "t": (11.5, 12.2)},
        ],
        "captions": PASS_AND_CUT_CAPTIONS + DRIBBLE_AT_CAPTIONS + [
            (8.4, "5 dribbles up. 2 keeps cutting to the rim"),
            (9.6, "5 hits 2. 1's man steps in to stop the layup"),
            (10.6, "2 kicks it out to 1 in the corner"),
            (11.5, "1 knocks down the 3!"),
        ],
    },
    {
        # Layer 3, but 2's cut ends on the low block: 5 passes in to him, makes
        # a Laker cut and gets it back for the layup.
        "slug": "pass-and-cut-layer-3",
        "title": "Layers 1-3: Pass and Cut + Dribble At + Laker Cut",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 14.8,
        "clear": [5.3, 10.4],
        "diagram_from": 10.35,                        # 5 still has it (the pass leaves at 10.4)
        "events": PASS_AND_CUT + DRIBBLE_AT + LAYER_3_POST + [
            {"move": 5, "t": (11.1, 12.3), "path": [(31, 27.5), (27.8, 19), (25.6, 12.2), (24.8, 9.6)]},
            {"beat": 5, "t": (11.1, 13.4)},
            {"pass": (2, 5), "t": (11.7, 12.1)},              # hit him in stride
            {"move": 5, "t": (12.3, 12.6), "path": [(24.8, 9.6), (24.6, 7.8)]},
            {"shot": 5, "t": (12.5, 13.0)},
        ],
        "captions": PASS_AND_CUT_CAPTIONS + DRIBBLE_AT_CAPTIONS + LAYER_3_CAPTIONS + [
            (11.1, "5 makes a Laker cut. 2 hits him in stride"),
            (12.3, "5 makes the layup!"),
        ],
    },
    {
        # Layers 1-3, but 5's man stays with him on the Laker cut and 4's man
        # helps; 4 rotates up to the top and 2 hits him for the 3.
        "slug": "layer-3-alt-3",
        "title": "Layers 1-3 Alternate: 3 Point Shot",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 16.0,
        "clear": [5.3, 10.4],
        "diagram_from": 10.35,
        "events": PASS_AND_CUT + DRIBBLE_AT + LAYER_3_POST + [
            {"move": 5, "t": (11.1, 12.3), "path": [(31, 27.5), (27.8, 19), (25.6, 12.2), (24.8, 9.6)]},
            {"move": 4, "t": (11.3, 12.5), "path": [(6.5, 19.5), (14, 26.5), (25, 29)]},
            {"guard": 4, "t": (11.5, 12.8), "at": (20, 14), "recover": 1.3},
            {"pass": (2, 4), "t": (12.8, 13.4)},
            {"shot": 4, "t": (13.7, 14.4)},
        ],
        "captions": PASS_AND_CUT_CAPTIONS + DRIBBLE_AT_CAPTIONS + LAYER_3_CAPTIONS + [
            (11.1, "5 makes a Laker cut. 4 rotates up to the top"),
            (12.8, "5 is covered, so 2 passes out to 4"),
            (13.7, "4 knocks down the 3!"),
        ],
    },
    {
        # Read & React circle movement: 1 drives north-south down the right
        # side of the lane and everyone moves one spot the same way (3 to the
        # corner, 5 along the baseline, 4 up to the wing, 2 behind the drive).
        # 3's man helps, so 1 pitches to 3 in the corner.
        "slug": "layer-4-circle",
        "title": "Layer 4: Circle Movement: Dribble Penetration, North-South",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 6.6,
        "diagram_until": 2.65,                        # the card shows the circle, not the pitch
        "events": [
            {"dribble": 1, "t": (0.8, 2.4), "path": [(25, 29), (28.2, 22), (29.2, 15.5), (28.4, 11.5)]},
            {"move": 3, "t": (1.0, 2.3), "path": [(43.5, 19.5), (46, 14), (47, 8)]},
            {"move": 5, "t": (1.0, 2.6), "path": [(47, 8), (42, 2.6), (25, 1.9), (8, 2.6), (3, 8)]},
            {"move": 4, "t": (1.1, 2.4), "path": [(3, 8), (4, 14), (6.5, 19.5)]},
            {"move": 2, "t": (1.1, 2.5), "path": [(6.5, 19.5), (14, 26.5), (25, 29)]},
            {"guard": 3, "t": (1.9, 2.9), "at": (31.5, 7), "recover": 1.3},
            {"pass": (1, 3), "t": (2.7, 3.3)},
            {"shot": 3, "t": (3.6, 4.3)},
        ],
        "captions": [
            (0.0, "1 has the ball at the top. Everyone is spaced out"),
            (0.8, "1 drives hard, north-south. Everyone circles his way"),
            (1.8, "3 to the corner, 5 runs the baseline, 4 and 2 move up"),
            (2.7, "3's man helps on the drive. 1 pitches to 3"),
            (3.6, "3 is wide open. Knock it down!"),
        ],
    },
    {
        # Read & React pin & skip, the youth "baby skip" version: the ball
        # goes right, 4's man sinks into the lane to help, 2 pins him, 3
        # dribbles up to shorten the skip and hits 4 popping out to the wing.
        "slug": "layer-5-pin-skip",
        "title": "Layer 7: Pin & Skip",
        "start": FIVE_OUT,
        "ball": 1,
        "length": 8.2,
        "diagram_from": 3.15,                         # the card: the pin, the pop and the skip
        "events": [
            {"pass": (1, 3), "t": (0.8, 1.45)},
            {"move": 1, "t": (1.6, 3.0), "path": [(25, 29), (26, 17), (25.5, 9.5)]},
            {"guard": 4, "t": (1.4, 5.3), "at": (16.5, 9.5), "recover": 1.2},
            {"move": 2, "screen": True, "t": (2.6, 3.5), "path": [(6.5, 19.5), (9, 15), (13, 11.8)]},
            {"move": 4, "t": (3.3, 4.4), "path": [(3, 8), (3.6, 14), (6.5, 19.5)]},
            {"dribble": 3, "t": (3.4, 4.5), "path": [(43.5, 19.5), (37, 25), (31, 27.5)]},
            {"move": 1, "t": (3.2, 4.7), "path": [(25.5, 9.5), (33, 9.5), (39, 13.5), (43.5, 19.5)]},
            {"pass": (3, 4), "t": (4.6, 5.3)},
            {"move": 2, "t": (4.7, 5.7), "path": [(13, 11.8), (7, 9), (3, 8)]},
            {"shot": 4, "t": (5.7, 6.4)},
        ],
        "captions": [
            (0.0, "1 has the ball at the top"),
            (0.8, "1 passes to 3"),
            (1.6, "1 cuts. 4's man sinks into the lane to help"),
            (2.6, "2 pins the helper. 4 pops out to the wing"),
            (3.6, "3 dribbles up to shorten the skip. 1 fills"),
            (4.6, "3 skips it to 4. 2 fills the corner"),
            (5.7, "4 is wide open. Knock it down!"),
        ],
    },
    {
        # Read & React basic post slides: when the ball is driven, the post
        # gets out of the way. Under him, he goes up; over him, he goes down.
        # 4 out, 1 in: 5 on the right mid-post.
        "slug": "layer-5-post-slides",
        "title": "Layer 5: Basic Post Slides",
        "start": {1: (25, 29), 2: (6.5, 19.5), 3: (43.5, 19.5), 4: (3, 8), 5: (31.5, 12)},
        "ball": 3,
        "parts": [
            {
                "length": 5.4,
                "events": [
                    {"dribble": 3, "t": (0.8, 2.3), "path": [(43.5, 19.5), (43.2, 12.5), (39.5, 7), (34.5, 5.2)]},
                    {"move": 5, "t": (0.9, 2.0), "path": [(31.5, 12), (32, 16), (30.5, 19.5)]},
                    {"guard": 5, "t": (1.6, 3.2), "at": (30.2, 4.6), "recover": 1.2},
                    {"pass": (3, 5), "t": (2.4, 2.9)},
                    {"shot": 5, "t": (3.3, 4.0)},
                ],
                "captions": [
                    (0.0, "Post rule: when the ball drives, get out of the way"),
                    (0.8, "3 drives baseline, UNDER 5. 5 slides UP to the elbow"),
                    (2.4, "5's man helps on the drive. 3 hits 5"),
                    (3.3, "5 is open at the elbow. Shoot it!"),
                ],
            },
            {
                "length": 5.4,
                "events": [
                    {"dribble": 3, "t": (0.8, 2.3), "path": [(43.5, 19.5), (36.5, 18.8), (30, 15.5), (27, 11.5)]},
                    {"move": 5, "t": (0.9, 2.0), "path": [(31.5, 12), (34, 8.5), (37.5, 6)]},
                    {"guard": 5, "t": (1.6, 3.2), "at": (27.5, 7.8), "recover": 1.2},
                    {"pass": (3, 5), "t": (2.4, 2.9)},
                    {"shot": 5, "t": (3.3, 4.0)},
                ],
                "captions": [
                    (0.0, "Same rule, other way: the drive goes OVER the post"),
                    (0.8, "3 drives middle, OVER 5. 5 slides DOWN to the short corner"),
                    (2.4, "5's man helps on the drive. 3 dumps it to 5"),
                    (3.3, "5 is open in the short corner. Score it!"),
                ],
            },
        ],
    },
    {
        # Read & React post pass & cut, east-west. X cut: after the post
        # feed, the passer screens away for the guard above him, who cuts
        # to the basket. Relocate: if the passer's man drops to double the
        # post, the passer relocates to the corner for the kick-out.
        "slug": "layer-13-x-cut",
        "title": "Layer 13: Post Pass & X Cut, East-West",
        "start": {1: (25, 29), 2: (6.5, 19.5), 3: (43.5, 19.5), 4: (3, 8), 5: (31.5, 12)},
        "ball": 3,
        "reach": 5,
        "parts": [
            {
                "length": 5.9,
                "events": [
                    {"pass": (3, 5), "t": (0.8, 1.4)},
                    {"move": 3, "screen": True, "t": (1.5, 2.4), "path": [(43.5, 19.5), (36.5, 22.5), (29, 22.6)]},
                    {"move": 1, "t": (2.4, 3.5), "path": [(25, 29), (31, 27.8), (34, 22), (29.6, 13.5), (26.2, 10)]},
                    {"beat": 1, "t": (2.4, 4.6)},
                    {"move": 3, "t": (3.0, 3.9), "path": [(29, 22.6), (26.6, 26.4), (25, 29)]},
                    {"pass": (5, 1), "t": (3.3, 3.7)},
                    {"move": 1, "t": (3.7, 4.0), "path": [(26.2, 10), (24.9, 7.7)]},
                    {"shot": 1, "t": (3.9, 4.4)},
                ],
                "captions": [
                    (0.0, "X cut: 3 has it on the wing, 5 posts up"),
                    (0.8, "3 passes in to 5"),
                    (1.5, "3 screens away for 1 at the top"),
                    (2.4, "1 cuts off the screen to the basket"),
                    (3.3, "5 hits 1 for the layup! 3 replaces at the top"),
                ],
            },
            {
                "length": 5.6,
                "events": [
                    {"pass": (3, 5), "t": (0.8, 1.4)},
                    {"guard": 3, "t": (1.2, 3.3), "at": (34.8, 13.6), "recover": 1.2},
                    {"move": 3, "t": (1.6, 2.6), "path": [(43.5, 19.5), (46, 14), (47, 8)]},
                    {"pass": (5, 3), "t": (2.8, 3.3)},
                    {"shot": 3, "t": (3.6, 4.3)},
                ],
                "captions": [
                    (0.0, "Relocate: same start, 3 feeds the post"),
                    (0.8, "3 passes in. His man drops down to double 5"),
                    (1.6, "3 relocates to the open corner"),
                    (2.8, "5 kicks it back out to 3"),
                    (3.6, "3 is wide open. Knock it down!"),
                ],
            },
        ],
    },
    {
        # Read & React press break (from the youth guide): our spots run
        # full court. 2 screens for 3, 1 inbounds to 2 on the wide side and
        # cuts up the middle, 3 fills behind, 4 fills the wing; 2 hits 1 in
        # the middle and we run.
        "slug": "layer-18-press-break",
        "title": "Layer 18: Press Break",
        "oob": 4.5,
        "depth": 60,
        "press": True,
        "toward": (25, 90),
        "diagram_until": 5.8,                         # the card: the break, not the push
        "start": PRESS_START,
        "ball": 1,
        "length": 9.4,
        "events": PRESS_INBOUND + [
            {"move": 1, "t": (3.5, 5.0), "path": [(30, -2.2), (28, 5), (26, 17), (25, 30)]},
            {"beat": 1, "t": (3.5, 5.6)},
            {"move": 3, "t": (3.6, 4.8), "path": [(6.5, 12), (13, 5), (21, 3.8)]},
            {"move": 4, "t": (3.6, 5.2), "path": [(5, 42), (4.5, 27), (6.5, 13)]},
            {"pass": (2, 1), "t": (5.0, 5.6)},
            {"dribble": 1, "t": (5.9, 7.6), "path": [(25, 30), (25, 42), (25.5, 55)]},
            {"move": 5, "t": (5.9, 7.4), "path": [(45, 42), (44, 50), (42, 57)]},
            {"move": 4, "t": (5.9, 7.8), "path": [(6.5, 13), (6, 32), (8, 56)]},
            {"move": 2, "t": (6.2, 7.8), "path": [(44, 12), (38, 28), (32, 42)]},
        ],
        "captions": PRESS_CAPTIONS + [
            (3.5, "1 cuts hard up the middle. 3 fills behind, 4 fills the wing"),
            (5.0, "2 hits 1 in the middle"),
            (5.9, "Press broken! 1 pushes the middle, 4 and 5 run the lanes"),
        ],
    },
    {
        # The middle is denied, so we reverse it: 2 back to 3 behind the ball,
        # 2 cuts up the middle, 3 swings it to 4, and 4 hits 2 in the middle.
        "slug": "layer-18-press-reverse",
        "title": "Layer 18 Alternate: Press Break Reversal",
        "oob": 4.5,
        "depth": 60,
        "press": True,
        "soft_behind": True,
        "toward": (25, 90),
        "diagram_until": 7.8,                         # the card: the reversal, not the push
        "start": PRESS_START,
        "ball": 1,
        "length": 11.6,
        "events": PRESS_INBOUND + [
            {"move": 1, "t": (3.5, 5.0), "path": [(30, -2.2), (28, 5), (26, 17), (25, 30)]},
            {"move": 3, "t": (3.6, 4.8), "path": [(6.5, 12), (12, 6.5), (17.5, 5)]},
            {"move": 4, "t": (3.6, 5.2), "path": [(5, 42), (4.5, 27), (6.5, 13)]},
            {"pass": (2, 3), "t": (5.1, 5.7)},
            {"move": 1, "t": (5.6, 6.8), "path": [(25, 30), (33, 29), (42, 24)]},
            {"move": 2, "t": (5.7, 7.0), "path": [(44, 12), (36, 20), (27, 29)]},
            {"beat": 2, "t": (5.7, 7.9)},
            {"guard": 4, "t": (5.4, 6.5), "at": (14.5, 21), "recover": 1.0},
            {"pass": (3, 4), "t": (6.1, 6.7)},
            {"pass": (4, 2), "t": (7.1, 7.7)},
            {"dribble": 2, "t": (8.0, 9.6), "path": [(27, 29), (26, 42), (25.5, 55)]},
            {"move": 5, "t": (8.0, 9.5), "path": [(45, 42), (44, 50), (42, 57)]},
            {"move": 4, "t": (8.0, 9.9), "path": [(6.5, 13), (6, 32), (8, 56)]},
            {"move": 1, "t": (8.2, 9.9), "path": [(42, 24), (37, 35), (33, 45)]},
            {"move": 3, "t": (8.4, 9.9), "path": [(17.5, 5), (19, 18), (20, 32)]},
        ],
        "captions": PRESS_CAPTIONS + [
            (3.5, "1 cuts up the middle, but his man takes it away"),
            (5.1, "2 reverses it back to 3, then cuts to the middle"),
            (6.1, "3 swings it to 4. 1 fills the open spot"),
            (7.1, "4 hits 2 in the middle"),
            (8.0, "Press broken! 2 pushes the middle, 4 and 5 run the lanes"),
        ],
    },
    {
        # 4 and 1: 5 holds the right block while the four perimeter players
        # run Layers 1 and 2 around him. Pass and cut, swing, post feed and a
        # Laker cut; then 3 drives the lane, 5's man helps, and 3 drops it
        # to 5 for the layup.
        "slug": "four-and-one",
        "title": "4 and 1",
        "start": {1: (25, 29), 2: (6.5, 19.5), 3: (43.5, 19.5), 4: (3, 8), 5: (31.8, 7.5)},
        "ball": 1,
        "length": 14.4,
        "clear": [5.2, 10.2],
        "diagram_from": 10.15,                        # the card: the drive and the drop-off
        "events": [
            # Layer 1: pass and cut
            {"pass": (1, 2), "t": (0.8, 1.4)},
            {"move": 1, "t": (1.6, 3.0), "path": [(25, 29), (24, 17), (23.5, 10.5)]},
            {"move": 3, "t": (1.9, 3.3), "path": [(43.5, 19.5), (36, 26.5), (25, 29)]},
            {"move": 1, "t": (3.2, 4.6), "path": [(23.5, 10.5), (28, 13.5), (36, 15.5), (43.5, 19.5)]},
            # Layer 2: swing it, feed the post, Laker cut
            {"pass": (2, 3), "t": (5.2, 5.8)},
            {"pass": (3, 1), "t": (6.3, 6.9)},
            {"guard": 5, "t": (6.6, 8.4), "at": (31.6, 4.4), "recover": 0.8},   # 5 seals him behind
            {"pass": (1, 5), "t": (7.3, 7.8)},
            {"beat": 1, "t": (7.3, 8.6)},                  # his man holds a beat, then covers the cut
            {"move": 1, "t": (7.9, 9.0), "path": [(43.5, 19.5), (37, 15.5), (31.5, 13), (27, 10.5), (25, 7.8)]},
            {"move": 1, "t": (9.0, 10.0), "path": [(25, 7.8), (33, 4.5), (41, 5.5), (47, 8)]},
            {"move": 3, "t": (8.6, 9.3), "path": [(25, 29), (29, 28.5), (33, 27)]},
            {"pass": (5, 3), "t": (9.4, 9.9)},
            # the finish: drive and drop it off to 5
            {"dribble": 3, "t": (10.3, 11.4), "path": [(33, 27), (31, 20), (28.5, 13.5)]},
            {"guard": 5, "t": (10.7, 12.2), "at": (28.4, 10.4), "recover": 1.0},
            {"pass": (3, 5), "t": (11.5, 11.9)},
            {"move": 5, "t": (11.9, 12.2), "path": [(31.8, 7.5), (29.2, 6.4)]},
            {"shot": 5, "t": (12.1, 12.6)},
        ],
        "captions": [
            (0.0, "4 and 1: 5 on the low block, four around the arc"),
            (0.8, "1 passes to 2 and cuts to the basket"),
            (1.9, "3 fills the top. 1 cuts through and fills the open wing"),
            (5.2, "Swing it: 2 to 3, then 3 to 1"),
            (7.3, "1 feeds the post and makes the Laker cut"),
            (9.2, "The cut's covered. 3 slides over, 5 kicks it out to him"),
            (10.3, "3 drives the lane. 5's man has to help"),
            (11.5, "3 drops it off to 5 on the block. Layup!"),
        ],
    },
    {
        # Pass and Cut start, but 1 stops his cut in the paint and flashes to
        # the ball-side elbow (left end of the free-throw line); 2 passes to
        # him, makes the Laker cut (4 fills his wing spot) and gets it back
        # for the layup.
        "slug": "laker-cut",
        "title": "Layer 2: Laker Cut",
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
    # ── Race & Space transition (full court) ───────────────────────────────
    # Mike Neighbors' roles: 1 is the Ball (Racker), 5 the Rabbit (rim runner),
    # 2 and 3 the Locks (corner runners), 4 the Dragon (trailer). We defend the
    # top basket and race to the far one.
    {
        # Off a miss: 4 rebounds and outlets to 1, 1 throws it ahead to 3, 3
        # attacks, the deep defender has to step up, and 3 hits 5.
        "slug": "race-space-rebound",
        "title": "Race & Space: Off a Rebound",
        "depth": 94,
        "hoop": (25, 88.75),
        "fps": 15,
        "start": RS_REBOUND_START,
        "ball": 4,
        "chase": RS_REBOUND_CHASE,
        "length": 7.6,
        "events": RS_REBOUND + [
            {"move": 4, "t": (1.3, 5.8), "path": [(22, 6.5), (24, 30), (25, 55), (25, 66)]},
            {"dribble": 3, "t": (3.7, 4.6), "path": [(44.5, 71), (41.5, 76), (38, 79.5)]},
            {"guard": 5, "t": (4.0, 5.4), "at": (33.8, 82.2), "recover": 1.0},
            {"pass": (3, 5), "t": (4.6, 5.1)},
            {"move": 5, "t": (5.1, 5.4), "path": [(19.5, 86.5), (22.6, 87.6)]},
            {"shot": 5, "t": (5.3, 5.8)},
        ],
        "captions": RS_REBOUND_CAPTIONS + [
            (3.7, "5 holds the deep defender. 3 attacks the rim"),
            (4.6, "The deep defender has to step up on 3. 3 hits 5"),
            (5.3, "Rabbit layup! We beat them down the floor"),
        ],
    },
    {
        # The same race off a miss, but 5's man stays home: 3 waits for 4,
        # the Dragon, to trail down and hits him on a basket cut.
        "slug": "race-space-dragon",
        "title": "Race & Space: Dragon Cut",
        "depth": 94,
        "hoop": (25, 88.75),
        "fps": 15,
        "start": RS_REBOUND_START,
        "ball": 4,
        "chase": dict(RS_REBOUND_CHASE, delay={4: 1.6, 1: 0.7, 2: 0.7, 3: 0.7, 5: 0.3}),
        "reach": 4,
        "length": 9.0,
        "events": RS_REBOUND + [
            {"move": 4, "t": (1.3, 5.0), "path": [(22, 6.5), (24, 30), (25, 52), (25, 64)]},
            {"move": 4, "t": (5.0, 6.0), "path": [(25, 64), (26.5, 73), (27.5, 81.5)]},
            {"pass": (3, 4), "t": (5.4, 5.8)},               # hit him in stride, mid-cut
            {"move": 4, "t": (6.0, 6.3), "path": [(27.5, 81.5), (26.4, 85.6)]},
            {"shot": 4, "t": (6.2, 6.7)},
        ],
        "captions": RS_REBOUND_CAPTIONS + [
            (3.7, "5 holds the deep defender. 3 waits on the Dragon"),
            (4.6, "Here comes 4, the Dragon, trailing down the middle"),
            (5.4, "4 cuts hard to the rim. 3 hits him in stride"),
            (6.2, "Dragon layup!"),
        ],
    },
    {
        # Off a make: 4 grabs it, steps out and inbounds to 1 right away, 1
        # pushes and throws it ahead to 2; 2 attacks, the deep defender has
        # to step up, and 2 hits 5 on the far block.
        "slug": "race-space-make",
        "title": "Race & Space: Off a Made Shot",
        "depth": 94,
        "oob": 4.5,
        "hoop": (25, 88.75),
        "fps": 15,
        "start": {4: (24, 5.5), 5: (30, 10), 1: (32, 24), 2: (12, 18), 3: (44, 12)},
        "ball": 4,
        "chase": {"from": {4: (25.5, 9.5), 5: (30, 45), 1: (28, 27), 2: (14, 22), 3: (40, 15)},
                  "speed": 11, "delay": {4: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 5: 0.3}},
        "length": 7.8,
        "events": [
            {"move": 4, "t": (0.2, 0.9), "path": [(24, 5.5), (26, 1.5), (27, -2.2)]},
            {"move": 1, "t": (0.3, 1.0), "path": [(32, 24), (37, 21), (40, 19)]},
            {"pass": (4, 1), "t": (1.0, 1.5)},
            {"move": 5, "t": (0.4, 4.4), "path": [(30, 10), (27, 30), (26, 60), (29.5, 82), (31.5, 86.5)]},
            {"move": 2, "t": (0.5, 3.7), "path": [(12, 18), (5, 45), (5, 66), (6, 72)]},
            {"move": 3, "t": (0.5, 4.2), "path": [(44, 12), (46, 40), (46.5, 70), (47, 86)]},
            {"dribble": 1, "t": (1.6, 3.3), "path": [(40, 19), (36, 33), (28.5, 52)]},
            {"pass": (1, 2), "t": (3.3, 3.9)},
            {"move": 1, "t": (4.0, 5.5), "path": [(28.5, 52), (31, 61), (34, 66)]},
            {"dribble": 2, "t": (4.0, 4.9), "path": [(6, 72), (11, 79), (16.5, 81.5)]},
            {"guard": 5, "t": (4.2, 5.6), "at": (19.6, 82.6), "recover": 1.0},
            {"pass": (2, 5), "t": (4.9, 5.3)},
            {"move": 5, "t": (5.3, 5.6), "path": [(31.5, 86.5), (27.6, 87.6)]},
            {"shot": 5, "t": (5.5, 6.0)},
            {"move": 4, "t": (1.6, 5.8), "path": [(27, -2.2), (24, 20), (22, 48), (22, 63)]},
        ],
        "captions": [
            (0.0, "Off a make: 4 grabs it and steps out of bounds, fast"),
            (1.0, "4 inbounds to 1 right away. Don't wait"),
            (1.6, "1 pushes it up the middle. 5 runs rim to rim"),
            (2.4, "2 and 3 sprint the lanes. 4 trails as the Dragon"),
            (3.3, "1 throws it ahead to 2, up the street"),
            (4.0, "2 attacks. The deep defender has to step up"),
            (4.9, "2 hits 5, the Rabbit, for the layup!"),
        ],
    },
    # ── Defense ─────────────────────────────────────────────────────────────
    {
        # Our Pack Line against a 5-out Read & React offense that never
        # shoots: pass & cut, a drive and kick, a dribble at, a baseline
        # drive, then a pin and a skip. We're the numbered circles.
        "slug": "pack-line",
        "title": "Pack Line Defense",
        "slow": 1.15,                                  # 15% slower, so the movement is easy to follow
        "hold_after_pass": 1.0,                        # freeze after every catch: check everyone's spot
        "us_on_defense": True,
        "pack": True,
        "show_pack": True,
        "trail": (205, 120, 105),
        "fps": 15,
        "chase": {"speed": 19},
        "start": FIVE_OUT,
        "ball": 1,
        "length": 25.0,
        "clear": [4.2, 8.7, 11.9, 17.6, 20.6],
        "diagram_until": 0.01,                        # the card: where everyone stands
        "events": [
            # Layer 1: pass and cut
            {"pass": (1, 2), "t": (4.2, 4.8)},
            {"move": 1, "t": (4.9, 6.3), "path": [(25, 29), (24, 17), (24.5, 9)]},
            {"move": 3, "t": (5.2, 6.6), "path": [(43.5, 19.5), (36, 26.5), (25, 29)]},
            {"move": 5, "t": (5.5, 6.8), "path": [(47, 8), (46.5, 14), (43.5, 19.5)]},
            {"move": 1, "t": (6.7, 8.1), "path": [(24.5, 9), (31, 8), (40, 7.4), (47, 8)]},
            # Layer 4: drive and kick
            {"dribble": 2, "t": (8.7, 9.8), "path": [(6.5, 19.5), (12, 16), (17.5, 12)]},
            {"guard": 4, "t": (8.9, 10.0), "at": (15.2, 10.2), "recover": 0.9},
            {"pass": (2, 4), "t": (9.9, 10.4)},
            {"move": 2, "t": (10.5, 11.6), "path": [(17.5, 12), (12, 16), (6.5, 19.5)]},
            # Layer 3: dribble at
            {"pass": (4, 2), "t": (11.9, 12.4)},
            {"dribble": 2, "t": (13.0, 14.2), "path": [(6.5, 19.5), (13, 25.5), (22.5, 28.6)]},
            {"move": 3, "t": (13.4, 14.6), "path": [(25, 29), (26.5, 18), (25.8, 9.5)]},
            {"move": 4, "t": (13.6, 14.8), "path": [(3, 8), (4, 14), (6.5, 19.5)]},
            {"move": 3, "t": (14.8, 16.0), "path": [(25.8, 9.5), (17, 7.6), (9, 7.2), (3, 8)]},
            {"pass": (2, 5), "t": (16.2, 16.8)},
            # Layer 6: baseline drive
            {"dribble": 5, "t": (17.6, 18.8), "path": [(43.5, 19.5), (43, 12.5), (38.5, 6.5), (33.5, 5)]},
            {"guard": 1, "t": (17.8, 19.0), "at": (31.2, 5.6), "recover": 1.0},
            {"pass": (5, 1), "t": (18.9, 19.4)},
            {"move": 5, "t": (19.4, 20.5), "path": [(33.5, 5), (39, 10), (43.5, 19.5)]},
            # Layer 7: pin and skip
            {"move": 3, "screen": True, "t": (20.6, 21.4), "path": [(3, 8), (12, 11), (18, 13.2)]},
            {"beat": 4, "t": (21.4, 22.8)},
            {"pass": (1, 4), "t": (21.5, 22.3)},
            {"move": 3, "t": (22.3, 23.3), "path": [(18, 13.2), (10, 10), (3, 8)]},
        ],
        "captions": [
            (0.0, "We're on defense. 1 pressures the ball: force it to the side"),
            (1.4, "One pass away (2, 3): in the gap, hand in the passing lane"),
            (2.8, "Two passes away (4, 5): sink to the middle of the floor"),
            (4.2, "Pass to the wing: all five move on the air time"),
            (4.9, "1 jumps to the ball and stays between the cutter and the ball"),
            (6.7, "Ball on the wing: now 4 and 3 are one away, 5 and 1 two away"),
            (8.7, "2 drives. 4 is in the gap: show yourself and stop the ball"),
            (9.9, "Kick out: 4 recovers. Close out under control, hands high"),
            (11.9, "Every pass, every defender moves. See your man and the ball"),
            (13.0, "Dribble at: 3 goes backdoor. We're in the pack: it's covered"),
            (16.2, "Ball to the right side: the left side sinks to the middle"),
            (17.6, "Baseline drive: 1 steps over and cuts it off. No layups"),
            (18.9, "Pitch to the corner: 1 sprints back and closes out"),
            (20.6, "Pin screen on 4. Fight over it: we don't switch"),
            (21.5, "Skip pass: the long close out. Short, choppy steps"),
            (23.0, "That's the Pack Line: one on the ball, four in the pack"),
        ],
    },
]

# ── Look ────────────────────────────────────────────────────────────────────
NAVY, ACCENT, RED = (7, 26, 46), (37, 150, 190), (216, 85, 63)
BOARD, BALL, SEAM = (255, 255, 255), (232, 121, 43), (110, 45, 10)
TRAIL = (7, 26, 46)         # arrow color (set per play)
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
    global VIEW, TOP_FT, LEFT_FT, W, COURT_H, H, TARGET, BASKET, TRAIL
    TRAIL = play.get("trail", NAVY)
    BASKET = play.get("hoop", HOME)
    TARGET = play.get("toward", BASKET)
    VIEW = play.get("depth", DEPTH)
    TOP_FT = play.get("oob", 0)
    LEFT_FT = play.get("oob_side", 0)
    W = int((50 + LEFT_FT) * PX + 2 * PAD)
    COURT_H = int((VIEW + TOP_FT) * PX + 2 * PAD)
    H = COURT_H + CAP_H
HOME = (25, 5.25)            # the basket at the top of the drawing
BASKET = HOME               # the basket we attack (set per play)
TARGET = BASKET             # where the ball handler holds the ball facing (set per play)
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
        if "beat" in e or "guard" in e:
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
        ball = hold_spot(pos[holder], TARGET)
        air = max(air, bounce)
    elif shot is not None:
        ball = shot
    return pos, ball, holder, air, trails


def hold_spot(me, toward):
    """Where the ball sits in a player's hands: on the side facing the play."""
    dx, dy = toward[0] - me[0], toward[1] - me[1]
    d = math.hypot(dx, dy) or 1
    return (me[0] + dx / d * 1.25 + 0.9, me[1] + dy / d * 1.25 + 0.4)


def chase_spots(play, t):
    """Transition defense: each defender starts where he was and runs toward
    his Pack Line spot, but no faster than play["chase"]["speed"] ft/s."""
    fps = play.get("fps", FPS)
    if "_chase" not in play:
        if "from" in play["chase"]:
            cur = dict(play["chase"]["from"])
        else:
            pos, ball, holder, _, _ = state_at(play, 0)
            cur = base_defense(play, pos, ball, ball_man(play, 0, pos, ball, holder))
        step = play["chase"]["speed"] / fps
        delay = play["chase"].get("delay", 0)
        wait = delay if isinstance(delay, dict) else {k: delay for k in cur}
        cache = []
        for i in range(int(play["length"] * fps) + 2):
            pos, ball, holder, _, _ = state_at(play, i / fps)
            tgt = base_defense(play, pos, ball, ball_man(play, i / fps, pos, ball, holder))
            for k, c in cur.items():
                if i / fps < wait.get(k, 0):
                    continue
                dx, dy = tgt[k][0] - c[0], tgt[k][1] - c[1]
                L = math.hypot(dx, dy)
                cur[k] = tgt[k] if L <= step else (c[0] + dx / L * step, c[1] + dy / L * step)
            cache.append(dict(cur))
        play["_chase"] = cache
    cache = play["_chase"]
    return dict(cache[min(len(cache) - 1, max(0, round(t * fps)))])


def defense_for(play, t, pos, ball):
    """Pack Line spots, then hold back any defender who's been screened."""
    spots = chase_spots(play, t) if play.get("chase") else base_defense(play, pos, ball)
    for e in play["events"]:
        if "beat" not in e:
            continue
        a, b = e["t"]
        if a <= t < b:
            p0, b0, _, _, _ = state_at(play, a)
            stuck = base_defense(play, p0, b0)[e["beat"]]
            g = ((t - a) / (b - a)) ** 3
            spots[e["beat"]] = lerp(stuck, spots[e["beat"]], g)
    apply_guards(play, t, spots)
    return keep_apart(spots, pos)


def apply_guards(play, t, spots):
    """Helpers: over to help (or sunk into the lane), then a late recovery.
    Returns True if any guard event is in play at t."""
    hit = False
    for e in play["events"]:
        if "guard" not in e:
            continue
        a, b = e["t"]
        n, rec = e["guard"], e.get("recover", 1.0)
        if a <= t < b:
            spots[n] = lerp(spots[n], e["at"], ease((t - a) / min(0.6, b - a)))
            hit = True
        elif b <= t < b + rec:
            spots[n] = lerp(e["at"], spots[n], ease((t - b) / rec))
            hit = True
    return hit


def base_defense(play, pos, ball, ballman=None):
    if play.get("pack"):
        return pack_rules(pos, ball, ballman)[0]
    if play.get("press"):
        return press_at(pos, ball, play.get("soft_behind", False))
    return defense_at(pos, ball, play.get("sag", 1.0), play.get("reach"))


def ball_man(play, t, pos, ball, holder):
    """Whose ball it is for the defense: the holder, or the receiver as soon
    as a pass is in the air (we move on the air time), or the man nearest."""
    if holder is not None:
        return holder
    for e in play["events"]:
        if "pass" in e and e["t"][0] <= t < e["t"][1]:
            return e["pass"][1]
    return min(pos, key=lambda n: dist(pos[n], ball))


def pack_jobs(pos, ballman):
    """Each defender's job: "ball", "one" or "two" passes away, or "cutter"
    for a man inside the arc. Passes away go by the order of the perimeter
    players around the basket: the ball's neighbors are one pass away."""
    jobs = {ballman: "ball"}
    perim = [n for n in pos if n != ballman and dist(pos[n], BASKET) >= 11]
    for n in pos:
        if n not in jobs and n not in perim:
            jobs[n] = "cutter"
    ang = lambda n: math.atan2(pos[n][1] - BASKET[1], pos[n][0] - BASKET[0])
    ring = sorted(perim + [ballman], key=ang)
    i = ring.index(ballman)
    near = {ring[j] for j in (i - 1, i + 1) if 0 <= j < len(ring)}
    for n in perim:
        jobs[n] = "one" if n in near else "two"
    return jobs


def pack_rules(pos, ball, ballman=None):
    """Our Pack Line, by the rules on the Pack Line page."""
    if ballman is None:
        ballman = min(pos, key=lambda n: dist(pos[n], ball))
    jobs = pack_jobs(pos, ballman)
    spots = {}
    for n, man in pos.items():
        to_rim = (BASKET[0] - man[0], BASKET[1] - man[1])
        L = math.hypot(*to_rim) or 1
        u = (to_rim[0] / L, to_rim[1] / L)
        job = jobs[n]
        if job == "ball":                                  # pressure, shade the middle: force him to the side
            tgt = (man[0] + u[0] * 3.0 + (0.9 if man[0] < 25 else -0.9), man[1] + u[1] * 3.0)
        elif job == "one":                                 # in the gap, a good step off, inside the line
            step = max(4.5, L - 14.5)
            tgt = lerp((man[0] + u[0] * step, man[1] + u[1] * step), ball, 0.2)
            if dist(tgt, BASKET) > PACK - 1:              # both feet inside the line
                tgt = lerp(BASKET, tgt, (PACK - 1) / dist(tgt, BASKET))
        elif job == "two":                                 # sink to the middle of the floor
            tgt = (25 + (man[0] - 25) * 0.2, max(8.0, min(15.0, man[1] * 0.55 + 4)))
        else:                                              # a cutter: stay between him and the ball
            tgt = lerp(man, ball, 0.22)
        spots[n] = tgt
    return keep_apart(spots, pos), jobs


def press_at(pos, ball, soft_behind=False):
    """Full-court man pressure: deny every pass, and play in front of the
    ball handler until he gets past half of the backcourt. With soft_behind,
    a man behind the ball is guarded from the upcourt side, so the pass back
    is open (real pressure gives that pass up)."""
    spots = {}
    for n, man in pos.items():
        if dist(man, ball) < 2.5:
            if man[1] < 0:                                 # the inbounder: arms up, just in bounds
                tgt = (man[0], 1.6)
            else:                                          # in front of him, then beaten behind him
                w = max(0.0, min(1.0, (man[1] - 24) / 10))
                tgt = lerp((man[0], man[1] + 3.0), (man[0] + 1.6, man[1] - 3.2), w)
        else:                                              # deny: between him and the ball
            v = (ball[0] - man[0], ball[1] - man[1])
            L = math.hypot(*v) or 1
            tgt = (man[0] + v[0] / L * 2.8, man[1] + v[1] / L * 2.8)
            if soft_behind:
                w = max(0.0, min(1.0, (ball[1] - man[1] - 1) / 4))
                tgt = lerp(tgt, (man[0], man[1] + 4.0), w)
        spots[n] = tgt
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
        if sag >= 1 and dist(tgt, BASKET) > PACK and w < 0.5:   # stay inside the pack line
            d = dist(tgt, BASKET)
            tgt = lerp(BASKET, tgt, (PACK + (d - PACK) * 0.35) / d)
        if reach and dist(tgt, man) > reach:               # don't play off him too far
            tgt = lerp(man, tgt, reach / dist(tgt, man))
        if dist(tgt, BASKET) < 2.6:                        # don't park on the rim: trail beside him
            side = 1 if man[0] <= BASKET[0] else -1
            tgt = (man[0] + 3.2 * side, man[1] + (1.2 if BASKET[1] < 47 else -1.2))
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
    d.line([P(25 - R, 0), P(25 - R, HOME[1])], fill=NAVY, width=lw)
    d.line([P(25 + R, 0), P(25 + R, HOME[1])], fill=NAVY, width=lw)
    bx, by = P(*HOME)
    rr = R * PX
    d.arc([bx - rr, by - rr, bx + rr, by + rr], 0, 180, fill=NAVY, width=lw)
    # backboard and rim
    d.line([P(22, 4), P(28, 4)], fill=NAVY, width=int(3 * SS))
    d.line([P(25, 4), P(25, 4.5)], fill=NAVY, width=lw)
    rim = 0.75 * PX
    d.ellipse([bx - rim, by - rim, bx + rim, by + rim], outline=NAVY, width=lw)
    if VIEW >= 94:                                     # full court: the far end, mirrored
        far_end(d, lw)


def far_end(d, lw):
    F = lambda x, y: P(x, 94 - y)
    for x0, x1 in ((0, 3), (47, 50)):                  # hash marks
        d.line([F(x0, 28), F(x1, 28)], fill=NAVY, width=lw)
    d.rectangle([F(19, 19), F(31, 0)], outline=NAVY, width=lw)            # lane
    cx, cy = F(25, 19)
    r = 6 * PX
    d.arc([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=NAVY, width=lw)
    for k in range(9):
        a0 = k * 20
        d.arc([cx - r, cy - r, cx + r, cy + r], a0, a0 + 11, fill=NAVY, width=lw)
    R = 19.75
    d.line([F(25 - R, 0), F(25 - R, HOME[1])], fill=NAVY, width=lw)
    d.line([F(25 + R, 0), F(25 + R, HOME[1])], fill=NAVY, width=lw)
    bx, by = F(*HOME)
    rr = R * PX
    d.arc([bx - rr, by - rr, bx + rr, by + rr], 180, 360, fill=NAVY, width=lw)
    d.line([F(22, 4), F(28, 4)], fill=NAVY, width=int(3 * SS))
    d.line([F(25, 4), F(25, 4.5)], fill=NAVY, width=lw)
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


JOB_TAGS = {"ball": ("ON BALL", NAVY), "one": ("1 AWAY", ACCENT), "two": ("2 AWAY", (31, 157, 87)),
            "cutter": ("CUTTER", (110, 120, 132)), "help": ("HELP", (232, 121, 43))}


def pack_line(d):
    """The pack line: a dashed arc 16 feet from the rim."""
    bx, by = P(*HOME)
    r = PACK * PX
    a = -19
    while a < 199:
        d.arc([bx - r, by - r, bx + r, by + r], a, a + 5, fill=(150, 196, 214), width=int(2 * SS))
        a += 9


def place_tags(d, spots, pos, jobs):
    """Put each job tag on whichever side of its circle (below, above, right,
    left) covers the fewest players and other tags. In feet."""
    bodies = [(p, 1.6) for p in list(pos.values()) + list(spots.values())]
    placed, out = [], {}
    for n in sorted(spots, key=lambda n: jobs[n] != "ball"):    # the ball's tag picks first
        p = spots[n]
        hw = (d.textlength(JOB_TAGS[jobs[n]][0], font=F_TAG) + 10 * SS) / 2 / PX
        hh = 8 * SS / PX
        def penalty(c):
            x0, x1, y0, y1 = c[0] - hw, c[0] + hw, c[1] - hh, c[1] + hh
            pen = 0.0
            for q, r in bodies:
                if q is p:
                    continue
                dx = max(x0 - q[0], 0, q[0] - x1)
                dy = max(y0 - q[1], 0, q[1] - y1)
                pen += max(0.0, r - math.hypot(dx, dy))
            for (a0, a1, b0, b1) in placed:
                pen += 3 * max(0.0, min(x1, a1) - max(x0, a0)) * max(0.0, min(y1, b1) - max(y0, b0))
            pen += max(0.0, x1 - 50) + max(0.0, -x0) + max(0.0, -y0) + max(0.0, y1 - VIEW)
            return pen
        cands = [(p[0], p[1] + 2.75), (p[0], p[1] - 2.75), (p[0] + 1.6 + hw, p[1]), (p[0] - 1.6 - hw, p[1])]
        best = min(cands, key=penalty)                       # ties keep the earlier (below) spot
        placed.append((best[0] - hw, best[0] + hw, best[1] - hh, best[1] + hh))
        out[n] = best
    return out


def tag(d, at, job):
    text, color = JOB_TAGS[job]
    x, y = P(*at)
    w = d.textlength(text, font=F_TAG) + 10 * SS
    d.rounded_rectangle([x - w / 2, y - 8 * SS, x + w / 2, y + 8 * SS], radius=6 * SS, fill=color)
    d.text((x, y + 0.5 * SS), text, font=F_TAG, fill=(255, 255, 255), anchor="mm")


def defense_frame(play, t, d, diagram):
    """Us on defense: the offense is the squares, we're the numbered circles,
    each tagged with his job right now."""
    pos, bp, holder, air, trails = state_at(play, t)
    if not diagram:
        for tr in trails:
            trail(d, *tr)
    spots = defense_for(play, t, pos, bp)
    jobs = pack_jobs(pos, ball_man(play, t, pos, bp, holder))
    for e in play["events"]:                       # a helper stepping over to stop a drive
        if "guard" in e and e["t"][0] <= t < e["t"][1]:
            jobs[e["guard"]] = "help"
    for n, p in pos.items():
        defender(d, p)
        if n == holder:
            x, y = P(*p)
            r2 = 1.2 * PX + 4 * SS
            d.rectangle([x - r2, y - r2, x + r2, y + r2], outline=ACCENT, width=int(2 * SS))
    for n, p in spots.items():
        offense(d, n, p, False)
    for n, at in place_tags(d, spots, pos, jobs).items():  # tags on top of everyone
        tag(d, at, jobs[n])
    ball(d, bp, air)


def frame(play, t, diagram=False):
    img = Image.new("RGB", (W, H if not diagram else COURT_H), BOARD)
    d = ImageDraw.Draw(img)
    court(d)
    if play.get("show_pack"):
        pack_line(d)
    if play.get("us_on_defense"):
        defense_frame(play, play.get("diagram_from", 0) if diagram else t, d, diagram)
        if not diagram:
            caption(d, play, t, play["length"])
        return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)
    if diagram:                                        # everything at once, players at the start
        t0 = play.get("diagram_from", 0)
        pos, _, holder, _, _ = state_at(play, t0)
        holder = holder or play["ball"]
        late = dict(play, clear=list(play.get("clear", [])) + ([t0] if t0 else []))
        _, _, _, _, trails = state_at(late, play.get("diagram_until", play["length"]))
        for tr in trails:
            trail(d, tr[0], tr[1], True)
        if play.get("defense", True):
            spots = chase_spots(play, t0) if play.get("chase") else base_defense(play, pos, hold_spot(pos[holder], TARGET))
            if apply_guards(play, t0, spots):                # a helper in the lane at that moment
                spots = keep_apart(spots, pos)
            for p in spots.values():
                defender(d, p)
        for n, p in pos.items():
            offense(d, n, p, n == holder)
        ball(d, hold_spot(pos[holder], TARGET))
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
    parts = [dict(play, **part) for part in play["parts"]] if "parts" in play else [play]
    fps = play.get("fps", FPS)
    frames, durs = [], []
    step = 1000 / fps                                  # "slow" rescales this below
    for part in parts:
        prepare(part)
        times = [i / fps for i in range(int(part["length"] * fps))]
        frames += [frame(part, t) for t in times]
        d = [step] * len(times)
        hold = part.get("hold_after_pass", 0)
        for e in part["events"] if hold else []:       # freeze just after each catch
            if "pass" in e:
                k = next((i for i, t in enumerate(times) if t >= e["t"][1] + 0.2), None)
                if k is not None:
                    d[k] += hold * 1000
        durs += d
    n = len(frames)
    # one shared palette so colors don't flicker from frame to frame
    sample = Image.new("RGB", (frames[0].width, frames[0].height * 4))
    for k, f in enumerate([frames[0], frames[n // 3], frames[2 * n // 3], frames[-1]]):
        sample.paste(f, (0, k * frames[0].height))
    pal = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    gif = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    path = os.path.join(out_dir, play["slug"] + ".gif")
    plain = play.get("slow", 1.0) == 1.0 and not any(p.get("hold_after_pass") for p in parts)
    if plain:
        duration = 1000 // fps
    else:
        # GIF delays come in hundredths of a second, so measure how fast the
        # plain GIF really plays and make "slow" relative to that
        buf = io.BytesIO()
        gif[0].save(buf, format="GIF", save_all=True, append_images=gif[1:], duration=1000 // fps, loop=0)
        buf.seek(0)
        real = sum(f.info.get("duration", 0) for f in ImageSequence.Iterator(Image.open(buf)))
        scale = real * play.get("slow", 1.0) / (step * n)
        durs = [x * scale if x == step else step * scale + (x - step) for x in durs]
        duration, run, shown = [], 0.0, 0             # spread the rounding so the average is exact
        for x in durs:
            run += x
            nxt = int(round(run / 10)) * 10
            duration.append(nxt - shown)
            shown = nxt
    gif[0].save(path, save_all=True, append_images=gif[1:], duration=duration, loop=0, optimize=False)
    png = os.path.join(out_dir, play["slug"] + ".png")
    frame(parts[0], 0, diagram=True).save(png, optimize=True)
    print(f"{play['slug']}: {n} frames, {os.path.getsize(path) // 1024} KB gif, {os.path.getsize(png) // 1024} KB png")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "plays")
    os.makedirs(out, exist_ok=True)
    want = set(sys.argv[1:])
    for p in PLAYS:
        if not want or p["slug"] in want:
            build(p, out)
