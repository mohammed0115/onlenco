# Onlenco Design Tokens Audit (Phase 1)

> **Status**: documentation-only. No CSS / template / settings changes
> made in this commit. This audit is the foundation for Phase 2
> (unified token layer in `static/css/onlenco-tokens.css`).
>
> **Scope**: Catalogue every design-token (color, spacing, radius,
> shadow, typography, transition) currently used across the codebase,
> show where each lives, where they disagree, and recommend the single
> set that Phase 2 will canonicalise.

---

## 1. The three CSS systems running in parallel today

| Layer | File | Lines | Token prefix | Style |
|---|---|---:|---|---|
| Student UI | [`static/css/onlenco.css`](../static/css/onlenco.css) | 314 | `--*` (no prefix) | HSL via CSS vars, Tailwind-compatible |
| Platform Admin | [`platform_admin/static/platform_admin/css/control.css`](../platform_admin/static/platform_admin/css/control.css) | 393 | `--cc-*` | HEX literals |
| Teacher Portal | [`teacher_portal/static/teacher_portal/css/teacher.css`](../teacher_portal/static/teacher_portal/css/teacher.css) | 436 | `--tp-*` | HEX literals (same values as `--cc-*`) |
| AI Tutor (voice page) | [`static/css/ai_tutor_voice.css`](../static/css/ai_tutor_voice.css) | 532 | inline `hsl()` literals | mixed |
| AI Tutor (realtime) | [`static/css/ai_tutor_realtime.css`](../static/css/ai_tutor_realtime.css) | 372 | inline `hsl()` literals | mixed |

**Observation**: Student-facing CSS lives on a deliberately-warm
teal/amber identity. Admin + Teacher live on a generic Material-style
blue/green. AI Tutor doesn't define tokens at all — it inlines colours.

---

## 2. Color tokens — side-by-side

### Student UI (`onlenco.css`)

The "real" Onlenco brand. HSL space, plays well with Tailwind via
`hsl(var(--primary))`.

| Variable | Value (HSL) | Approx HEX | Role |
|---|---|---|---|
| `--background` | `36 38% 97%` | `#F9F7F1` | page bg — warm cream |
| `--foreground` | `178 45% 10%` | `#0E2625` | body text — deep teal-black |
| `--card` | `0 0% 100%` | `#FFFFFF` | card surface |
| `--popover` | `0 0% 100%` | `#FFFFFF` | popover surface |
| **`--primary`** | **`178 65% 18%`** | **`#0F4E4B`** | **brand teal — "Nile depth"** |
| `--primary-foreground` | `36 38% 97%` | `#F9F7F1` | text on primary |
| `--primary-glow` | `178 55% 35%` | `#288F8A` | hover/focus glow |
| **`--secondary`** | **`28 85% 58%`** | **`#EC983A`** | **brand amber — "Sudanese sunset"** |
| `--secondary-foreground` | `178 45% 10%` | `#0E2625` | text on amber |
| `--muted` | `36 25% 92%` | `#EAE4DB` | subtle bg |
| `--muted-foreground` | `178 15% 38%` | `#566F6D` | secondary text |
| `--accent` | `14 80% 60%` | `#E96A45` | warm coral accent |
| `--destructive` | `0 75% 50%` | `#DF2020` | errors / delete |
| `--border` | `36 20% 88%` | `#DED7CC` | hairlines |
| `--input` | `36 20% 90%` | `#E3DDD2` | form input bg |
| `--ring` | `178 65% 18%` | `#0F4E4B` | focus ring (= primary) |
| `--radius` | `1rem` | — | base radius |

### Platform Admin (`control.css`)

