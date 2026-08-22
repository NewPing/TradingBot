"""Unit tests for configuration loading and validation."""

import pytest
from pydantic import ValidationError

from atlas.core.config import Settings


def test_default_settings_valid() -> None:
    settings = Settings()
    assert settings.atlas_env in ("dev", "research", "live")
    assert settings.atlas_allow_live is False
    assert settings.atlas_max_leverage <= 1.0


def test_settings_rejects_excessive_leverage() -> None:
    with pytest.raises(ValidationError, match="cannot exceed 1.0"):
        Settings(atlas_max_leverage=1.5)
