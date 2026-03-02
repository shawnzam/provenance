from django.db import models


class ActionItem(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]

    description = models.TextField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    person = models.ForeignKey(
        "core.Person", null=True, blank=True, on_delete=models.SET_NULL, related_name="action_items"
    )
    meeting = models.ForeignKey(
        "core.Meeting", null=True, blank=True, on_delete=models.SET_NULL, related_name="action_items"
    )
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "created_at"]

    def __str__(self):
        return self.description[:80]

    def to_dict(self):
        return {
            "id": self.pk,
            "description": self.description,
            "due_date": str(self.due_date) if self.due_date else None,
            "status": self.status,
            "person": self.person.slug if self.person else None,
            "meeting": self.meeting.slug if self.meeting else None,
            "tags": [t.strip() for t in self.tags.split(",") if t.strip()],
        }
