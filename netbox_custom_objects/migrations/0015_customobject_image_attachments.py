"""
Data migration: list the 'image_attachments' feature on every existing
CustomObjectType's ObjectType.

CustomObject now subclasses ImageAttachmentsMixin, so newly created Custom Object
Types pick up 'image_attachments' automatically (create_model() recomputes the
feature list from the model's mixins).  Custom Object Types created before this
change carry a stale ObjectType.features array; refresh them so they appear in the
object-type filter on NetBox's global Image Attachments list.

Image attachment validation itself (ImageAttachment.clean()) resolves the feature
from the model class via issubclass(), so attaching images already works without
this migration; this only keeps the persisted features array accurate.

Idempotent: skips object types that already list the feature.  The reverse
migration is a no-op (leaving the feature listed is harmless).
"""

from django.db import migrations


def add_image_attachments_feature(apps, schema_editor):
    CustomObjectType = apps.get_model("netbox_custom_objects", "CustomObjectType")
    for cot in CustomObjectType.objects.select_related("object_type").all():
        object_type = cot.object_type
        if object_type is None or "image_attachments" in object_type.features:
            continue
        object_type.features = [*object_type.features, "image_attachments"]
        object_type.save(update_fields=["features"])


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_custom_objects", "0014_fix_mixed_case_field_names"),
    ]

    operations = [
        migrations.RunPython(add_image_attachments_feature, migrations.RunPython.noop),
    ]
