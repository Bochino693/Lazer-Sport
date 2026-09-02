"""Roda a suíte com SQLite isolado e sem requisições externas de requests."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

def main():
    os.chdir(Path(__file__).resolve().parent)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'lazer.settings_test'

    import requests
    from django.core.management import execute_from_command_line

    with patch('requests.sessions.Session.request', side_effect=requests.RequestException('Rede externa desativada nos testes')):
        execute_from_command_line(['manage.py', 'test', '--noinput', *sys.argv[1:]])

if __name__ == "__main__":
    main()
