from django.db import models
from slugify import slugify


class ReadingItem(models.Model):
    STATUS_CHOICES = [
        ("to_read", "To Read"),
        ("read", "Read"),
        ("archived", "Archived"),
    ]

    url = models.URLField(max_length=2000, unique=True)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    title = models.CharField(max_length=500, blank=True)
    summary = models.TextField(blank=True, help_text="AI-generated summary")
    notes = models.TextField(blank=True, help_text="Your own notes on this article")
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="to_read")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = self.title or self.url
            self.slug = slugify(base)[:280]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or self.url
