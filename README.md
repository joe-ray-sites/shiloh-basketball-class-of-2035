# Shiloh Saints Basketball — Team Hub

Mobile-first team hub for Shiloh 4th Grade Basketball (Class of 2035):
roster, coaching staff, schedule, practice plans, team stats, per-game box
scores and play-by-play. Sister site to the football hub, same architecture.

`index.html` is the whole app — no build step, no dependencies. Open it in a
browser and it runs. Live at
https://joe-ray-sites.github.io/shiloh-basketball-class-of-2035/

## Layout

```
index.html            the entire site (markup, styles, data, logic)
resize-photos.py      batch-resizes photos for the web
make-icons.py         favicon + home-screen icons from the logo
assets/
  sc-logo.png         team mark (drop it here, then run make-icons.py)
  players/            player photos, named by JERSEY NUMBER (23.jpg, 1.png …)
  coaches/            coach photos, named by their id in COACHES (1.jpg …)
  icons/              generated — don't edit by hand
  _originals/         full-res originals (git-ignored)
```

## Adding photos

Name each file after the player's jersey number and drop it in
`assets/players/`. Both `.jpg` and `.png` work — the page tries `.jpg`, then
`.png`, then falls back to an initials monogram. Then shrink them for the web:

```bash
python3 resize-photos.py          # add --dry-run to preview
```

Originals are moved to `assets/_originals/` untouched. The script also applies
the EXIF rotation flag and strips EXIF metadata (phone photos can carry GPS).

## Logo and icons

Drop the logo at `assets/sc-logo.png` and run:

```bash
python3 make-icons.py
```

It writes the favicon and every home-screen icon onto a white plate (iOS
composites transparent icons onto black). Until the logo exists the script
draws the "SC" monogram instead. If the logo's shape differs from the football
mark, update `--logo-ratio` in the `:root` block of `index.html`.

## Schedule

The Schedule tab merges two lists in `index.html` by date, grouped by month:

- **`PRACTICE_DAYS`** holds practices, shown as white cards with black text.
  Each one is `{ date, time, loc, plan }`, where `loc` is a key in `GYMS`
  and `plan` is the id of a season plan in `PRACTICES`. Tapping the card opens
  that plan, and the plan shows its date(s) and sorts by them on the Practice
  tab. Add `optional:true` for an optional practice, or
  `{ date, off:true, note }` to call out a day with no practice.
- **`GAMES`** holds games, shown as dark cards with white text. It is empty
  until the game schedule is out, and the tab says games are coming soon.

The first event on or after today gets the "Next Up" badge, and past days dim.

## Entering a game

Everything derives from the `GAMES` array in `index.html` — player season
totals, the Team Stats page, leaders and each box score all roll up from it.
Give a game `final:true`, the score and a `stats` block and the rest updates
itself. Player lines are keyed by **jersey number**, never by name:

```js
stats:{
  players:{ 23:{ pts:8, fgm:4, fga:9, tpm:0, tpa:1, ftm:0, fta:2,
                 oreb:1, dreb:2, ast:2, stl:3, blk:0, to:2, fouls:1 }, … },
  team:{ quarters:{ us:[8,9,6,8], them:[6,4,8,5] },   // optional
         opp:{ fgm:10, fga:30, … } },                  // optional
  quarters:[ { n:1, plays:[ { t:"#23 layup", pts:2 },
                            { t:"Opponent jumper", pts:2, opp:true },
                            { t:"#5 steal", stl:true } ] }, … ],
}
```

The shape is documented in full above `GAMES` in `index.html`. Final scores
are authoritative as entered — nothing on the page re-derives them. On load
the page audits each played game and warns in the browser console if a
dictated team total disagrees with the player lines.

Open the page with `?demo=1` to see a made-up box score while the season
hasn't started; the live site never shows it.

## Practice plans

The Practice tab lists the season plans in the `PRACTICES` array in
`index.html`, one per practice day. Each plan matches its slot (Thursdays 60
minutes, Mondays and the Tuesday session 90) and follows the coaching pages:
start side by side, shooting and Vegas Close Outs every practice, a Pack Line
piece, the Read & React layer of the day, a fun game, and live play to finish. Each block is `{ min, drill, note? }` and `drill` is a key into
`DRILLS`, the library of drills and games (name, category, source, video link,
description). Add a drill to `DRILLS` once and reference it from any plan; the
Drill Library tab renders everything in `DRILLS` grouped by category. Set a
practice's `date` ("2026-11-10") once the schedule is known and the list sorts
by date.

