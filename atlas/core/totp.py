"""Time-Based One-Time Password (TOTP) Authenticator under RFC 6238 (Phase 9)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time


class TOTPAuthenticator:
    """RFC 6238 compliant TOTP generator and verifier using standard library HMAC/SHA1."""

    def __init__(
        self,
        secret_base32: str | None = None,
        digits: int = 6,
        interval_seconds: int = 30,
    ) -> None:
        self.digits = digits
        self.interval = interval_seconds
        self.secret = secret_base32 or self.generate_secret()

    @staticmethod
    def generate_secret(byte_length: int = 20) -> str:
        """Generate a cryptographically secure random base32 encoded secret."""
        raw_bytes = os.urandom(byte_length)
        return base64.b32encode(raw_bytes).decode("ascii").replace("=", "")

    def _get_time_step(self, timestamp: float | None = None) -> int:
        current_time = timestamp if timestamp is not None else time.time()
        return int(current_time // self.interval)

    def generate_code(self, timestamp: float | None = None) -> str:
        """Generate 6-digit TOTP code for the given timestamp."""
        time_step = self._get_time_step(timestamp)
        # Pack time step as 8-byte big-endian integer
        msg = struct.pack(">Q", time_step)

        # Pad base32 secret with '=' if necessary
        secret_str = self.secret.upper()
        missing_padding = len(secret_str) % 8
        if missing_padding:
            secret_str += "=" * (8 - missing_padding)

        key = base64.b32decode(secret_str, casefold=True)
        hmac_digest = hmac.new(key, msg, hashlib.sha1).digest()

        # Dynamic truncation (RFC 4226)
        offset = hmac_digest[-1] & 0x0F
        code_int = struct.unpack(">I", hmac_digest[offset : offset + 4])[0] & 0x7FFFFFFF
        code_modulo = code_int % (10**self.digits)

        return f"{code_modulo:0{self.digits}d}"

    def verify_code(
        self,
        code: str,
        timestamp: float | None = None,
        drift_steps: int = 1,
    ) -> bool:
        """Verify code against current time step with allowed clock drift (+/- drift_steps)."""
        clean_code = str(code).strip()
        if len(clean_code) != self.digits:
            return False

        current_time = timestamp if timestamp is not None else time.time()
        base_step = self._get_time_step(current_time)

        for step_offset in range(-drift_steps, drift_steps + 1):
            target_time = (base_step + step_offset) * self.interval
            expected_code = self.generate_code(timestamp=target_time)
            # Constant-time comparison
            if hmac.compare_digest(clean_code, expected_code):
                return True

        return False

    def get_provisioning_uri(self, account_name: str, issuer_name: str = "ATLAS") -> str:
        """Generate standard otpauth:// URL for authenticator apps (Google Authenticator, Bitwarden, etc.)."""
        import urllib.parse

        encoded_issuer = urllib.parse.quote(issuer_name)
        encoded_account = urllib.parse.quote(account_name)
        return (
            f"otpauth://totp/{encoded_issuer}:{encoded_account}"
            f"?secret={self.secret}&issuer={encoded_issuer}&algorithm=SHA1&digits={self.digits}&period={self.interval}"
        )
