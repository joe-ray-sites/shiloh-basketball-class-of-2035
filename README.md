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

The Practice tab lists 60-minute plans built from the `PRACTICES` array in
`index.html`. Each block is `{ min, drill, note? }` and `drill` is a key into
`DRILLS`, the library of drills and games (name, category, source, video link,
description). Add a drill to `DRILLS` once and reference it from any plan; the
Drill Library tab renders everything in `DRILLS` grouped by category. Set a
practice's `date` ("2026-11-10") once the schedule is known and the list sorts
by date.

Sources: Breakthrough Basketball youth drills, USA Basketball's foundational
skills and drills, the Jr. NBA drill videos, Basketball For Coaches' written
guides to the classic games, and the Read & React teaching videos.

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

Menu also holds Defensive Levels, Transition Defense and Read & React
Offense, transcribed from the coaching spreadsheet into `DEF_LEVELS_MD`,
`DEF_TRANSITION_MD` and `READ_REACT_MD` (same markdown mini-format; indent
two spaces to nest a bullet, `[text](url)` for links). The Read & React
layers table comes from `RR_GROUPS`; every R&R teaching video is also a
drill in the library (keys starting with `rr`).

## Access code

The landing screen asks for a 4-digit code. It is a deterrent, not security —
the code sits in `index.html` and asset files can be fetched directly. Don't
put anything sensitive behind it.
