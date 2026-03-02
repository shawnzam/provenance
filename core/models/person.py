from django.db import models
from slugify import slugify


class Person(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    role = models.CharField(max_length=200, blank=True)
    org = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    relationship_context = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "people"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        parts = [self.name]
        if self.role:
            parts.append(self.role)
        if self.org:
            parts.append(self.org)
        return " — ".join(parts)

    def to_dict(self):
        return {
            "slug": self.slug,
            "name": self.name,
            "role": self.role,
            "org": self.org,
            "email": self.email,
            "relationship_context": self.relationship_context,
            "notes": self.notes,
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()],
        }
