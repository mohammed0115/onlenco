# Audit — Smart Tutor Voice/Avatar Gender Compatibility

> Read-only audit of `/subscriptions/preferences/` and related Smart-Tutor
> preference code. **No code, no migrations, no push.** Awaiting review.

**Product rule under audit:** male avatar ⇒ voice must not be female;
female avatar ⇒ voice must not be male; neutral avatar is compatible with
male/female unless a product setting later restricts it.

---

## 1. Current files involved

| Concern | File / symbol |
|---|---|
| Preferences view (page) | `subscriptions/views.py` → `preferences_page` (GET render + POST save) |
| Preferences view (JSON API) | `subscriptions/views.py` → `preference_api` (GET snapshot, POST update) |
| Save / business logic | `subscriptions/services/preference_service.py` → `set_preference`, `resolve_voice_for`, `resolve_avatar_for`, `preference_snapshot`, `_gender_mismatch`, `_voice_for_gender` |
| Stored preference model | `subscriptions/models.py` → `UserAIPreference` |
| Voice catalog model | `subscriptions/models.py` → `VoiceProfile` |
| Avatar catalog model | `subscriptions/models.py` → `AvatarProfile` |
| Template | `subscriptions/templates/subscriptions/preferences.html` |
| Existing tests | `subscriptions/tests/test_voice_avatar_preferences.py` |

## 2. The view handling tutor preferences

- `preferences_page` (`@login_required`): on **POST** calls
  `preference_service.set_preference(user, voice_code=..., avatar_code=..., speed=..., pitch=..., sound_effects_enabled=...)`, flashes "Preferences saved.", redirects. On **GET** lists active voices + avatars + `preference_snapshot` and renders the template.
- `preference_api`: JSON `POST` with `{voice_code, avatar_code, speed, pitch, sound_effects_enabled}` → same `set_preference`; returns `preference_snapshot`.

## 3. Form / validation logic, if any

- **No Django Form** is used; raw POST params are passed straight to `set_preference`.
- `set_preference` validates only that codes exist + are active, and that speed/pitch are valid choices. **There is NO voice↔avatar gender compatibility validation on save.** A male avatar + female voice will be persisted as-is.
- There IS *read-time* mitigation: `resolve_voice_for(user)` (used by the tutor/voice session) calls `_gender_mismatch(voice, avatar)` and, on mismatch, returns a gender-aligned voice via `_voice_for_gender(avatar.gender)`. So the **live session** already avoids a mismatched voice — but the **stored row** and the **preferences page/snapshot** still reflect the incompatible saved voice.

## 4. Source of available avatars/personalities

`AvatarProfile.objects.filter(is_active=True).order_by("sort_order", "name_en")` (in `preferences_page`). Seeded via management seed; managed in admin.

## 5. Source of available voices

`VoiceProfile.objects.filter(is_active=True).order_by("sort_order", "name_en")` (in `preferences_page`).

## 6. Do voices have explicit gender metadata?

**YES.** `VoiceProfile.voice_type` is a stored `CharField(choices=VOICE_TYPE_CHOICES, default="neutral")` with choices exactly `male / female / neutral`. This is the voice's gender — **no new field required**.

## 7. Do avatars/personalities have explicit gender metadata?

**YES.** `AvatarProfile.gender` is a stored `CharField(choices=GENDER_CHOICES, default="neutral")` with choices `male / female / neutral`. **No new field required.**

## 8. Is gender inferred from names/images or stored explicitly?

**Stored explicitly** on both models (`VoiceProfile.voice_type`, `AvatarProfile.gender`). The template displays them from the stored fields (`{{ v.get_voice_type_display }}`, `{{ a.get_gender_display }}`) — **no name/image inference anywhere.** This satisfies the "do not infer from names" requirement already.

## 9. Template rendering the avatar/voice cards

`subscriptions/templates/subscriptions/preferences.html`:
- Voice cards: `<input type="radio" name="voice_code" value="{{ v.code }}">` + shows `voice_type · style · tone`. **No `data-*` gender attribute, no JS.**
- Avatar cards: `<input type="radio" name="avatar_code" value="{{ a.code }}">` + shows `gender`. **No `data-*` gender attribute, no JS.**
- Single `<form method="post">`; inline styles; RTL via the global layout. Messages block already present.

## 10. Save endpoint / POST handling

Two entry points, both → `set_preference` (no gender gate):
- `POST /subscriptions/preferences/` (form).
- `POST` JSON to the preference API (`preference_api`).

## 11. Existing tests for tutor preferences

`subscriptions/tests/test_voice_avatar_preferences.py` covers: catalog seeding, `resolve_voice_for`/`resolve_avatar_for` defaults + inactive fallback, `set_preference` (set voice/avatar/speed/pitch, invalid codes ignored), page render, API get/post, admin catalog. **None assert voice↔avatar gender compatibility** (no test that a male avatar rejects a female voice).

## 12. Risk of breaking existing saved preferences

