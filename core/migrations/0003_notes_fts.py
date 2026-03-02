from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_document"),
    ]

    operations = [
        # Store the full text of a meeting's notes file for search and display.
        # Kept in sync by cli/indexer.py whenever a notes file is written.
        migrations.AddField(
            model_name="meeting",
            name="content",
            field=models.TextField(
                blank=True,
                help_text="Full text of notes file, synced by indexer for search",
            ),
        ),

        # FTS5 virtual table — indexes ALL notes files (meetings, docs, freeform).
        # Standalone (not content-backed): we manage inserts/deletes ourselves.
        # tokenize='porter unicode61': stemming + unicode folding (AI matches artificial).
        migrations.RunSQL(
            sql="""
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts
                USING fts5(
                    path UNINDEXED,
                    content,
                    tokenize='porter unicode61'
                );
            """,
            reverse_sql="DROP TABLE IF EXISTS notes_fts;",
        ),
    ]
