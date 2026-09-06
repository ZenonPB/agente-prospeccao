"""Configuração do limitador HTTP.

O slowapi 0.1.10 ainda chama ``asyncio.iscoroutinefunction``. A função foi
depreciada no Python 3.14; manter a compatibilidade aqui evita que a importação
das rotas falhe sob ``-W error`` sem alterar o comportamento do limitador.
"""
import inspect
import sys

import slowapi.extension

if sys.version_info >= (3, 14):
    slowapi.extension.asyncio.iscoroutinefunction = inspect.iscoroutinefunction

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
