"""Downloader robusto de snapshot oficial (PR C).

Seam: `services.registry.downloader` — sem rede real: transporte httpx
mockado e resolvedor DNS injetado. Nenhum teste depende de snapshot real,
relógio de parede ou data atual (backoff zerado onde há retry).
"""
from __future__ import annotations

import asyncio
import hashlib

import httpx

PUBLIC_IP = "93.184.216.34"
EVIL_IP = "10.9.9.9"
BODY = b"x" * 65536 + b"y" * 1024


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest():
    from services.registry.manifest import parse_manifest

    return parse_manifest({
        "manifest_version": "1",
        "source": "receita_cnpj",
        "snapshot_month": "2026-08",
        "layout": "NOVOLAYOUTDOSDADOSABERTOSDOCNPJ",
        "layout_version": "2026-08",
        "encoding": "latin-1",
        "origin_kind": "receita_oficial",
        "origin_url": "https://arquivos.receitafederal.gov.br/dados/cnpj/2026-08",
        "accessed_at": "2026-09-01",
        "files": [{"table_kind": "estabelecimentos", "file_name": "ESTABELE0"}],
    })


def _downloader(**overrides):
    from services.registry.downloader import SnapshotDownloader

    params = {
        "resolver": lambda host, port: [PUBLIC_IP],
        "backoff_base": 0.0,
        "backoff_max": 0.0,
    }
    params.update(overrides)
    return SnapshotDownloader(**params)


def _run(coro):
    return asyncio.run(coro)


def test_specs_derivam_url_e_destino_do_manifesto(tmp_path):
    from services.registry.downloader import manifest_download_specs

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    assert len(specs) == 1
    assert specs[0].url == (
        "https://arquivos.receitafederal.gov.br/dados/cnpj/2026-08/ESTABELE0")
    assert specs[0].dest_path == str(tmp_path / "ESTABELE0")
    assert specs[0].allowed_hosts == {"arquivos.receitafederal.gov.br"}


def test_specs_rejeitam_file_name_com_path_traversal(tmp_path):
    from services.registry.downloader import DownloadError, manifest_download_specs
    from services.registry.manifest import parse_manifest

    manifest = parse_manifest({**_manifest_dict(), "files": [
        {"table_kind": "estabelecimentos", "file_name": "../EVIL"}]})
    try:
        manifest_download_specs(manifest, str(tmp_path))
    except DownloadError:
        return
    raise AssertionError("path traversal deveria ser rejeitado")


def _manifest_dict():
    return {
        "manifest_version": "1",
        "source": "receita_cnpj",
        "snapshot_month": "2026-08",
        "layout": "NOVOLAYOUTDOSDADOSABERTOSDOCNPJ",
        "layout_version": "2026-08",
        "encoding": "latin-1",
        "origin_kind": "receita_oficial",
        "origin_url": "https://arquivos.receitafederal.gov.br/dados/cnpj/2026-08",
        "accessed_at": "2026-09-01",
        "files": [{"table_kind": "estabelecimentos", "file_name": "ESTABELE0"}],
    }


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ok_handler(request):
    assert request.headers.get("user-agent", "").startswith("ProspectAI-RegistryDownloader")
    return httpx.Response(200, headers={"Content-Length": str(len(BODY))}, content=BODY)


def test_download_ok_grava_atomico_com_sha(tmp_path):
    from services.registry.downloader import manifest_download_specs

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    result = _run(_downloader().download(specs[0], client=_client(_ok_handler)))
    assert result.bytes == len(BODY)
    assert result.sha256 == _sha(BODY)
    assert result.attempts == 1
    assert result.resumed is False
    assert (tmp_path / "ESTABELE0").read_bytes() == BODY
    assert not (tmp_path / "ESTABELE0.part").exists()


def test_download_rejeita_ip_privado_sem_rede():
    from services.registry.downloader import DownloadError, DownloadSpec

    def evil_resolver(host, port):
        return [EVIL_IP]

    from services.registry.downloader import SnapshotDownloader

    calls = []

    def fail_if_called(request):
        calls.append(request)
        raise AssertionError("rede não deveria ser tocada")

    spec = DownloadSpec(
        url="https://arquivos.receitafederal.gov.br/dados/cnpj/2026-08/ESTABELE0",
        dest_path="/tmp/irrelevante", allowed_hosts={"arquivos.receitafederal.gov.br"})
    downloader = SnapshotDownloader(resolver=evil_resolver, backoff_base=0.0, backoff_max=0.0)
    try:
        _run(downloader.download(spec, client=_client(fail_if_called)))
    except DownloadError:
        assert calls == []
        return
    raise AssertionError("IP privado deveria ser rejeitado")


def test_download_rejeita_host_fora_da_confianca(tmp_path):
    from services.registry.downloader import DownloadError, DownloadSpec

    spec = DownloadSpec(
        url="https://evil.example.com/ESTABELE0",
        dest_path=str(tmp_path / "ESTABELE0"),
        allowed_hosts={"arquivos.receitafederal.gov.br"})
    try:
        _run(_downloader().download(spec, client=_client(_ok_handler)))
    except DownloadError:
        return
    raise AssertionError("host fora da confiança deveria ser rejeitado")


