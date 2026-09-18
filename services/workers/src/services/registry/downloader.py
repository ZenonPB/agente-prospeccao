"""Downloader robusto de snapshot oficial (fonte → disco local).

Baixa os arquivos listados no manifesto com streaming (nunca o arquivo
inteiro em RAM), resume seguro via Range, retry com backoff, validação de
integridade (tamanho + SHA-256) e rename atômico. Idempotente: destino com
SHA igual é reaproveitado sem rede.

Confiança restrita e documentada: https obrigatório, host precisa estar no
conjunto permitido (por manifesto, o host da origem declarada), IP literal
e TODOS os IPs resolvidos precisam ser públicos, redirects manuais
revalidados por hop. Nenhuma exceção genérica de rede privada.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
import os
import shutil
import socket
from typing import Any, Callable, Mapping, NamedTuple
from urllib.parse import urljoin, urlsplit

import httpx

from services.prospecting.safe_web_client import SafePublicWebClient
from services.registry.manifest import SnapshotManifest

logger = logging.getLogger(__name__)

USER_AGENT = "ProspectAI-RegistryDownloader/1.0"
_CHUNK_SIZE = 1024 * 1024


class DownloadError(RuntimeError):
    """Falha de download com motivo auditável. Nunca expõe segredo."""

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason
        self.message = message

    def __str__(self) -> str:
        return self.message or self.reason


class _Retryable(DownloadError):
    """Falha transitória: pode tentar de novo dentro do orçamento."""


class DownloadSpec(NamedTuple):
    url: str
    dest_path: str
    allowed_hosts: frozenset[str]
    expected_bytes: int | None = None
    expected_sha256: str | None = None


class DownloadResult(NamedTuple):
    file_name: str
    path: str
    bytes: int
    sha256: str
    resumed: bool
    attempts: int
    from_cache: bool


def _default_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


def _check_ip_global(value: str, reason: str) -> None:
    try:
        global_ = bool(ipaddress.ip_address(value).is_global)
    except ValueError:
        global_ = False
    if not global_:
        raise DownloadError(reason, f"destino não público: {value}")


def manifest_download_specs(
    manifest: SnapshotManifest, dest_dir: str,
) -> list[DownloadSpec]:
    """Deriva as specs de download do manifesto (origem + nomes de arquivo).

    O host permitido é exatamente o host da origem declarada. Nomes com
    separador ou `..` são rejeitados (sem escape do diretório de destino).
    """
    origin = urlsplit(manifest.origin_url)
    if not origin.hostname:
        raise DownloadError("invalid_origin", "manifesto sem host de origem")
    specs = []
    for entry in manifest.files:
        name = entry.file_name
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise DownloadError("unsafe_file_name", f"nome de arquivo inseguro: {name!r}")
        if os.path.basename(name) != name:
            raise DownloadError("unsafe_file_name", f"nome de arquivo inseguro: {name!r}")
        url = manifest.origin_url.rstrip("/") + "/" + name
        specs.append(DownloadSpec(
            url=url,
            dest_path=os.path.join(dest_dir, name),
            allowed_hosts=frozenset({origin.hostname.lower()}),
            expected_bytes=entry.bytes,
            expected_sha256=entry.sha256,
        ))
    return specs


def manifest_with_observed(
    manifest: SnapshotManifest, observed: Mapping[str, tuple[int, str]],
) -> SnapshotManifest:
    """Devolve cópia do manifesto com bytes/sha observados preenchidos."""
    from services.registry.manifest import ManifestFile

    files = tuple(
        ManifestFile(
            table_kind=entry.table_kind,
            file_name=entry.file_name,
            bytes=observed[entry.file_name][0] if entry.file_name in observed else entry.bytes,
            sha256=observed[entry.file_name][1] if entry.file_name in observed else entry.sha256,
        )
        for entry in manifest.files
    )
    return SnapshotManifest(
        source=manifest.source,
        snapshot_month=manifest.snapshot_month,
        layout=manifest.layout,
        layout_version=manifest.layout_version,
        encoding=manifest.encoding,
        origin_kind=manifest.origin_kind,
        origin_url=manifest.origin_url,
        accessed_at=manifest.accessed_at,
        files=files,
    )


class SnapshotDownloader:
    """Baixa arquivos de snapshot com retomada, retry e integridade."""

    def __init__(
        self, *,
        timeout_connect: float = 10.0,
        timeout_read: float = 60.0,
        timeout_total: float = 1800.0,
        max_attempts: int = 4,
        backoff_base: float = 2.0,
        backoff_max: float = 60.0,
        max_redirects: int = 5,
        min_free_bytes: int = 256 * 1024 * 1024,
        resolver: Callable[[str, int], list[str]] | None = None,
        transport: Any | None = None,
    ) -> None:
        self.timeout_connect = timeout_connect
        self.timeout_read = timeout_read
        self.timeout_total = timeout_total
        self.max_attempts = max(1, max_attempts)
        self.backoff_base = max(0.0, backoff_base)
        self.backoff_max = max(0.0, backoff_max)
        self.max_redirects = max(0, max_redirects)
        self.min_free_bytes = min_free_bytes
        self._resolver = resolver or _default_resolver
        self._transport = transport
        self._trust = SafePublicWebClient(resolver=self._resolver)

    def _check_url(self, url: str, allowed_hosts: frozenset[str]) -> str:
        parsed = urlsplit((url or "").strip())
        if parsed.scheme.lower() != "https":
            raise DownloadError("scheme_not_allowed", f"só https: {url!r}")
        try:
            target = self._trust.validate_url(url)
        except Exception as exc:
            raise DownloadError(getattr(exc, "reason", "invalid_url"), str(exc)) from exc
        host = (parsed.hostname or "").rstrip(".").lower()
        if host not in allowed_hosts:
            raise DownloadError("untrusted_host", f"host fora da confiança: {host!r}")
        return target

    async def _check_destination(self, url: str) -> None:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        try:
            ips = await asyncio.to_thread(
                self._resolver, host, parsed.port or 443)
        except Exception as exc:
            raise DownloadError("dns_failed", f"DNS falhou para {host!r}") from exc
        try:
            self._trust.validate_destination(host, ips)
        except Exception as exc:
            raise DownloadError(getattr(exc, "reason", "dns_failed"), str(exc)) from exc

    def _check_disk(self, dest_dir: str, need: int | None) -> None:
        try:
            free = shutil.disk_usage(dest_dir).free
        except OSError as exc:
            raise DownloadError("disk_unavailable", f"disco indisponível: {exc}") from exc
        required = need if need is not None else self.min_free_bytes
        if free < required:
            raise DownloadError(
                "insufficient_disk_space",
                f"espaço livre insuficiente: {free} < {required}")

    @staticmethod
    def _hash_file(path: str) -> tuple[int, str]:
        digest = hashlib.sha256()
        total = 0
        with open(path, "rb") as handle:
            while True:
                raw = handle.read(_CHUNK_SIZE)
                if not raw:
                    break
                digest.update(raw)
                total += len(raw)
        return total, digest.hexdigest()

    async def download(
        self, spec: DownloadSpec, *, client: httpx.AsyncClient | None = None,
    ) -> DownloadResult:
        """Baixa um arquivo com retry. Erro final vira DownloadError."""
        file_name = os.path.basename(spec.dest_path)
        if spec.expected_sha256 is not None and os.path.exists(spec.dest_path):
            size, digest = await asyncio.to_thread(self._hash_file, spec.dest_path)
            if digest == spec.expected_sha256.lower():
                logger.info("download skip %s (sha256 igual)", file_name)
                return DownloadResult(file_name, spec.dest_path, size, digest,
                                      False, 0, True)
        elif os.path.exists(spec.dest_path):
            size, digest = await asyncio.to_thread(self._hash_file, spec.dest_path)
            if spec.expected_bytes is None or size == spec.expected_bytes:
                logger.info("download skip %s (já existe, sem sha esperado)", file_name)
                return DownloadResult(file_name, spec.dest_path, size, digest,
                                      False, 0, True)
        owned = client is None
        if owned:
            timeout = httpx.Timeout(self.timeout_total, connect=self.timeout_connect,
                                    read=self.timeout_read)
            client = httpx.AsyncClient(timeout=timeout, follow_redirects=False,
                                       transport=self._transport)
        try:
            last_error: DownloadError = DownloadError("unknown", "falha desconhecida")
            for attempt in range(1, self.max_attempts + 1):
                try:
                    return await self._attempt(spec, client, attempt)
                except _Retryable as exc:
                    last_error = exc
                    logger.warning("download %s tentativa %d: %s",
                                   file_name, attempt, exc.reason)
                    if attempt < self.max_attempts:
                        await asyncio.sleep(min(
                            self.backoff_max, self.backoff_base * (2 ** (attempt - 1))))
            raise DownloadError(last_error.reason, str(last_error))
        finally:
            if owned:
                await client.aclose()

    async def _attempt(
        self, spec: DownloadSpec, client: httpx.AsyncClient, attempt: int,
    ) -> DownloadResult:
        from urllib.parse import urljoin

        file_name = os.path.basename(spec.dest_path)
        dest_dir = os.path.dirname(spec.dest_path) or "."
        self._check_disk(dest_dir, spec.expected_bytes)
        target = self._check_url(spec.url, spec.allowed_hosts)
        part_path = spec.dest_path + ".part"
        part_size = os.path.getsize(part_path) if os.path.exists(part_path) else 0

        redirects = 0
        headers = {"User-Agent": USER_AGENT}
        if part_size > 0:
            headers["Range"] = f"bytes={part_size}-"
        while True:
            await self._check_destination(target)
            try:
                response_ctx = client.stream("GET", target, headers=headers)
                response = await response_ctx.__aenter__()
            except httpx.TimeoutException as exc:
                raise _Retryable("timeout", f"timeout: {exc}") from exc
            except httpx.RequestError as exc:
                raise _Retryable("network_error", f"rede: {exc}") from exc
            try:
                code = response.status_code
                if 300 <= code < 400 and response.headers.get("location"):
                    redirects += 1
                    if redirects > self.max_redirects:
                        raise DownloadError("too_many_redirects", "redirects demais")
                    target = self._check_url(
                        urljoin(target, response.headers["location"]), spec.allowed_hosts)
                    continue
                if code == 416:
                    try:
                        os.remove(part_path)
                    except OSError:
                        pass
                    part_size = 0
                    headers.pop("Range", None)
                    continue
                if code == 429 or 500 <= code < 600:
                    raise _Retryable(f"http_{code}", f"HTTP transitório: {code}")
                if code not in (200, 206):
                    raise DownloadError(f"http_{code}", f"HTTP não recuperável: {code}")
                if code == 200 and part_size > 0:
                    part_size = 0
                    try:
                        os.remove(part_path)
                    except OSError:
                        pass
                return await self._receive(spec, response, code, part_size, attempt)
            finally:
                await response_ctx.__aexit__(None, None, None)

    async def _receive(
        self, spec: DownloadSpec, response: httpx.Response, code: int,
        part_size: int, attempt: int,
    ) -> DownloadResult:
        file_name = os.path.basename(spec.dest_path)
        dest_dir = os.path.dirname(spec.dest_path) or "."
        part_path = spec.dest_path + ".part"
        declared_total: int | None = None
        if code == 206:
            content_range = response.headers.get("content-range", "")
            total = content_range.rsplit("/", 1)[-1] if "/" in content_range else ""
            declared_total = int(total) if total.isdigit() else None
        else:
            length = response.headers.get("content-length", "")
            declared_total = int(length) if length.isdigit() else None
        if declared_total is not None:
            expected_total = part_size + declared_total if code == 206 else declared_total
            if spec.expected_bytes is not None and expected_total != spec.expected_bytes:
                raise DownloadError(
                    "size_mismatch",
                    f"tamanho anunciado diverge do manifesto: {expected_total} "
                    f"!= {spec.expected_bytes}")
            self._check_disk(dest_dir, expected_total - part_size)

        digest = hashlib.sha256()
        received = 0
        if part_size > 0:
            try:
                with open(part_path, "rb") as existing:
                    while True:
                        raw = existing.read(_CHUNK_SIZE)
                        if not raw:
                            break
                        digest.update(raw)
            except OSError as exc:
                raise DownloadError("resume_failed", f"retomada falhou: {exc}") from exc
        try:
            mode = "ab" if part_size > 0 else "wb"
            with open(part_path, mode) as handle:
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    handle.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
        except OSError as exc:
            raise DownloadError("disk_full", f"escrita falhou: {exc}") from exc
        total = part_size + received
        if declared_total is not None and total != declared_total:
            raise DownloadError(
                "truncated_body",
                f"corpo truncado: {total} != {declared_total}")
        if spec.expected_bytes is not None and total != spec.expected_bytes:
            try:
                os.remove(part_path)
            except OSError:
                pass
            raise DownloadError(
                "size_mismatch",
                f"tamanho final diverge do manifesto: {total} != {spec.expected_bytes}")
        hexdigest = digest.hexdigest()
        if spec.expected_sha256 is not None and hexdigest != spec.expected_sha256.lower():
            try:
                os.remove(part_path)
            except OSError:
                pass
            raise DownloadError("sha256_mismatch", "SHA-256 diverge do manifesto")
        os.replace(part_path, spec.dest_path)
        logger.info("download %s ok: %d bytes (tentativa %d%s)",
                    file_name, total, attempt, ", retomado" if part_size else "")
        return DownloadResult(file_name, spec.dest_path, total, hexdigest,
                              part_size > 0, attempt, False)

    async def download_all(
        self, specs: list[DownloadSpec], *, client: httpx.AsyncClient | None = None,
    ) -> list[DownloadResult]:
        """Baixa a lista em sequência; primeira falha aborta (fail-fast)."""
        results = []
        for spec in specs:
            results.append(await self.download(spec, client=client))
        return results
