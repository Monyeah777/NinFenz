"""Versioned cryptographic suites for ASVS V11.2.2 crypto agility.

Callers select a named suite rather than depending on a hard-coded primitive.
The default remains the established ``v1`` contract so existing tokens and
digests do not change silently. Deployments may select another reviewed suite
through ``NF_CRYPTO_SUITE``; unknown identifiers fail closed.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass

ENV_NAME = "NF_CRYPTO_SUITE"
DEFAULT_SUITE = "v1"


@dataclass(frozen=True)
class CryptoSuite:
    """One reviewed set of random, digest, and constant-time comparison choices."""

    id: str
    token_bytes: int
    digest: str
    mac: str
    migration_note: str


SUITES = {
    "v1": CryptoSuite(
        id="v1",
        token_bytes=32,
        digest="sha256",
        mac="hmac.compare_digest",
        migration_note=(
            "Compatibility suite. Existing content digests and 64-character "
            "daemon tokens remain valid."
        ),
    ),
    "v2-sha512": CryptoSuite(
        id="v2-sha512",
        token_bytes=48,
        digest="sha512",
        mac="hmac.compare_digest",
        migration_note=(
            "Upgraded integrity suite for new artifacts. Migration must "
            "recompute versioned digests and rotate daemon sessions."
        ),
    ),
}


def get_suite(name: str | None = None) -> CryptoSuite:
    """Resolve a closed-registry suite name; unknown values fail closed."""
    suite_id = str(name or DEFAULT_SUITE).strip()
    suite = SUITES.get(suite_id)
    if suite is None:
        raise ValueError(
            f"unknown cryptographic suite {suite_id!r}"
            "（修复指引：使用已审查的 NF_CRYPTO_SUITE 值）"
        )
    if suite.digest not in hashlib.algorithms_available:
        raise ValueError(
            f"cryptographic digest unavailable: {suite.digest}"
            "（修复指引：安装包含该摘要算法的 Python/OpenSSL 运行时后重试）"
        )
    return suite


class CryptoPolicy:
    """Mutable selection point used by long-lived services and migration tests."""

    def __init__(self, name: str | None = None):
        self.swap(name if name is not None else os.environ.get(ENV_NAME))

    @property
    def suite(self) -> CryptoSuite:
        return self._suite

    @property
    def suite_id(self) -> str:
        return self._suite.id

    def swap(self, name: str | None) -> CryptoSuite:
        self._suite = get_suite(name)
        return self._suite

    def new_token(self) -> str:
        return secrets.token_hex(self._suite.token_bytes)

    def digest_hex(self, data: bytes) -> str:
        return hashlib.new(self._suite.digest, bytes(data)).hexdigest()

    def compare(self, left: str, right: str) -> bool:
        return hmac.compare_digest(str(left), str(right))


def new_token() -> str:
    """Generate a token with the currently configured suite."""
    return CryptoPolicy().new_token()


def digest_hex(data: bytes) -> str:
    """Hash bytes with the currently configured suite."""
    return CryptoPolicy().digest_hex(data)


def compare(left: str, right: str) -> bool:
    """Constant-time comparison through the active policy abstraction."""
    return CryptoPolicy().compare(left, right)


__all__ = [
    "CryptoPolicy",
    "CryptoSuite",
    "DEFAULT_SUITE",
    "ENV_NAME",
    "SUITES",
    "compare",
    "digest_hex",
    "get_suite",
    "new_token",
]