def test_download_rejeita_esquema_http(tmp_path):
    from services.registry.downloader import DownloadError, DownloadSpec

    spec = DownloadSpec(
        url="http://arquivos.receitafederal.gov.br/ESTABELE0",
        dest_path=str(tmp_path / "ESTABELE0"),
        allowed_hosts={"arquivos.receitafederal.gov.br"})
    try:
        _run(_downloader().download(spec, client=_client(_ok_handler)))
    except DownloadError:
        return
    raise AssertionError("http deveria ser rejeitado")


def test_redirect_para_host_inseguro_e_bloqueado(tmp_path):
    from services.registry.downloader import DownloadError, manifest_download_specs

    def handler(request):
        if "evil" in str(request.url):
            raise AssertionError("hop inseguro não deveria ser requisitado")
        return httpx.Response(302, headers={"location": "https://evil.example.com/x"})

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    try:
        _run(_downloader().download(specs[0], client=_client(handler)))
    except DownloadError:
        return
    raise AssertionError("redirect inseguro deveria ser bloqueado")


def test_redirect_mesmo_host_e_seguido(tmp_path):
    from services.registry.downloader import manifest_download_specs

    def handler(request):
        if str(request.url).endswith("/final"):
            return httpx.Response(200, headers={"Content-Length": str(len(BODY))}, content=BODY)
        return httpx.Response(302, headers={"location": "/final"})

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    result = _run(_downloader().download(specs[0], client=_client(handler)))
    assert result.sha256 == _sha(BODY)


def test_resume_continua_part_quando_206(tmp_path):
    from services.registry.downloader import manifest_download_specs

    part = tmp_path / "ESTABELE0.part"
    part.write_bytes(BODY[:1000])

    def handler(request):
        assert request.headers.get("range") == "bytes=1000-"
        rest = BODY[1000:]
        return httpx.Response(206, headers={
            "Content-Range": f"bytes 1000-{len(BODY) - 1}/{len(BODY)}",
            "Content-Length": str(len(rest))}, content=rest)

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    result = _run(_downloader().download(specs[0], client=_client(handler)))
    assert result.resumed is True
    assert result.sha256 == _sha(BODY)
    assert (tmp_path / "ESTABELE0").read_bytes() == BODY


def test_recomeca_quando_servidor_ignora_range(tmp_path):
    from services.registry.downloader import manifest_download_specs

    (tmp_path / "ESTABELE0.part").write_bytes(b"lixo-antigo")

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    result = _run(_downloader().download(specs[0], client=_client(_ok_handler)))
    assert result.resumed is False
    assert result.sha256 == _sha(BODY)


def test_retry_em_500_e_sucesso(tmp_path):
    from services.registry.downloader import manifest_download_specs

    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(500, content=b"erro")
        return httpx.Response(200, headers={"Content-Length": str(len(BODY))}, content=BODY)

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    result = _run(_downloader(max_attempts=3).download(specs[0], client=_client(handler)))
    assert result.attempts == 2
    assert result.sha256 == _sha(BODY)


def test_404_nao_tenta_de_novo(tmp_path):
    from services.registry.downloader import DownloadError, manifest_download_specs

    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404, content=b"nao achado")

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    try:
        _run(_downloader(max_attempts=3).download(specs[0], client=_client(handler)))
    except DownloadError:
        assert len(calls) == 1
        return
    raise AssertionError("404 não deveria repetir tentativas")


def test_sha_divergente_apaga_temporario(tmp_path):
    from services.registry.downloader import DownloadError, manifest_download_specs

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    spec = specs[0]._replace(expected_sha256="0" * 64)
    try:
        _run(_downloader().download(spec, client=_client(_ok_handler)))
    except DownloadError:
        assert not (tmp_path / "ESTABELE0").exists()
        assert not (tmp_path / "ESTABELE0.part").exists()
        return
    raise AssertionError("sha divergente deveria falhar")


def test_tamanho_esperado_divergente_falha(tmp_path):
    from services.registry.downloader import DownloadError, manifest_download_specs

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    spec = specs[0]._replace(expected_bytes=len(BODY) + 1)
    try:
        _run(_downloader().download(spec, client=_client(_ok_handler)))
    except DownloadError:
        return
    raise AssertionError("tamanho divergente deveria falhar")


def test_destino_com_sha_igual_e_reaproveitado_sem_rede(tmp_path):
    from services.registry.downloader import manifest_download_specs

    (tmp_path / "ESTABELE0").write_bytes(BODY)
    calls = []

    def fail_if_called(request):
        calls.append(request)
        raise AssertionError("rede não deveria ser tocada")

    specs = manifest_download_specs(_manifest(), str(tmp_path))
    spec = specs[0]._replace(expected_sha256=_sha(BODY), expected_bytes=len(BODY))
    result = _run(_downloader().download(spec, client=_client(fail_if_called)))
    assert result.from_cache is True
    assert result.sha256 == _sha(BODY)
    assert calls == []


def test_manifesto_observado_preenche_bytes_e_sha():
    from services.registry.downloader import manifest_with_observed

    manifest = _manifest()
    updated = manifest_with_observed(manifest, {"ESTABELE0": (len(BODY), _sha(BODY))})
    assert updated.files[0].bytes == len(BODY)
    assert updated.files[0].sha256 == _sha(BODY)
    assert updated.snapshot_month == manifest.snapshot_month
