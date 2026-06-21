from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0001_initial"),
    ]

    operations = [
        # Book
        migrations.RemoveField("Book", "tags"),
        migrations.AlterField("Book", "cached_at", models.DateTimeField(auto_now=True)),
        migrations.AlterField("Book", "cache_ttl", models.PositiveIntegerField()),
        migrations.AddField("Book", "source", models.CharField(db_index=True, default="", max_length=50)),
        migrations.AddField("Book", "rating", models.FloatField(blank=True, null=True)),
        migrations.AlterUniqueTogether("Book", {("external_id", "source")}),
        migrations.AlterField("Book", "source", models.CharField(db_index=True, max_length=50)),

        # Collection
        migrations.RemoveField("Collection", "tags"),
        migrations.AlterField("Collection", "cached_at", models.DateTimeField(auto_now=True)),
        migrations.AlterField("Collection", "cache_ttl", models.PositiveIntegerField()),
        migrations.AddField("Collection", "source", models.CharField(db_index=True, default="", max_length=50)),
        migrations.AlterUniqueTogether("Collection", {("external_id", "source")}),
        migrations.AlterField("Collection", "source", models.CharField(db_index=True, max_length=50)),

        # Edition
        migrations.RemoveField("Edition", "tags"),
        migrations.AlterField("Edition", "cached_at", models.DateTimeField(auto_now=True)),
        migrations.AlterField("Edition", "cache_ttl", models.PositiveIntegerField()),
        migrations.AddField("Edition", "source", models.CharField(db_index=True, default="", max_length=50)),
        migrations.AlterUniqueTogether("Edition", {("isbn", "source")}),
        migrations.AlterField("Edition", "source", models.CharField(db_index=True, max_length=50)),
    ]