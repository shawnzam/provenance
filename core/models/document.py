from django.db import models
from slugify import slugify as _slugify


class Document(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    file_path = models.CharField(max_length=500, help_text="Relative path to the .md file in notes/docs/")
    source = models.CharField(max_length=500, blank=True, help_text="Original filename (for imported files)")
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    notes = models.TextField(blank=True, help_text="Your notes about this document")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def to_dict(self):
        return {
            "slug": self.slug,
            "title": self.title,
            "file_path": self.file_path,
            "source": self.source,
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()],
            "notes": self.notes,
        }
