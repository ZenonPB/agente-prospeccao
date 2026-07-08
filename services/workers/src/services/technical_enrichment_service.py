import httpx
import ssl
import certifi
import re
import json
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import asyncio
import time

class TechnicalEnrichmentService:
    def __init__(self):
        self.client = httpx.AsyncClient(
            verify=certifi.where(), 
            follow_redirects=True,
            timeout=10
        )
        self.common_sensitive_paths = [
            "/robots.txt",
            "/sitemap.xml",
            "/.git/config",
            "/.env",
            "/wp-config.php",
            "/admin/",
            "/login/",
        ]

    async def _check_ssl(self, url: str) -> Dict[str, Any]:
        """Verifica o status SSL/HTTPS de uma URL."""
        ssl_info = {
            "ssl_ok": False,
            "https_redirect_ok": False,
            "ssl_issuer": None,
            "ssl_expiry_date": None,
            "error": None
        }
        parsed_url = urlparse(url)
        if parsed_url.scheme != 'https':
            ssl_info["error"] = "URL não é HTTPS."
            
            try:
                resp = await self.client.get(f"http://{parsed_url.netloc}", follow_redirects=False, timeout=5)
                if 300 <= resp.status_code < 400 and resp.headers.get('location', '').startswith('https://'):
                    ssl_info["https_redirect_ok"] = True
                    ssl_info["error"] = "Redirecionamento para HTTPS configurado."
                    return await self._check_ssl(resp.headers['location'])
            except httpx.RequestError as e:
                ssl_info["error"] = f"Erro ao verificar redirecionamento HTTP: {e}"
            return ssl_info

        try:
            resp = await self.client.get(url, timeout=5)
            resp.raise_for_status()
            ssl_info["ssl_ok"] = True
            if resp.request.url.scheme == 'https':
                ssl_info["https_redirect_ok"] = True

        except httpx.ConnectError:
            ssl_info["error"] = "Não foi possível conectar ao host (DNS, Firewall)."
        except httpx.TimeoutException:
            ssl_info["error"] = "Timeout na conexão SSL."
        except httpx.RequestError as e:
            ssl_info["error"] = f"Erro na requisição HTTPS: {e}"
        except ssl.SSLError as e:
            ssl_info["error"] = f"Erro SSL: {e}"
        
        return ssl_info

    async def _get_headers_and_status(self, url: str) -> Dict[str, Any]:
        """Obtém status HTTP e headers de segurança."""
        headers_info = {
            "status_code": None,
            "load_time_ms": None,
            "headers": {},
            "security_headers_missing": [],
            "error": None
        }
        start_time = time.time()
        try:
            resp = await self.client.get(url, timeout=10)
            end_time = time.time()
            
            headers_info["status_code"] = resp.status_code
            headers_info["load_time_ms"] = int((end_time - start_time) * 1000)
            headers_info["headers"] = {k.lower(): v for k, v in resp.headers.items()}

            # Verificar headers de segurança
            required_security_headers = {
                "x-frame-options": ["deny", "sameorigin"],
                "x-content-type-options": ["nosniff"],
                "strict-transport-security": [r".*"], 
                "content-security-policy": [r".*"], 
            }
            
            for header, expected_values in required_security_headers.items():
                if header not in headers_info["headers"]:
                    headers_info["security_headers_missing"].append(header)
                else:
                    header_value = headers_info["headers"][header]
                    if not any(re.search(pattern, header_value, re.IGNORECASE) for pattern in expected_values):
                        headers_info["security_headers_missing"].append(f"{header} (valor inesperado)")

        except httpx.RequestError as e:
            headers_info["error"] = f"Erro na requisição: {e}"
        return headers_info

    async def _detect_cms(self, url: str) -> Optional[str]:
        """Tenta detectar o CMS via headers e meta tags."""
        try:
            resp = await self.client.get(url, timeout=5)
            resp.raise_for_status()
            
            if "x-powered-by" in resp.headers and "wordpress" in resp.headers["x-powered-by"].lower():
                return "WordPress"
            if "x-generator" in resp.headers and "joomla" in resp.headers["x-generator"].lower():
                return "Joomla"

            html_content = resp.text
            if re.search(r'wp-content|wp-includes', html_content, re.IGNORECASE):
                return "WordPress"
            if re.search(r'joomla\.css|com_content', html_content, re.IGNORECASE):
                return "Joomla"
            if re.search(r'_next/', html_content, re.IGNORECASE):
                return "Next.js"
            if re.search(r'nuxt\.js', html_content, re.IGNORECASE):
                return "Nuxt.js"
            if re.search(r'drupal\.js', html_content, re.IGNORECASE):
                return "Drupal"
            if re.search(r'<meta name="generator" content="Joomla!', html_content, re.IGNORECASE):
                return "Joomla"
            if re.search(r'<meta name="generator" content="WordPress', html_content, re.IGNORECASE):
                return "WordPress"

        except httpx.RequestError:
            pass
        return None

    async def _check_sensitive_paths(self, base_url: str) -> List[str]:
        """Verifica a exposição de arquivos ou diretórios sensíveis."""
        exposed_paths = []
        for path in self.common_sensitive_paths:
            full_url = f"{base_url.rstrip('/')}{path}"
            try:
                resp = await self.client.head(full_url, timeout=5, follow_redirects=True)
                if resp.status_code == 200:
                    exposed_paths.append(path)
            except httpx.RequestError:
                pass 
        return exposed_paths

    async def enrich_website(self, website_url: str) -> Dict[str, Any]:
        """
        Executa uma análise técnica passiva de um website e retorna um relatório JSON.
        Nenhuma exploração ativa é realizada.
        """
        if not website_url:
            return {"error": "URL do website não fornecida."}

        if not website_url.startswith(("http://", "https://")):
            website_url = f"http://{website_url}"

        report: Dict[str, Any] = {
            "target_url": website_url,
            "overall_status": "OK",
            "errors": [],
            "warnings": [],
            "ssl": {},
            "http_headers": {},
            "cms_detection": None,
            "exposed_paths": [],
        }

        try:
            # Checagem SSL/HTTPS
            ssl_result = await self._check_ssl(website_url)
            report["ssl"] = ssl_result
            if not ssl_result["ssl_ok"]:
                if ssl_result["https_redirect_ok"]:
                    report["warnings"].append("Site redireciona para HTTPS, mas a URL inicial era HTTP ou SSL ainda possui algum problema.")
                else:
                    report["errors"].append(f"Problema SSL/HTTPS: {ssl_result['error'] or 'Sem certificado ou inválido'}")
                    report["overall_status"] = "PROBLEMA"
            
            # Status HTTP e Headers de Segurança
            headers_result = await self._get_headers_and_status(website_url)
            report["http_headers"] = {
                "status_code": headers_result["status_code"],
                "load_time_ms": headers_result["load_time_ms"],
                "headers": headers_result["headers"]
            }
            if headers_result["error"]:
                report["errors"].append(f"Erro ao obter headers: {headers_result['error']}")
                report["overall_status"] = "PROBLEMA"
            if headers_result["security_headers_missing"]:
                report["warnings"].append(f"Headers de segurança ausentes ou mal configurados: {', '.join(headers_result['security_headers_missing'])}")
                if "x-frame-options" in headers_result["security_headers_missing"] or "content-security-policy" in headers_result["security_headers_missing"]:
                    report["overall_status"] = "PROBLEMA"

            # Detecção de CMS
            report["cms_detection"] = await self._detect_cms(website_url)
            if report["cms_detection"] == "WordPress":
                report["warnings"].append("CMS WordPress detectado (verificar versão e plugins)")

            # Checagem de Caminhos Sensíveis
            report["exposed_paths"] = await self._check_sensitive_paths(website_url)
            if report["exposed_paths"]:
                report["errors"].append(f"Arquivos/diretórios sensíveis publicamente acessíveis: {', '.join(report['exposed_paths'])}")
                report["overall_status"] = "PROBLEMA"

        except Exception as e:
            report["errors"].append(f"Erro inesperado durante o enriquecimento: {e}")
            report["overall_status"] = "FALHA_CRITICA"
        finally:
            pass

        return report

async def main_test_enrichment():
    enricher = TechnicalEnrichmentService()
    website = "https://www.google.com"
    report = await enricher.enrich_website(website)
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError: 
        loop = None
    
    if loop and loop.is_running():
        pass
    else:
        asyncio.run(main_test_enrichment())