"""Gitee polling failures must be categorized, visible, and fail closed."""

from __future__ import annotations

import importlib.util
import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / ".github" / "scripts"))


def _bot():
    spec = importlib.util.spec_from_file_location(
        "nf_gitee_ingest_diagnostics",
        ROOT / ".github" / "scripts" / "gitee_ingest.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GiteeDiagnosticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bot = _bot()

    def test_http_failures_have_stable_categories(self) -> None:
        cases = {
            401: "token_invalid",
            403: "forbidden",
            404: "endpoint_not_found",
            429: "rate_limited",
            500: "upstream_error",
            418: "http_error",
        }
        for status, category in cases.items():
            with self.subTest(status=status):
                self.assertEqual(category, self.bot._classify_http_failure(status, ""))
        self.assertEqual(
            "rate_limited",
            self.bot._classify_http_failure(403, "API rate limit exceeded"),
        )

    def test_http_error_is_raised_with_redacted_diagnostic(self) -> None:
        err = urllib.error.HTTPError(
            "https://gitee.com/api/v5/x",
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"message":"bad token secret-value"}'),
        )
        with mock.patch.object(self.bot.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(self.bot.GiteeAPIError) as caught:
                self.bot.gitee_api("/repos/x/issues")
        exc = caught.exception
        self.assertEqual("forbidden", exc.category)
        self.assertEqual(403, exc.status)
        rendered = str(exc)
        self.assertIn("category=forbidden", rendered)
        self.assertNotIn("secret-value", rendered)

    def test_transport_error_is_network_category(self) -> None:
        with mock.patch.object(
            self.bot.urllib.request,
            "urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaises(self.bot.GiteeAPIError) as caught:
                self.bot.gitee_api("/repos/x/issues")
        self.assertEqual("network_error", caught.exception.category)

    def test_unexpected_payload_shape_fails_closed(self) -> None:
        with mock.patch.object(self.bot, "gitee_api", return_value={"message": "changed"}):
            with self.assertRaises(self.bot.GiteeAPIError) as caught:
                self.bot.fetch_open_submissions()
        self.assertEqual("response_shape", caught.exception.category)

    def test_missing_token_is_explicit(self) -> None:
        with mock.patch.object(self.bot, "TOKEN", ""):
            rc = self.bot.main()
        self.assertEqual(1, rc)

    def test_intake_path_symbol_is_imported(self) -> None:
        self.assertEqual("library/intake.json", self.bot.INTAKE_REL)


if __name__ == "__main__":
    unittest.main()
