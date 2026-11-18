"""Django's command-line utility."""

import os
import sys

from django.core.management import execute_from_command_line


def main() -> None:
    """Run a Django management command."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
