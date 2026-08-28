# Design feedback backlog

Tracked but intentionally not fixed yet — noted during pile-v1 prototype review, not blocking.

## 1. Piles skew to the sides instead of mounding in the center — DONE
Fixed by biasing spawn x toward lane center (average of 3 uniform samples,
Irwin-Hall-ish) instead of uniform random across the full width.

## 2. Icon sizes should scale realistically relative to each other
Current icons are uniform-radius circles/shapes regardless of crop. Needs real
per-crop size ratios once we're doing actual icon art (a cherry tomato icon
should read smaller than a summer squash icon, etc).

## 3. Prefer 1:1 icon-to-unit ratio, not compressed multi-unit icons
Real constraint to solve before this is viable: full-season Tomatoes,
salad/slicer = 562 units. Collision resolution is O(n^2) per iteration
(4 iterations/frame) — 562 icons in one lane is ~1.3M pairwise checks/frame.
Options when we get here: spatial-grid broad-phase (only check nearby icons),
or lean on the date-range selector so default views stay in the low hundreds,
or both.

## 4. Whole site should feel like a garden
User has a candidate photo taken in the garden to use as a background, plus an
idea for ambient birds/bees/butterflies drifting across the page. This is a
whole-site art-direction decision, not a per-chart tweak — revisit once we're
building the real GH Pages site, not the artifact prototypes. Will need a
contrast scrim over the photo wherever there's text/UI (dataviz accessibility
rules still apply to real UI, not just charts). taste-skill (or similar) may be
worth trying here for the ambient-motion/illustration layer specifically.

## 5. Farm truck as the "container" for the pile, with drive-in/drive-out transitions
Veggies dump onto the bed of a cute truck with wooden side rails (parked in frame)
instead of a bare lane floor. On date-range change: current truck drives off-screen
right (full, or however full it ended up), a new empty truck drives in from the
left, then the new dump animation plays onto it. Turns the range-change interaction
into a small scene transition rather than an abrupt reset. Would want the truck bed
to act as the physics floor/walls (replacing the current lane box) so piles look
contained by the wooden rails rather than the page background.

## 6. Full email-driven update loop, with auto-reply
Ideal flow: CC a dedicated address on the existing weekly totals email -> it gets
parsed -> Airtable updates (now the source of truth, replacing the earlier
copy-of-the-Google-Sheet plan) -> the live site regenerates -> an auto-reply goes
back to everyone CC'ed with a weekly visual. This is the full version of the
"weekly manual update" MVP step, with two new pieces beyond what was already
planned: (a) a real inbound-mail trigger (a dedicated Gmail address + Apps Script/
filter, or an inbound-parse webhook service, since nothing currently listens for
mail) and (b) generating a rendered chart image server-side to attach/embed in the
reply (headless render of the pile chart, or a simpler static summary chart just
for email). Meaningfully bigger than the plain "paste into a conversation" MVP —
worth doing only after that manual version is proven out.

## 7. Weekly photos in a gallery, filtered by the selected date range
Every weekly count email already includes a photo. Want those collected and shown
in a gallery on the site, filtered to whatever date range is currently selected in
the pile view (so picking "September" also shows September's photos). Needs: a
place to store photos (repo assets vs. Drive), a photo-to-date mapping, and a
gallery UI wired to the same range-selector state the pile chart uses. Mostly
straightforward once photos are actually being collected somewhere — the collection
mechanism is the part that depends on item 6 (or, in the MVP-manual version, on
you dropping photos in a folder alongside the pasted weekly totals).
