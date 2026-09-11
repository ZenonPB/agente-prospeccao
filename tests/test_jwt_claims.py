"""JWT com `iss`/`aud` configuráveis (hardening — rejeita token de outro emissor).

Os claims existiam, mas literais no código. A emissão e a validação passam a
ler `settings.JWT_ISSUER`/`settings.JWT_AUDIENCE` (env, com defaults seguros),
de modo que staging/prod podem isolar emissores.
"""
import jwt

from src.auth.security import create_access_token, decode_access_token
from src.config.settings import settings


def test_token_carrega_iss_e_aud_do_settings():
    token = create_access_token({"sub": "u-1"})
    payload = jwt.decode(token, options={"verify_signature": False})
    assert payload["iss"] == settings.JWT_ISSUER
    assert payload["aud"] == settings.JWT_AUDIENCE


def test_settings_trazem_defaults_seguros_documentados():
    assert settings.JWT_ISSUER == "prospect-ai"
    assert settings.JWT_AUDIENCE == "prospect-ai-api"


def test_decode_rejeita_audience_errada():
    import datetime

    forged = jwt.encode(
        {
            "sub": "u-1",
            "iss": settings.JWT_ISSUER,
            "aud": "outra-api",
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(forged) is None


def test_decode_rejeita_issuer_errado():
    import datetime

    forged = jwt.encode(
        {
            "sub": "u-1",
            "iss": "outro-emissor",
            "aud": settings.JWT_AUDIENCE,
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(forged) is None


def test_decode_aceita_token_valido_emitido():
    token = create_access_token({"sub": "u-1", "email": "a@b.c"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "u-1"
