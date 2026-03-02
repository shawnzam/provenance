from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_notes_fts"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReadingItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.URLField(max_length=2000, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=300, unique=True)),
                ("title", models.CharField(blank=True, max_length=500)),
                ("summary", models.TextField(blank=True, help_text="AI-generated summary")),
                ("notes", models.TextField(blank=True, help_text="Your own notes on this article")),
                ("tags", models.CharField(blank=True, help_text="Comma-separated tags", max_length=500)),
                ("status", models.CharField(
                    choices=[("to_read", "To Read"), ("read", "Read"), ("archived", "Archived")],
                    default="to_read",
                    max_length=20,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
