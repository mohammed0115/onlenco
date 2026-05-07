#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Auto-switch to test settings when running `manage.py test` so test-only
    # overrides (axes off, MD5 hasher, in-memory email) take effect without
    # the developer having to pass --settings or set the env var manually.
    if "test" in sys.argv[1:2]:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.test')
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
