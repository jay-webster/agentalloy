# AgentAlloy Tuning — Coding-Skill Injection for Smaller Models

**Purpose:** Improve the coding lift AgentAlloy delivers when it dynamically prepends skills to a user prompt, specifically for smaller models (e.g. Haiku-class). This document is derived from a controlled A/B test (Opus vs. Haiku) building the same web-UI month-calendar against the same spec. Opus scored 8.0/10; Haiku scored 6.0/10. **Every recommendation here maps to a real, observed failure in the Haiku output** — these are not generic best practices, they are the specific deltas that separated the two runs.

The framing throughout: each skill is written so it can be **injected verbatim (or lightly templated) into the front of a prompt**. Skills are short, imperative, example-bearing, and self-contained. Smaller models follow concrete rules-with-examples far better than abstract principles, so every skill below pairs a rule with a wrong/right code pair.

---

## 0. Executive Summary — the root-cause pattern

All four of Haiku's defects share **one root cause**: *the same fact was encoded in two places that silently disagreed.*

| Defect | Place A | Place B (disagreed) |
|---|---|---|
| Grid misaligned every month | Header labels `['Mon'…'Sun']` | Math used `getDay()` (Sunday=0) |
| Overflow badge off-by-one | `slice(0, 3)` (3 dots) | `length - 2` (implies 5) |
| Events feature dead in app | Feature built + tested in `Calendar.jsx` | `App.jsx` rendered `<Calendar/>` with no `events` prop |
| Events repeat every month | Intent: match a specific date | `event.date === dayNumber` (day-of-month only) |

Opus avoided all four by maintaining a **single source of truth** flowing through a **typed, pure** layer.

**The meta-skill AgentAlloy should inject for every coding task is: "Derive, don't duplicate. Any fact that appears twice must be computed from one constant."** Everything below is an instance of that principle plus the verification habits that catch violations.

The secondary root cause: Haiku produced **60 passing tests that were blind to a visible bug**. High test *volume*, low test *power*. Injected testing skills must push for behavior-assertions, not existence-assertions.

---

## 1. Skill: Single Source of Truth (derive, don't duplicate)

**Inject when:** any task involving configuration, layout conventions, indexing, ordering, or repeated literals.

> **SKILL — Single Source of Truth.** If the same fact (a week-start day, a column count, a max-items limit) is needed in more than one place, define it ONCE as a named constant and derive every use from it. Never hardcode the fact in one place and re-derive it by hand in another — they will drift and silently disagree.