Sources: Breakthrough Basketball youth drills, USA Basketball's foundational
skills and drills, the Jr. NBA drill videos, Basketball For Coaches' written
guides to the classic games, the Read & React teaching videos, Coach's
Clipboard's Pack Line drills, Pack Line clinic videos, Race & Space, and
drills from our own coaching pages (these link to the page instead of out).

When the season plans are rewritten, bump `PLAN_REV` in `index.html`. Each
device then turns any edits a coach made to the old plans into "(my edit)"
plans under Mine, so the new season plans show as written and nothing is
lost.

Every plan, season or coach-made, can be edited, duplicated, shared and
deleted from its page, and the list can be filtered (All / Mine / Season
plans) and reordered. All of that is per device, in localStorage:
coach-made plans in `shiloh-bb.practices`, edits to season plans in
`shiloh-bb.planEdits` (with a "Reset to original" button), deleted season
plans in `shiloh-bb.planHidden` (a "Restore" link brings them back), the
list order in `shiloh-bb.planOrder`, and an unsaved draft in
`shiloh-bb.practiceDraft`. "Share link" packs the whole plan into a
`?plan=` URL that opens on any phone with a "Save to my practices" button.

### Getting a coach's plan into the season plans

A coach-made (or edited) plan has a "Send to the season plans" button. It
produces a block of text the coach can share, copy or email: a readable
summary, the share link, and a paste-ready entry for the `PRACTICES` array.
To publish it, paste that text into Claude with "add this as a season plan"
(or drop the entry into `PRACTICES` by hand with the next id), then commit
and push. Set `ADMIN.email` in `index.html` to enable the Email button.

## Basketball Philosophy

Menu → Basketball Philosophy renders the coach's write-up from the
`PHILOSOPHY_MD` string in `index.html` (headings, paragraphs, lists, bold and
italic are supported). The line `*[Graphs go here]*` is where the three shot
charts are inserted; their data lives in `SHOT_PCT` / `SHOT_PPS` next to it.

## Coaching pages

Menu also holds Defensive Levels, Pack Line Defense, Transition Defense and
Read & React Offense, in `DEF_LEVELS_MD`, `PACK_LINE_MD`, `DEF_TRANSITION_MD`
and `READ_REACT_MD` (same markdown mini-format; indent
two spaces to nest a bullet, `[text](url)` for links, `[text](#packline)`
to link to another page in the app). The Read & React
layers table comes from `RR_GROUPS`; every R&R teaching video is also a
drill in the library (keys starting with `rr`).

## Plays

The Plays tab (bottom nav) lists offense and defense play calls from the
`PLAYS` array in `index.html` (name, offense/defense, tag, summary, steps,
coaching points, related drills). Each play has a looping animated GIF and a
still clipboard diagram in `assets/plays/<id>.gif` / `<id>.png`, drawn by:

```bash
python3 make-plays.py            # every play
python3 make-plays.py pass-and-cut
```

`make-plays.py` holds the choreography: start spots for 1-5 (feet on a half
court, basket at the top), who has the ball, and timed passes, cuts,
dribbles and shots, plus the captions shown under the court. A long play can
clear its arrows between phases (`clear`) and draw its still diagram from a
later phase (`diagram_from`). Plays can share a start: Pass and Cut -
Extended reuses the Pass and Cut events. Offense is circled
numbers; the defense (squares with an X) is placed automatically by Pack Line
rules, or set `"defense": False`. To add a play, add its choreography there
and its words to `PLAYS` with the same id, then run the script.

Players now lives in the Menu, next to Coaches.

## League pages

Menu → League Directors Meeting and League Rules are the AAO NWA League's
Fall 2026–27 directors meeting deck and league rules, transcribed word for
word into `LEAGUE_MEETING_MD` and `LEAGUE_RULES_MD`. The meeting's weekend
list and season schedule graphic are tables built from `LEAGUE_WEEKENDS` and
`LEAGUE_GRAPHIC`. The source PDFs are not committed. Past Seasons is off the
Menu until there is a past season; add it back to `MENU_PAGES` then.

## Access code

The landing screen asks for a 4-digit code. It is a deterrent, not security —
the code sits in `index.html` and asset files can be fetched directly. Don't
put anything sensitive behind it.