- Some `UserAIPreference` rows may already store an incompatible pair (e.g. male avatar + female voice). The live session is already safe (read-time realignment), but a strict save-time rule + a page-load auto-correction will **change the stored voice** for those users.
- Mitigation: auto-correct by switching only the VOICE to the nearest compatible default (same gender as the avatar, else neutral), never block the user, and log the change. Never change the avatar (the user's identity choice).
- `speed`, `pitch`, `sound_effects_enabled` are unaffected.

---

## Current data shape

**VoiceProfile** (catalog): `code`, `name_en/ar`, `provider_voice_id`, **`voice_type` ∈ {male,female,neutral}**, `style`, `accent`, `tone`, `preview_audio_url`, `is_active`, `sort_order`.

**AvatarProfile** (catalog): `code`, `name_en/ar`, **`gender` ∈ {male,female,neutral}**, `style`, `image_url`/`image_file` (+ `effective_image_url`), `lipsync_video_url`, `is_active`, `sort_order`.

**UserAIPreference** (per-user): `user` (OneToOne), `voice_profile` (FK), `avatar_profile` (FK), `speed`, `pitch`, `sound_effects_enabled`.

## Current save flow

`POST → preferences_page / preference_api → set_preference()` → sets `voice_profile` / `avatar_profile` (existence+active only) → save. **No compatibility check.** Page GET → `preference_snapshot()` returns stored values verbatim (no correction).

## Current gaps

1. **No backend save-time validation** of voice↔avatar gender → an incompatible pair can be persisted (form or API).
2. **No frontend** disabling/hiding of incompatible voice cards; no auto-switch; no friendly message.
3. **No single public source-of-truth function** (logic is split between `_gender_mismatch` + `_voice_for_gender`, and only applied at read-time).
4. **`preference_snapshot` does not self-heal** an already-saved invalid pair, so the page can show a mismatched voice as "selected".
5. **No tests** for the compatibility rule.
6. **No `data-*` metadata** on cards for the UI to reason about gender.

## Safe implementation plan (proposed — not yet implemented)

**Backend (source of truth, applies to BOTH form + API):**
- Add `preference_service.is_voice_compatible_with_avatar(voice_gender, avatar_gender)`:
  male→{male,neutral}; female→{female,neutral}; neutral→neutral always, others gated by a setting `PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES` (default True). Refactor `_gender_mismatch` to call it.
- Add `default_voice_for_avatar(avatar)` (prefer same gender → neutral → any compatible).
- `set_preference`: if the resulting (avatar, voice) is incompatible: **reject** when the voice was explicitly picked (`raise IncompatibleVoiceError`); **auto-switch** the voice to a compatible default when only the avatar changed.
- Add `correct_incompatible_preference(user)` (persist + log) and call it at the top of `preference_snapshot` to heal legacy rows on page load.
- `preferences_page` / `preference_api`: catch `IncompatibleVoiceError` → friendly message
  AR: "هذا الصوت غير متوافق مع الشخصية المختارة." / EN: "This voice is not compatible with the selected avatar."

**Frontend (`preferences.html` + small inline JS):**
- Add `data-voice-gender="{{ v.voice_type }}"` to voice cards and `data-gender="{{ a.gender }}"` to avatar cards (explicit stored metadata, no inference).
- On avatar change: disable/dim incompatible voice cards; if the selected voice becomes incompatible, auto-select the best compatible voice (or clear) and show the friendly message. Keep RTL + existing design.

**Settings:** add `PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES` (env-bool, default True).

## Whether a migration is needed

**No schema migration required.** Both gender fields already exist (`VoiceProfile.voice_type`, `AvatarProfile.gender`). The work is service + view + template + a settings flag + tests. (A data backfill is *not* a schema migration; legacy invalid pairs are healed lazily on save/page-load via `correct_incompatible_preference`, optionally a one-off management command if a bulk sweep is preferred.)

## Proposed tests (`subscriptions`)

1. Male avatar + female voice → **rejected** (save raises / API 4xx, nothing persisted).
2. Male avatar + male voice → accepted.
3. Male avatar + neutral voice → accepted.
4. Female avatar + male voice → **rejected**.
5. Female avatar + female voice → accepted.
6. Female avatar + neutral voice → accepted.
7. Neutral avatar behavior follows `PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES` (allow-all vs neutral-only).
8. Changing avatar to male auto-switches an existing female voice to a compatible default (no error path).
9. Legacy invalid saved pair is auto-corrected on `preference_snapshot` (page load).
10. Valid preferences still save successfully end-to-end (form + API).
11. (UI) template exposes `data-voice-gender` / `data-gender` so the JS can disable incompatible voices.

## Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Legacy rows (male avatar + female voice) silently changed | Low–Med | Switch only the VOICE to nearest compatible; never touch avatar; log every correction |
| Rejecting an API save breaks an existing client flow | Low | Reject only when the voice is *explicitly* incompatible; auto-switch on avatar-only change so normal flows don't error |
| Neutral-avatar policy too strict/loose | Low | Behind the `PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES` setting (default permissive) |
| Breaking the live tutor session | Very low | `resolve_voice_for` already realigns; new rule is consistent with it |
| Schema risk | None | No migration (fields already exist) |

---

**Status:** audit complete. No code/migrations/push performed. Awaiting your review before implementing the plan above.
