import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0002_cacheable"),
    ]

    operations = [
        migrations.CreateModel(
            name="CollectionBook",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.PositiveIntegerField(default=0)),
                ("collection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="collection_books", to="books.collection")),
                ("book", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="collection_books", to="books.book")),
            ],
            options={
                "ordering": ["order"],
                "unique_together": {("collection", "book")},
            },
        ),
        migrations.AddField(
            model_name="collection",
            name="books",
            field=models.ManyToManyField(related_name="collections", through="books.CollectionBook", to="books.book"),
        ),
    ]