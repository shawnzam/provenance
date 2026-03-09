from django.contrib import admin
from .models import Person, Meeting, ActionItem, Topic, ReadingItem


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "role", "org", "email", "slug"]
    search_fields = ["name", "org", "role", "email", "tags"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ["title", "date", "slug"]
    list_filter = ["date"]
    search_fields = ["title", "summary", "tags"]
    filter_horizontal = ["attendees"]
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_display = ["description", "status", "due_date", "person", "meeting"]
    list_filter = ["status", "due_date"]
    search_fields = ["description", "tags"]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ReadingItem)
class ReadingItemAdmin(admin.ModelAdmin):
    list_display = ["title", "status", "tags", "created_at", "slug"]
    list_filter = ["status"]
    search_fields = ["title", "url", "tags", "summary", "notes"]
    readonly_fields = ["slug", "created_at", "read_at"]
