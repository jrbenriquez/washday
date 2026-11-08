from django.db import migrations, models
from django.utils import timezone


def preserve_existing_shops(apps, schema_editor):
    apps.get_model("core", "Shop").objects.using(schema_editor.connection.alias).update(
        onboarding_completed_at=timezone.now()
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0008_branch_hub_url")]
    operations = [
        migrations.AddField(
            model_name="shop",
            name="onboarding_completed_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.RunPython(preserve_existing_shops, migrations.RunPython.noop),
    ]
