from django.db import models
from slugify import slugify


class Meeting(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    date = models.DateField()
    attendees = models.ManyToManyField("core.Person", blank=True, related_name="meetings")
    summary = models.TextField(blank=True)
    content = models.TextField(blank=True, help_text="Full text of notes file, synced by indexer for search")
    notes_file = models.CharField(max_length=500, blank=True, help_text="Relative path to .md notes file")
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.date}-{self.title}" if self.date else self.title
            self.slug = slugify(str(base))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} — {self.title}"

    def to_dict(self):
        return {
            "slug": self.slug,
            "title": self.title,
            "date": str(self.date),
            "attendees": [p.slug for p in self.attendees.all()],
            "summary": self.summary,
            "notes_file": self.notes_file,
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()],
        }