| Variable | HEX | Role |
|---|---|---|
| `--cc-primary` | `#2563eb` | primary action (Material blue 600) |
| `--cc-secondary` | `#10b981` | success / emerald |
| `--cc-accent` | `#fbbf24` | warning / amber |
| `--cc-bg` | `#f8fafc` | page bg (slate-50) |
| `--cc-surface` | `#ffffff` | card surface |
| `--cc-text` | `#0f172a` | body text (slate-900) |
| `--cc-muted` | `#64748b` | secondary text (slate-500) |
| `--cc-border` | `#e2e8f0` | hairlines (slate-200) |

### Teacher Portal (`teacher.css`)

| Variable | HEX | Role |
|---|---|---|
| `--tp-primary` | `#2563EB` | **same as `--cc-primary` (case-only differ)** |
| `--tp-secondary` | `#10B981` | **same as `--cc-secondary`** |
| `--tp-accent` | `#FBBF24` | **same as `--cc-accent`** |
| `--tp-bg` | `#F8FAFC` | **same as `--cc-bg`** |
| `--tp-surface` | `#FFFFFF` | **same as `--cc-surface`** |
| `--tp-text` | `#0F172A` | **same as `--cc-text`** |
| `--tp-muted` | `#64748B` | **same as `--cc-muted`** |
| `--tp-border` | `#E2E8F0` | **same as `--cc-border`** |

**Observation**: 100% duplication between admin and teacher CSS, just
with a different prefix. There's no reason for two copies — Phase 2
collapses them into one `--ink-*` / `--surface-*` neutral scale.

### AI Tutor

No `--vars` defined. Top inline HSL literals across both files:

| Approx HSL | Where (representative) |
|---|---|
| `hsl(178 65% 18%)` | matches student `--primary` ✓ |
| `hsl(28 85% 58%)` | matches student `--secondary` ✓ |
| `hsl(0 70% 35%)` | red destructive variant — close to `--destructive` |
| `hsl(160 50% 96%)` | mint highlight — not in any token system |
| `hsl(220 25% 25%)` | dark slate — not in any token system |

**Observation**: AI Tutor's main brand colours already match Student
UI, but the secondary palette (mint, slate, blue) is invented per-file.

---

## 3. The disagreement (visual proof)

| Pair | Student says | Admin/Teacher says |
|---|---|---|
| Primary | `#0F4E4B` deep teal | `#2563EB` Material blue |
| Secondary | `#EC983A` warm amber | `#10B981` emerald green |
| Background | `#F9F7F1` cream | `#F8FAFC` slate-tinted white |
| Foreground | `#0E2625` teal-black | `#0F172A` slate-black |
| Border | `#DED7CC` warm taupe | `#E2E8F0` cool slate |

> **Same brand, two completely different colour identities depending
> on which view a user lands on.** A teacher logging in sees a generic
> SaaS dashboard; a student sees Onlenco's real brand. Phase 2 picks
> one — the Student UI palette is the brand and wins.

---

## 4. Radii inventory

| Value | Count | Used for |
|---|---:|---|
| `9999px` / `border-radius:9999px` | 16 | pill buttons, badges, rings |
| `8px` | 14 | cards, inputs, table cells (admin/teacher) |
| `999px` | 4 | pills (variant of 9999) |
| `50%` | 2 | circular avatars |
| `1rem` | 2 | onlenco.css `--radius` and a card |

**Recommendation** (Phase 2 scale):

```
--radius-sm:   6px    (inputs, table cells, small chips)
--radius-md:   12px   (cards, modals, dialogs)
--radius-lg:   16px   (hero cards, feature panels)        ← matches existing 1rem
--radius-pill: 9999px (badges, pill buttons)
--radius-full: 50%    (avatars, circular icon buttons)
```

Maps cleanly: `9999px → --radius-pill` (20 sites), `8px → --radius-sm`
(14 sites), `1rem / 16px → --radius-lg` (existing `--radius` token).

---

## 5. Spacing inventory

Most-used gap values across the project:

