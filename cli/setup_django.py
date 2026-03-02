"""Bootstrap Django before any model imports."""
import os
import django


def setup():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "provenance.settings")
    django.setup()
