import httpx
import ssl
import re
import json
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import asyncio
import time

from services.domain_utils import extract_instagram_url

logger = logging.getLogger(__name__)

class TechnicalEnrichmentService:
    def __init__(self):
        # NÃO sondar caminhos de segredos (.env, .git,
        # wp-config.php, /admin/...) — isso é varredura ativa e contradiz a
        # postura 100% passiva (Lei 12.737/2012). Mantemos apenas arquivos que
        # qualquer visitante público acessa (SEO standard).
        self.common_public_paths = [
            "/robots.txt",
            "/sitemap.xml",
        ]
    
    def _create_client(self) -> httpx.AsyncClient:
        """Cria um novo AsyncClient para cada operação (defaults compartilhados)."""
        from services.provider_client import create_http_client
        return create_http_client(timeout=10)

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
                async with self._create_client() as client:
                    resp = await client.get(f"http://{parsed_url.netloc}", follow_redirects=False, timeout=5)
                    if 300 <= resp.status_code < 400 and resp.headers.get('location', '').startswith('https://'):
                        ssl_info["https_redirect_ok"] = True
                        ssl_info["error"] = "Redirecionamento para HTTPS configurado."
                        return await self._check_ssl(resp.headers['location'])
            except httpx.RequestError as e:
                ssl_info["error"] = f"Erro ao verificar redirecionamento HTTP: {e}"
            return ssl_info

        try:
            async with self._create_client() as client:
                resp = await client.get(url, timeout=5)
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
        """Obtém status HTTP, headers de segurança e o HTML da página em uma única requisição."""
        headers_info = {
            "status_code": None,
            "load_time_ms": None,
            "headers": {},
            "html_content": None,
            "security_headers_missing": [],
            "error": None
        }
        start_time = time.time()
        try:
            async with self._create_client() as client:
                resp = await client.get(url, timeout=10)
                end_time = time.time()
                
                headers_info["status_code"] = resp.status_code
                headers_info["load_time_ms"] = int((end_time - start_time) * 1000)
                headers_info["headers"] = {k.lower(): v for k, v in resp.headers.items()}
                headers_info["html_content"] = resp.text

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

    def _detect_cms(self, html_content: Optional[str], headers: Dict[str, str]) -> Optional[str]:
        """Detecta o CMS/tecnologia do site a partir do HTML e headers já baixados (sem nova requisição)."""
        if not html_content and not headers:
            return None

        html_lower = (html_content or "").lower()

        # WordPress + variantes (Elementor, Divi)
        if re.search(r'wp-content|wp-includes', html_lower):
            if re.search(r'elementor', html_lower):
                return "WordPress + Elementor"
            if re.search(r'\bdivi\b', html_lower):
                return "WordPress + Divi"
            return "WordPress"
        if re.search(r'<meta name="generator" content="wordpress', html_lower):
            if re.search(r'elementor', html_lower):
                return "WordPress + Elementor"
            return "WordPress"

        # Joomla
        if re.search(r'joomla\.css|com_content', html_lower):
            return "Joomla"
        if re.search(r'<meta name="generator" content="joomla', html_lower):
            return "Joomla"

        # Next.js / Nuxt.js
        if re.search(r'_next/', html_lower):
            return "Next.js"
        if re.search(r'nuxt', html_lower):
            return "Nuxt.js"

        # Drupal
        if re.search(r'drupal\.js|drupal\.settings', html_lower):
            return "Drupal"

        # Webflow
        if re.search(r'data-wf-|assets\.website-files\.com', html_lower):
            return "Webflow"

        # Wix
        if re.search(r'static\.wixstatic\.com|wix\.com', html_lower):
            return "Wix"

        # Shopify
        if re.search(r'cdn\.shopify\.com', html_lower):
            return "Shopify"

        # Squarespace
        if re.search(r'squarespace\.com', html_lower):
            return "Squarespace"

        # Google Sites
        if re.search(r'sites\.google\.com', html_lower):
            return "Google Sites"

        # Via headers HTTP
        x_powered = headers.get("x-powered-by", "").lower()
        if "php" in x_powered:
            return "PHP"
        if "asp.net" in x_powered:
            return "ASP.NET"
        if "express" in x_powered:
            return "Node.js/Express"
        if "wordpress" in x_powered:
            return "WordPress"

        x_generator = headers.get("x-generator", "").lower()
        if "joomla" in x_generator:
            return "Joomla"
        if "wordpress" in x_generator:
            return "WordPress"

        # Server não é CMS, mas registramos info útil para argumento comercial
        server = headers.get("server", "").lower()
        if "nginx" in server:
            return None  # Não é CMS, apenas infra — retorna None para não poluir

        return None

    def _check_seo(self, html_content: Optional[str]) -> Dict[str, Any]:
        """Verifica SEO básico e menção a LGPD/privacidade a partir do HTML já baixado (sem nova requisição)."""
        result = {
            "seo_title_ok": False,
            "seo_description_ok": False,
            "seo_h1_ok": False,
            "seo_title_length_ok": False,
            "lgpd_mention_found": False,
            "issues": [],
        }

        if not html_content:
            result["issues"].append("HTML não disponível para análise de SEO")
            return result

        html_lower = html_content.lower()

        # <title>
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        title_text = title_match.group(1).strip() if title_match else ""
        if not title_text:
            result["issues"].append("Tag <title> ausente ou vazia")
        else:
            result["seo_title_ok"] = True
            if not (30 <= len(title_text) <= 60):
                result["issues"].append(f"<title> com {len(title_text)} caracteres (ideal 30-60)")
            else:
                result["seo_title_length_ok"] = True

        # <meta name="description">
        desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html_content, re.IGNORECASE | re.DOTALL)
        desc_text = desc_match.group(1).strip() if desc_match else ""
        if not desc_text:
            result["issues"].append("Meta description ausente ou vazia")
        else:
            result["seo_description_ok"] = True

        # <h1>
        if re.search(r'<h1[^>]*>', html_content, re.IGNORECASE):
            result["seo_h1_ok"] = True
        else:
            result["issues"].append("Nenhum <h1> encontrado na página")

        # LGPD / privacidade (menção textual)
        if re.search(r'privacidade|política|lgpd|cookies|termos de uso', html_lower):
            result["lgpd_mention_found"] = True
        else:
            result["issues"].append("Nenhuma menção a privacidade/LGPD/cookies encontrada na home")

        return result

    def _check_ux(self, html_content: Optional[str]) -> Dict[str, Any]:
        """Verifica sinais de conversão/mobile a partir do HTML já baixado (passivo).

        Dá evidência DETERMINÍSTICA para alegações que a LLM costuma inventar
        (responsividade, formulário de contato, canais clicáveis). Sem isto, o
        gancho de abordagem alega "site não responsivo" sem ter medido nada.
        """
        result = {
            "viewport_ok": False,
            "contact_form_found": False,
            "tel_link_found": False,
            "whatsapp_link_found": False,
            "mailto_link_found": False,
            "login_portal_found": False,
            "system_mention_found": False,
            "issues": [],
        }
        if not html_content:
            result["issues"].append("HTML não disponível para análise de UX/conversão")
            return result

        html_lower = html_content.lower()

        result["viewport_ok"] = bool(re.search(r'<meta\s+name=["\']viewport["\']', html_lower))
        if not result["viewport_ok"]:
            result["issues"].append("Meta viewport ausente (provável layout não mobile-friendly)")

        result["contact_form_found"] = bool(re.search(r'<form[\s>]', html_lower))
        if not result["contact_form_found"]:
            result["issues"].append("Nenhum formulário de contato (<form>) na página")

        result["tel_link_found"] = bool(re.search(r'href=["\']tel:', html_lower))
        result["whatsapp_link_found"] = bool(
            re.search(r'wa\.me/|api\.whatsapp\.com/send', html_lower)
        )
        result["mailto_link_found"] = bool(re.search(r'href=["\']mailto:', html_lower))
        if not (result["tel_link_found"] or result["whatsapp_link_found"] or result["mailto_link_found"]):
            result["issues"].append("Nenhum canal de contato clicável (telefone/WhatsApp/e-mail) na home")

        # Área logada / portal / painel — evidência determinística de que a
        # empresa JÁ tem sistema próprio (template "Aplicações Web / ERP").
        # Sem isto, a LLM alegaria "tem portal/painel" ou "não tem" sem medir.
        result["login_portal_found"] = bool(
            re.search(
                r'login|área\s+do\s+cliente|área\s+do\s+aluno|'
                r'portal\s+do\s+(cliente|aluno)|meu\s+painel|'
                r'[\'"](?:/)?(?:login|painel|area-do-cliente|portal)[/\'"]',
                html_lower,
            )
        )
        if result["login_portal_found"]:
            result["issues"].append("Área logada/portal/painel detectado na página")

        # Menção a sistema/ERP/software — indício de automação de processos.
        result["system_mention_found"] = bool(
            re.search(r'\bsistema\b|\berp\b|\bsoftware\b', html_lower)
        )
        if result["system_mention_found"]:
            result["issues"].append("Menção a sistema/ERP/software detectada na página")

        return result

    def _rate_performance(self, load_time_ms: Optional[int]) -> Dict[str, Any]:
        """Interpreta o tempo de carregamento em uma classificação legível."""
        if load_time_ms is None:
            return {"load_time_ms": None, "is_slow": False, "rating": "não medido"}

        if load_time_ms < 1500:
            rating = "rápido"
        elif load_time_ms <= 3000:
            rating = "aceitável"
        elif load_time_ms <= 5000:
            rating = "lento"
        else:
            rating = "muito lento"

        return {
            "load_time_ms": load_time_ms,
            "is_slow": load_time_ms > 3000,
            "rating": rating,
        }

    async def _check_public_paths(self, base_url: str) -> List[str]:
        """Verifica a existência de arquivos públicos de SEO (robots/sitemap).

        100% passivo — são os arquivos que qualquer visitante acessa. Não
        sonda segredos/caminhos internos (Lei 12.737/2012).
        """
        exposed_paths = []
        async with self._create_client() as client:
            for path in self.common_public_paths:
                full_url = f"{base_url.rstrip('/')}{path}"
                try:
                    resp = await client.head(full_url, timeout=5, follow_redirects=True)
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
            "performance": {},
            "cms_detection": None,
            "seo": {},
            "ux": {},
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
            
            # Status HTTP, Headers de Segurança e HTML (uma única requisição)
            headers_result = await self._get_headers_and_status(website_url)
            html_content = headers_result.get("html_content")
            resp_headers = headers_result.get("headers", {})

            report["http_headers"] = {
                "status_code": headers_result["status_code"],
                "load_time_ms": headers_result["load_time_ms"],
                "headers": resp_headers,
                "security_headers_missing": headers_result["security_headers_missing"],
            }
            if headers_result["error"]:
                report["errors"].append(f"Erro ao obter headers: {headers_result['error']}")
                report["overall_status"] = "PROBLEMA"
            if headers_result["security_headers_missing"]:
                report["warnings"].append(f"Headers de segurança ausentes ou mal configurados: {', '.join(headers_result['security_headers_missing'])}")
                if "x-frame-options" in headers_result["security_headers_missing"] or "content-security-policy" in headers_result["security_headers_missing"]:
                    report["overall_status"] = "PROBLEMA"

            # Interpretação de performance (sem nova requisição)
            report["performance"] = self._rate_performance(headers_result["load_time_ms"])
            if report["performance"].get("is_slow"):
                report["warnings"].append(f"Site lento: {report['performance']['rating']} ({report['performance']['load_time_ms']}ms)")

            # Detecção de CMS/tecnologia (reusa HTML já baixado)
            report["cms_detection"] = self._detect_cms(html_content, resp_headers)
            if report["cms_detection"] == "WordPress":
                report["warnings"].append("CMS WordPress detectado (verificar versão e plugins)")

            # SEO + LGPD (reusa HTML já baixado)
            report["seo"] = self._check_seo(html_content)
            for issue in report["seo"].get("issues", []):
                report["warnings"].append(f"SEO/LGPD: {issue}")

            # UX/conversão (reusa HTML já baixado) — evidência determinística
            # para responsividade/formulário/canais clicáveis. A LLM só pode
            # alegar esses pontos se houver fact (grounding do pitch).
            report["ux"] = self._check_ux(html_content)
            for issue in report["ux"].get("issues", []):
                report["warnings"].append(f"UX/Conversão: {issue}")

            # Checagem de arquivos públicos de SEO (robots/sitemap):
            # sem varredura de caminhos sensíveis (.env, .git, admin/).
            report["exposed_paths"] = await self._check_public_paths(website_url)
            if report["exposed_paths"]:
                report["warnings"].append(f"Arquivos públicos presentes: {', '.join(report['exposed_paths'])}")

            # Presença social detectada no HTML — destaque para Instagram
            # (sinal de atividade digital sem site próprio).
            if html_content:
                ig = extract_instagram_url(html_content)
                if ig:
                    report["social_links"] = {"instagram": ig}
                else:
                    report["social_links"] = {}

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
    logger.info("%s", json.dumps(report, indent=2))

if __name__ == "__main__":
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError: 
        loop = None
    
    if loop and loop.is_running():
        pass
    else:
        asyncio.run(main_test_enrichment())