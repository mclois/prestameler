from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0006_remove_book_language_edition_language"),
    ]

    operations = [
        migrations.RenameField(
            model_name="collection",
            old_name="filter_config",
            new_name="filter_config_raw",
        ),
        migrations.AlterField(
            model_name="collection",
            name="filter_config_raw",
            field=models.JSONField(default=dict, db_column="filter_config"),
        ),
        migrations.RenameField(
            model_name="facet",
            old_name="filter_config",
            new_name="filter_config_raw",
        ),
        migrations.AlterField(
            model_name="facet",
            name="filter_config_raw",
            field=models.JSONField(default=dict, db_column="filter_config"),
        ),
    ]