**Wrong (Haiku's actual bug):**
```js
const WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']; // header says Monday-first
// ...but the math assumes Sunday-first:
for (let i = firstDay.getDay() - 1; i >= 0; i--) { /* leading blanks */ }
// Result: June 1 2025 (a Sunday) renders under the "Mon" column. Every month shifts.
```

**Right:**
```js
const WEEK_START = 1; // Monday = single source of truth
const WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const leadingBlanks = (firstOfMonth.getDay() - WEEK_START + 7) % 7; // derived, can't drift
```

**Checklist to inject alongside:**
- Does any literal (`'Mon'`, `7`, `3`, `0`) appear in two spots? Name it.
- Does one part of the code *describe* a convention and another part *implement* it? They must reference the same constant.

---

## 2. Skill: Write tests that a bug would fail (assert behavior, not existence)

**Inject when:** any task that asks for tests, or any task where the model will self-verify.

This is the highest-leverage skill for small models. Haiku wrote **60 tests, all green, and still shipped a visibly broken grid** because the tests asserted *"day 1 renders"* and *"42 cells exist"* — never *which column day 1 lands in*. Existence/count assertions manufacture false confidence.

> **SKILL — Tests must assert behavior a bug would break.** For every test ask: "What specific wrong output would make this fail?" If the answer is "nothing — it just checks something exists or counts elements," the test is not pulling its weight. Pin known inputs (fixed dates, fixed data) and assert the exact semantic result.

**Weak (Haiku-style — passes on broken code):**
```js
it('renders day 1', () => {
  render(<Calendar month={5} year={2025} />);
  expect(screen.getByText('1')).toBeInTheDocument(); // green even when misaligned
});
```

**Strong (would have caught the bug):**
```js
it('June 1 2025 (Sunday) sits in the last/Sun column', () => {
  render(<Calendar month={5} year={2025} />);
  const cells = screen.getAllByRole('gridcell');
  const firstNonBlank = cells.findIndex(c => c.textContent === '1');
  expect(firstNonBlank % 7).toBe(6); // Sunday column under Mon-first header
});
```

**Inject this rule of thumb:** *"More assertions on one pinned input beats more test cases on unpinned inputs."* A handful of tests with `vi.setSystemTime` / fixed props that check exact placement outperforms dozens that check existence.

---

## 3. Skill: Trace the feature from the real entry point (verify wiring)

**Inject when:** multi-file tasks, component+app structure, anything with an integration seam.

Haiku fully built and tested an events feature — then `App.jsx` rendered `<Calendar />` **with no `events` prop**, so the feature was dead in the running product. Unit tests were green; the app showed nothing. Small models tend to verify the unit and assume the wiring.

> **SKILL — Verify the wiring, not just the unit. After building a feature, trace it from the application's real entry point (App → component → render) and confirm the data actually flows. Green unit tests prove the unit works in isolation; they do NOT prove the running app uses it. "Run it and read the top-level render" catches integration gaps tests structurally cannot.**

**Wrong:**
```jsx
// App.jsx — feature built in Calendar but never fed:
<Calendar />          // events prop missing → indicators never show
```

**Right:**
```jsx
<Calendar events={events} />   // and confirm `events` is actually populated
```

**Inject the habit:** end every multi-file task with a "data-flow trace" — name the prop/state, follow it from source to render, confirm no link is empty.

---

## 4. Skill: Use platform normalization for dates; never hand-roll calendar math

**Inject when:** any date/time/calendar logic (one of the most bug-dense domains).

Opus routed *all* date arithmetic through `new Date(year, month, day)`, which self-normalizes overflow (Dec→Jan rollover, day overflow) for free. Haiku hand-rolled offsets and matched events on day-of-month only.

> **SKILL — Lean on `Date` normalization; never hand-roll rollover or compare dates loosely.**
> - Advance a month with `new Date(y, m + 1, 1)` — December→January is handled automatically.
> - Build a month grid from `new Date(y, m, 1 - leadingBlanks)` and increment by day; overflow normalizes itself.
> - Compare dates by **year AND month AND day** (or by normalized timestamp), never by day-of-month alone, never as strings.

**Wrong (Haiku — events repeat in every month):**
```js
const dayEvents = events.filter(e => e.date === dayNumber); // ignores month & year
```

**Wrong (manual rollover, error-prone):**
```js
if (month === 11) { month = 0; year++; } else { month++; }
```

**Right:**
```js
const next = new Date(year, month + 1, 1);          // rollover for free
const sameDay = (a, b) =>
  a.getFullYear() === b.getFullYear() &&
  a.getMonth() === b.getMonth() &&
  a.getDate() === b.getDate();
```

---

## 5. Skill: Off-by-one discipline (tie paired counts to one constant)

**Inject when:** slicing, pagination, "show N + overflow" patterns, truncation.

Haiku showed 3 dots (`slice(0, 3)`) but computed the overflow badge as `length - 2`, implying 5 events for 4. The slice count and the remainder must be the *same* number.

> **SKILL — When you slice a list and also report the remainder, both must reference ONE named constant. Never write the limit as a literal in one expression and a different adjusted literal in the other.**

**Wrong:**
```js
const shown = events.slice(0, 3);
const overflow = events.length - 2; // off by one vs. the slice
```

**Right:**
```js
const MAX_DOTS = 3;
const shown = events.slice(0, MAX_DOTS);
const overflow = Math.max(0, events.length - MAX_DOTS);
```

---

## 6. Skill: Add a type layer, even lightweight

**Inject when:** any non-trivial task in a JS/TS-capable stack.

Every Haiku bug lived in **untyped data** — the `events` shape and the `getDay()` offset had no contract for the model to check against. Opus used `strict` TypeScript with a typed, pure date module; the type system made "is this a Date or a day number?" a compile error instead of a runtime mystery.

> **SKILL — Introduce a type contract for any shared data shape. Prefer TypeScript with `strict`; if the project is plain JS, add PropTypes or a JSDoc `@typedef`. A typed `Event { date: Date; label: string }` turns whole classes of shape/units bugs into compile-time errors.**

**Inject template (TS):**
```ts
interface CalendarEvent { date: Date; label: string; }
function eventsOn(events: CalendarEvent[], day: Date): CalendarEvent[] { /* ... */ }
```
**Inject template (plain JS fallback):**
```js
/** @typedef {{ date: Date, label: string }} CalendarEvent */
Calendar.propTypes = { events: PropTypes.arrayOf(PropTypes.shape({
  date: PropTypes.instanceOf(Date).isRequired,
  label: PropTypes.string.isRequired,
})) };
```

---

## 7. Skill: Separate a pure logic layer from presentation

**Inject when:** any UI task with non-trivial logic (dates, sorting, filtering, formatting).

Opus isolated all date math into a pure, React-free `calendar.ts` (`addMonths`, `buildMonthMatrix`, `isSameDay`) and kept components presentational. This made the logic independently testable and kept bugs out of JSX. Haiku mixed 125 lines of grid math, event filtering, and rendering in one component, which is where its bugs hid.

> **SKILL — Put non-trivial logic in pure functions with no UI/framework imports, and unit-test those functions directly. Keep components thin: they receive computed data and render it. Pure functions are where you can afford airtight tests; mixed components are where bugs hide.**

**Inject structure:**
```
src/lib/calendar.ts   // pure: addMonths, buildMonthMatrix, isSameDay — no React
src/components/...     // presentational: receive matrix, render cells
```

---

## 8. Skill: Accessibility baseline for interactive UI

**Inject when:** any interactive component (this was the ONE weakness *both* models shared — so it's a reliable, high-value injection).

Both implementations shipped bare `<div>`s with no grid semantics and no keyboard navigation. Because *neither* model did this unprompted, an injected a11y skill is pure upside.

> **SKILL — For grid/list/table UIs, use semantic roles and keyboard support by default: `role="grid"` → `role="row"` → `role="gridcell"` (or a real `<table>`); every interactive control gets an accessible name; support arrow-key navigation and visible `:focus-visible` focus. Meet a 44×44px minimum touch target for anything tappable.**

Note: Haiku's nav buttons were ~32px tall — below the 44px target its own spec required. Inject the 44px rule explicitly; small models honor concrete numbers.

---

## 9. Skill: Honor scope — finish the spec, don't invent or under-wire

**Inject when:** spec-bounded tasks.

Both models correctly treated CRUD/persistence as out of scope — good. But Haiku built an *in-scope* feature (events) and left it unwired. The lesson for injection: **"in scope" means wired and working end-to-end, not merely present in a file.**

> **SKILL — Implement exactly what the spec lists as in-scope, fully wired end-to-end. Do not add out-of-scope features; do not count a feature "done" until it is reachable and functioning from the running app. A built-but-unwired feature scores as incomplete, not partial credit.**

---

## 10. Injection strategy notes for AgentAlloy

Operational guidance for *how* to inject, tuned to small-model behavior observed here:

1. **Concrete > abstract.** Small models acted on rules paired with wrong/right code pairs, and ignored abstract principles. Always inject the example, not just the maxim.
2. **Imperative voice, numbered, short.** "Do X. Not Y. Here's the pair." Avoid prose.
3. **Lead with the meta-skill (Section 0).** "Derive, don't duplicate" + "tests must fail on bugs" are the two highest-ROI injections; they generalize beyond calendars.
4. **Domain-trigger the date skill (Section 4).** Detect date/time/calendar keywords and inject Section 4 — it is the densest bug source and the clearest Opus/Haiku delta.
5. **Always append a verification coda.** Inject a closing instruction: *"Before finishing: (a) trace each feature from the app entry point and confirm data flows; (b) for each test, name the bug it would catch; (c) grep for any literal that appears twice."* This converts the skills into a self-check the model runs at the end — exactly the step Haiku skipped.
6. **Budget-aware.** If injection token budget is tight, prioritize: §0 meta → §2 tests → §1 SSOT → domain skill (§4) → §3 wiring. These four account for all four observed Haiku defects.
7. **Measure lift the same way.** Re-run the same A/B harness after injection and score on the same 7 categories (features, stack, code quality, completeness, correctness, polish, testing). The target metric is **Correctness** and **Testing** — those were Haiku's collapse points (4/10 and 6/10) and where injection should move the needle first.

---

## Appendix — Scorecard deltas this tuning targets

| Category | Haiku (baseline) | Opus (target) | Skills that close it |
|---|---:|---:|---|
| Correctness | 4 | 10 | §1, §4, §5 |
| Code quality | 6 | 9 | §6, §7 |
| Testing | 6 | 9 | §2 |
| Completeness | 8 | 7 | §3, §9 |
| Polish/UX | 7 | 7 | §8 |
| **Overall** | **6.0** | **8.0** | — |

Priority order of injection by expected lift: **§2 (tests) and §1 (SSOT) first** — together they address the every-month grid bug *and* the reason it shipped undetected, which is the single biggest quality gap between the two runs.
