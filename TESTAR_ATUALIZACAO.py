import os
import sys
from pathlib import Path
from unittest.mock import patch

def main():
    os.chdir(Path(__file__).resolve().parent)
    os.environ["DJANGO_SETTINGS_MODULE"] = "lazer.settings_test"

    from django.core.management import execute_from_command_line
    from requests.exceptions import RequestException

    with patch(
        "requests.sessions.Session.request",
        side_effect=RequestException("Rede externa desativada nos testes"),
    ):
        execute_from_command_line(
            ["manage.py", "test", "--noinput", *sys.argv[1:]]
        )

if __name__ == "__main__":
    main()