| Value | Count | Suggested token |
|---|---:|---|
| `12px` | 9 | `--space-3` |
| `10px` | 6 | `--space-2.5` (or normalise to 8/12) |
| `6px` | 5 | `--space-1.5` |
| `8px` | 4 | `--space-2` |
| `16px` | 4 | `--space-4` |
| `4px` | 2 | `--space-1` |
| `18px` | 2 | normalise → `16px` `--space-4` |
| `14px` | 1 | normalise → `12px` `--space-3` |

Most-used padding values:

| Value | Count | Suggested token |
|---|---:|---|
| `18px` | 4 | normalise → `16px` `--space-4` |
| `10px 12px` | 3 | inputs |
| `16px` | 2 | cards |
| `6px 10px` | 2 | small buttons |
| `12px` | 2 | table cells |

**Recommendation**: 4px base scale.

```
--space-0:  0
--space-1:  4px
--space-2:  8px
--space-3:  12px
--space-4:  16px
--space-5:  20px
--space-6:  24px
--space-8:  32px
--space-10: 40px
--space-12: 48px
```

Phase 2 will round non-conforming values (10, 14, 18, 22) to the nearest
slot — most of those are accidental rather than intentional.

---

## 6. Font / typography inventory

Defined in [`templates/base.html:15-16`](../templates/base.html#L15-L16):

```
Plus Jakarta Sans  (latin UI)
Fraunces          (display / headings, latin)
Cairo             (Arabic UI + display)
```

Applied at:

| Selector | Font | File:line |
|---|---|---|
| `body` (default) | Plus Jakarta Sans | [onlenco.css:59](../static/css/onlenco.css#L59) |
| `[dir="rtl"] body` | Cairo | [onlenco.css:64](../static/css/onlenco.css#L64) |
| `[dir="rtl"] .font-display` | Cairo | [onlenco.css:65](../static/css/onlenco.css#L65) |
| `.font-display` (LTR) | Fraunces | [onlenco.css:68](../static/css/onlenco.css#L68) |
| `[dir="rtl"] .onlenco-toast` | Cairo | [ai_tutor_voice.css:175](../static/css/ai_tutor_voice.css#L175) |
| `[dir="rtl"] .onlenco-call-sub` | Cairo | [ai_tutor_realtime.css:248](../static/css/ai_tutor_realtime.css#L248) |

`control.css` and `teacher.css` declare **no font-family at all**,
so they inherit from `<body>` — which means admin + teacher follow the
student UI font choice by accident. Fine for now; should be explicit
once tokens are unified.

### Font-size literals in the wild

Most-used (excluding Tailwind classes):

| Value | Count |
|---|---:|
| `.85rem` (~13.6px) | 7 |
| `14px` | 6 |
| `.8rem` (~12.8px) | 4 |
| `.9rem` (~14.4px) | 3 |
| `.95rem` (~15.2px) | 3 |
| `.7rem` (~11.2px) | 3 |
| `13px` | 3 |
| `0.78rem` (~12.5px) | 3 |
| `.75rem` (~12px) | 2 |
| `1rem` (~16px) | 4 |

**Recommendation**: 7-step type scale (Tailwind-compatible).

```
--text-xs:   12px / 16px line-height   (.7rem and .75rem → here)
--text-sm:   14px / 20px                (.85rem, 13px, .8rem, 0.78rem → here)
--text-base: 16px / 24px                (1rem)
--text-lg:   18px / 28px                (.95rem → here)
--text-xl:   20px / 28px
--text-2xl:  24px / 32px
--text-3xl:  30px / 36px                (hero / display)
```

Plus `font-weight` tokens (`--font-regular`, `--font-medium`,
`--font-semibold`, `--font-bold`). Today the project uses Tailwind's
`font-bold` (112 sites) and `font-semibold` (90 sites) heavily so the
weight scale already exists implicitly; we just declare it.

---

## 7. Shadow inventory

Defined in `onlenco.css`:

| Variable | Value | Use |
|---|---|---|
| `--shadow-soft` | `0 2px 8px -2px hsl(178 65% 18% / 0.08)` | card hover lift |
| `--shadow-elegant` | `0 20px 50px -20px hsl(178 65% 18% / 0.25)` | hero card / modal |
| `--shadow-glow` | `0 0 60px hsl(28 85% 58% / 0.35)` | accent glow (auth, CTA) |

`control.css` / `teacher.css` don't define shadow tokens. The AI Tutor
CSS uses one-off `box-shadow` literals (8 occurrences) for the mic-pulse
animation — those are component-specific, not part of the design system.

**Recommendation**: keep the existing 3 as `--shadow-sm` (= soft),
`--shadow-md` (new mid step), `--shadow-lg` (= elegant), and rename
`--shadow-glow` → `--shadow-accent-glow` for clarity.

```
--shadow-sm:   0 1px 2px hsl(var(--ink) / .04)
--shadow-md:   0 2px 8px -2px hsl(var(--ink) / .08)       (= --shadow-soft)
--shadow-lg:   0 20px 50px -20px hsl(var(--ink) / .25)    (= --shadow-elegant)
--shadow-xl:   0 25px 60px -20px hsl(var(--ink) / .35)
--shadow-accent-glow: 0 0 60px hsl(var(--accent) / .35)
```

---

## 8. Gradients

`onlenco.css` defines four:

| Variable | Definition | Used at |
|---|---|---|
| `--gradient-hero` | teal → teal-light → amber | hero cards, landing |
| `--gradient-sunset` | amber → coral | feature cards, CTAs |
| `--gradient-card` | white → cream | card backgrounds |
| `--gradient-text` | teal → amber | display text fill |

**Recommendation**: keep all four. They are intentional brand
expressions, used consistently in Student UI. Phase 2 simply ensures
admin / teacher / AI tutor pages can reach for them by the same token
name instead of inventing their own.

---

## 9. Transitions

Only one defined: `--transition-smooth: cubic-bezier(0.4, 0, 0.2, 1)`
([onlenco.css:51](../static/css/onlenco.css#L51)). Used 5+ times via
Tailwind's `transition-smooth` extension.

**Recommendation**:

```
--ease-out:   cubic-bezier(0.4, 0, 0.2, 1)    (=current --transition-smooth)
--ease-in:    cubic-bezier(0.4, 0, 1, 1)
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1)
--duration-fast:    120ms
--duration-base:    200ms
--duration-slow:    400ms
```

---

## 10. Inline-style hotspots

229 total `style="..."` attributes across templates:

| Area | Count | Worst file |
|---|---:|---|
| `templates/` (Student/main) | 147 | `lessons/dashboard.html` (24 uses) |
| `platform_admin/templates/` | 70 | scattered (admin grid containers) |
| `teacher_portal/templates/` | 9 | low |
| `daily_learning/templates/` | 3 | low |

Most-repeated inline-style patterns:

| Pattern (N = numeric) | Count | Phase 2 replacement |
|---|---:|---|
| `style="opacity:N.N"` | 22 | utility class `.opacity-{N}` |
| `style="background: rgba(N,N,N,N.N);"` | 6 | token-backed bg utility |
| `style="height:N.Nrem;padding:N N.Nrem"` | 5 | size-aware button variant |
| `style="width: {{ v.pct }}%"` | 4 | **legit dynamic** — keep |
| `style="max-width:Nrem"` | 4 | `--container-{narrow/wide}` |
| `style="color: hsl(var(--destructive))"` | 4 | `.text-destructive` utility |
| `style="border-color: hsl(var(--destructive)); background: hsl(N N% N%);"` | 3 | `.alert-danger` component |
| `style="margin-bottom:Npx"` | 3 | `mb-N` token |
| `style="display:none"` | 2 | `hidden` attr or `.hidden` class |

> **Inline-style policy for Phase 2 onward**:
> - Static styling → always a class (component or utility).
> - **Dynamic values** (progress bars `width: {{ v.pct }}%`, chart inline
>   metrics) → still inline; these are data, not design.
> - Anything matching `style="color:..."`, `style="background:..."`,
>   `style="margin:..."`, `style="padding:..."` is a refactor candidate.

---

## 11. Tailwind utility usage (top 20)

Grepped from all templates:

| Utility | Count |
|---|---:|
| `text-muted-foreground` | 247 |
| `text-sm` | 183 |
| `font-bold` | 112 |
| `font-display` | 109 |
| `w-4` | 108 |
| `h-4` | 108 |
| `text-xs` | 99 |
| `font-semibold` | 90 |
| `bg-muted` | 79 |
| `gap-3` | 62 |
| `p-5` | 48 |
| `gap-2` | 48 |
| `p-6` | 44 |
| `gap-4` | 42 |
| `w-5` | 39 |
| `h-5` | 39 |
| `text-center` | 37 |
| `h-screen` | 36 |
| `w-full` | 34 |
| `text-primary-foreground` | 33 |

**Observation**: the project is **already mostly Tailwind-driven** in
templates. Phase 2's job is to make sure Tailwind's `text-primary`,
`bg-primary`, `border-border` etc. resolve to the same token values
across **every** page — today they only work inside `templates/`
(because the Tailwind config in `base.html` reads `--primary` from
`onlenco.css`, which isn't loaded as a CSS source in admin/teacher
pages, but `base.html` IS the parent template so it still applies).

---

## 12. Recommended unified token set (preview for Phase 2)

This is the **target shape** of `static/css/onlenco-tokens.css`:

```css
:root {
  /* ---- Brand ---- */
  --brand-teal-50:  178 60% 95%;
  --brand-teal-100: 178 60% 88%;
  --brand-teal-300: 178 55% 50%;
  --brand-teal-500: 178 60% 28%;
  --brand-teal-700: 178 65% 18%;    /* = --primary */
  --brand-teal-900: 178 70% 10%;

  --brand-amber-50:  28 90% 96%;
  --brand-amber-100: 28 88% 90%;
  --brand-amber-300: 28 85% 70%;
  --brand-amber-500: 28 85% 58%;    /* = --secondary */
  --brand-amber-700: 28 75% 45%;
  --brand-amber-900: 14 80% 30%;

  /* ---- Semantic (theme-aware) ---- */
  --background: var(--brand-teal-50);     /* approximate; fine-tuned in Phase 2 */
  --foreground: var(--brand-teal-900);
  --card:       0 0% 100%;
  --primary:    var(--brand-teal-700);
  --primary-foreground: var(--background);
  --secondary:  var(--brand-amber-500);
  --secondary-foreground: var(--brand-teal-900);
  --accent:     14 80% 60%;
  --destructive: 0 75% 50%;
  --warning:    38 90% 50%;
  --success:    158 65% 38%;
  --info:       210 75% 50%;
  --muted:      36 25% 92%;
  --muted-foreground: 178 15% 38%;
  --border:     36 20% 88%;
  --input:      36 20% 90%;
  --ring:       var(--primary);

  /* ---- Surfaces (neutral scale) ---- */
  --ink:        178 45% 10%;
  --ink-soft:   178 15% 38%;
  --surface:    0 0% 100%;
  --surface-2:  36 30% 98%;
  --surface-3:  36 25% 95%;

  /* ---- Spacing ---- */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px; --space-8: 32px; --space-10: 40px; --space-12: 48px;

  /* ---- Radius ---- */
  --radius-sm: 6px; --radius-md: 12px; --radius-lg: 16px;
  --radius-pill: 9999px; --radius-full: 50%;

  /* ---- Typography ---- */
  --text-xs: 12px; --text-sm: 14px; --text-base: 16px;
  --text-lg: 18px; --text-xl: 20px; --text-2xl: 24px; --text-3xl: 30px;
  --font-regular: 400; --font-medium: 500; --font-semibold: 600; --font-bold: 700;
  --leading-tight: 1.25; --leading-normal: 1.5; --leading-relaxed: 1.7;

  /* ---- Shadow ---- */
  --shadow-sm: 0 1px 2px hsl(var(--ink) / .04);
  --shadow-md: 0 2px 8px -2px hsl(var(--ink) / .08);
  --shadow-lg: 0 20px 50px -20px hsl(var(--ink) / .25);
  --shadow-xl: 0 25px 60px -20px hsl(var(--ink) / .35);
  --shadow-accent-glow: 0 0 60px hsl(var(--secondary) / .35);

  /* ---- Motion ---- */
  --ease-out: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 120ms;
  --duration-base: 200ms;
  --duration-slow: 400ms;

  /* ---- Z-index scale ---- */
  --z-base: 0; --z-overlay: 100; --z-modal: 1000; --z-toast: 2000;

  /* ---- Gradients (unchanged, just centralised) ---- */
  --gradient-hero:    linear-gradient(135deg, hsl(178 65% 18%) 0%, hsl(178 55% 28%) 50%, hsl(28 75% 45%) 100%);
  --gradient-sunset:  linear-gradient(135deg, hsl(28 85% 58%) 0%, hsl(14 80% 60%) 100%);
  --gradient-card:    linear-gradient(180deg, hsl(0 0% 100%) 0%, hsl(36 30% 97%) 100%);
  --gradient-text:    linear-gradient(135deg, hsl(178 65% 18%), hsl(28 80% 45%));
}

[data-theme="dark"] {
  /* Phase 2 may stub these so a future dark-mode toggle has hooks. */
  --background: 178 45% 8%;
  --foreground: 36 30% 95%;
  --card: 178 40% 12%;
  --border: 178 25% 22%;
  --muted: 178 25% 18%;
}
```

### Migration mapping (Phase 2 will do this in code)

| Old token (admin/teacher) | New token | Notes |
|---|---|---|
| `--cc-primary` `#2563eb` | `--primary` (was teal) | **Brand decision**: drop the blue, use Onlenco teal everywhere |
| `--cc-secondary` `#10b981` | `--success` `#34A56F` | Repurpose: it was used as "success" semantically |
| `--cc-accent` `#fbbf24` | `--warning` `#F5B400` | Repurpose: it was used as warning/highlight |
| `--cc-bg` `#f8fafc` | `--background` (teal-tinted cream) | Match Student UI |
| `--cc-surface` `#ffffff` | `--surface` | Same |
| `--cc-text` `#0f172a` | `--foreground` | Slightly warmer |
| `--cc-muted` `#64748b` | `--muted-foreground` | Slightly warmer |
| `--cc-border` `#e2e8f0` | `--border` | Slightly warmer |
| `--tp-*` (all 8) | (delete file's `:root`) | Inherit from `--cc-*`-replaced tokens |

---

## 13. What this audit does NOT change

- ❌ No CSS file edited
- ❌ No template edited
- ❌ No settings edited
- ❌ No `base.html` edited
- ✅ Single new file: `Docs/design-tokens-audit.md` (this document)
- ✅ Existing Phase A–C and admin pages stay exactly as they are

---

## 14. Sign-off checklist for Phase 1

- [x] Catalogued every `--var` defined in every CSS file under the project
- [x] Catalogued every literal colour/radius/font/spacing value used >1×
- [x] Identified all 229 inline-style attributes by pattern
- [x] Counted Tailwind utility usage for top-20 classes
- [x] Mapped admin/teacher tokens to their student-UI equivalents
- [x] Proposed unified token shape for Phase 2
- [x] No code changed, no runtime risk

**Phase 2 starts when the user approves this audit.** Phase 2's
deliverable: `static/css/onlenco-tokens.css` + minimal change to
`templates/base.html` to load it before any other stylesheet, plus a
new kitchen-sink page at `/dev/tokens/` (dev-only) that previews every
token so future regressions are visible.
