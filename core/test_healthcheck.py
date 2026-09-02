from unittest import TestCase
from unittest.mock import Mock

from core.healthcheck import HealthcheckWSGI


class HealthcheckTests(TestCase):
    def test_probe_does_not_enter_django_even_if_dependencies_fail(self):
        django = Mock(side_effect=RuntimeError("banco indisponível"))
        app = HealthcheckWSGI(django)
        for path in ("/healthz", "/healthz/"):
            for method in ("GET", "HEAD"):
                start = Mock()
                result = app({"PATH_INFO": path, "REQUEST_METHOD": method}, start)
                self.assertEqual(b"".join(result), b"ok" if method == "GET" else b"")
                self.assertEqual(start.call_args.args[0], "200 OK")
        django.assert_not_called()

    def test_other_routes_and_writes_keep_normal_application(self):
        for path, method in (("/pronto/", "GET"), ("/healthz/extra", "GET"),
                             ("/healthz/", "POST"), ("/orcamentos/", "POST")):
            django = Mock(return_value=[b"original"])
            env = {"PATH_INFO": path, "REQUEST_METHOD": method}
            start = Mock()
            self.assertEqual(HealthcheckWSGI(django)(env, start), [b"original"])
            django.assert_called_once_with(env, start)
