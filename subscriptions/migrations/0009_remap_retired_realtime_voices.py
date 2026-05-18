"""Remap retired Beta voices to GA-supported ones on VoiceProfile.

The OpenAI Realtime GA migration retired ``nova``, ``onyx``, ``fable``
on ``/v1/realtime/client_secrets`` (the new endpoint that replaced the
Beta ``/v1/realtime/sessions``). Sessions opened with those voice IDs
now return HTTP 400 ``invalid_value``.

We swap the ``provider_voice_id`` to a closest-personality GA voice so
existing user preferences continue to work without manual re-selection.
Display names + style metadata are left untouched — the swap is purely
on the upstream identifier.
"""
from django.db import migrations


REMAP = {
    "nova":  "shimmer",   # warm female → closest GA female
    "onyx":  "ash",       # deep male   → closest GA deep male
    "fable": "ballad",    # soft narrator → closest GA storyteller
}


def remap(apps, schema_editor):
    Voice = apps.get_model("subscriptions", "VoiceProfile")
    for old_id, new_id in REMAP.items():
        Voice.objects.filter(provider_voice_id=old_id).update(provider_voice_id=new_id)


def unremap(apps, schema_editor):
    """Reverse: restore the Beta voice IDs. (Rare — keeps migration replayable.)"""
    Voice = apps.get_model("subscriptions", "VoiceProfile")
    for old_id, new_id in REMAP.items():
        Voice.objects.filter(provider_voice_id=new_id).update(provider_voice_id=old_id)


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0008_avatarprofile_image_file"),
    ]
    operations = [
        migrations.RunPython(remap, reverse_code=unremap),
    ]
