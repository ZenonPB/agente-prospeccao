"""Rollout 1E começa desligado e não muda produção por default."""


def test_commercial_dimensions_shadow_default_off():
    from src.config.settings import settings

    assert settings.COMMERCIAL_DIMENSIONS_SHADOW_ENABLED is False
