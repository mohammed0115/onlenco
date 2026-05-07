# 13. Prompt — دعم عربي/إنجليزي احترافي i18n + RTL/LTR

```text
You are a senior Django i18n engineer.

Audit and improve Arabic/English support in Onlenco.

Goal:
The platform must support Arabic and English professionally, including translations and RTL/LTR layout.

Tasks:
1. Inspect all templates, views, forms, and static text.
2. Find hardcoded Arabic or English strings.
3. Convert strings to Django translation system using:
   - {% trans %}
   - {% blocktrans %}
   - gettext_lazy
4. Make layout direction dynamic:
   - dir="rtl" for Arabic
   - dir="ltr" for English
5. Ensure buttons, forms, cards, navigation, and dashboards work in both languages.
6. Update translation files.
7. Compile messages.
8. Add tests for language switching.
9. Fix any broken alignment in RTL/LTR.

Constraints:
- Do not remove current language switch behavior unless replacing it with better implementation.
- Do not hardcode Arabic inside JavaScript if avoidable.
- Avoid duplicated translation logic.

Validation:
python manage.py makemessages -l ar
python manage.py makemessages -l en
python manage.py compilemessages
python manage.py test
python manage.py check

Output:
- List of translated templates/files
- Remaining untranslated strings if any
- RTL/LTR fixes
```
