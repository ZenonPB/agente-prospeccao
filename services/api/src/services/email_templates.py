"""Templates HTML de e-mail com a identidade AlphaMec.

Segue as convenções da indústria para renderização em clientes de e-mail:

- Layout em **tabelas** (Outlook desktop não entende flexbox/grid), largura
  máx 600px e fluido no mobile.
- CSS **inline** (Gmail ignora `<style>` no corpo em muitos casos) + bloco
  `<style>` no `<head>` apenas para dark mode.
- **Preheader**: texto oculto que aparece como preview no inbox.
- **Botão CTA com fallback**: `v:roundrect` (MSO/Outlook) + `<a>` moderno.
- **Dark mode** via `prefers-color-scheme` e `[data-ogsc]` (Gmail).
- Tipografia em **system stack** — web fonts são instáveis em e-mail.

Paleta extraída do tema AlphaMec (`apps/web`): vinho #910001/#4c0000 sobre
branco quente #fffaf8, com a marca do radar como elemento de assinatura.
"""
import html
from typing import Optional

_BRAND_WORDMARK = "AlphaMec"
_BRAND_SUPTITLE = "Prospecção B2B inteligente"

_FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, "
    "Arial, sans-serif"
)


def _radar_mark(size: int = 34) -> str:
    """Marca do radar (anéis concêntricos + ping) em CSS puro.

    `border-radius` degrada para quadrado no Outlook desktop (aceitável);
    nos clientes modernos renderiza como o radar da marca.
    """
    dot_margin = size / 2 - 1
    ring = (
        f"display:inline-block;width:{size}px;height:{size}px;"
        "border:1.5px solid #910001;border-radius:50%;vertical-align:middle;"
        "box-sizing:border-box"
    )
    return (
        f'<span style="{ring}">'
        f'<span style="display:block;width:2px;height:2px;border-radius:50%;'
        f'background:#910001;margin:{dot_margin}px auto 0 auto"></span>'
        f"</span>"
    )


def _preheader(text: str) -> str:
    if not text:
        return ""
    return (
        '<!--[if !mso]><!-->'
        '<div style="display:none;font-size:1px;line-height:1px;'
        'max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">'
        f"{html.escape(text)}"
        "</div>"
        '<!--<![endif]-->'
    )


def _header(wordmark: str = _BRAND_WORDMARK, subtitle: str = "") -> str:
    subtitle_html = (
        f'<div style="font-family:{_FONT_STACK};font-size:12px;color:#7a6865;'
        f'line-height:1.3;margin-top:2px;">{html.escape(subtitle)}</div>'
        if subtitle else ""
    )
    return (
        '<tr><td style="padding:28px 32px 0 32px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr>'
        f'<td valign="middle">{_radar_mark()}</td>'
        '<td valign="middle" style="padding-left:10px;">'
        f'<div style="font-family:{_FONT_STACK};font-size:20px;font-weight:700;'
        f'color:#4c0000;line-height:1.15;">{html.escape(wordmark)}</div>'
        f"{subtitle_html}"
        "</td>"
        "</tr>"
        "</table>"
        '<div style="height:24px;line-height:24px;font-size:0;">&nbsp;</div>'
        "</td></tr>"
    )


def _outreach_header(sender_name: str, sender_email: str) -> str:
    """Cabeçalho discreto para e-mails de cadência — assinatura do vendedor."""
    return (
        '<tr><td style="padding:24px 32px 0 32px;" align="left">'
        '<table role="presentation" cellpadding="0" cellspacing="0">'
        "<tr>"
        f'<td valign="middle">{_radar_mark(26)}</td>'
        f'<td valign="middle" style="padding-left:8px;">'
        f'<div style="font-family:{_FONT_STACK};font-size:14px;font-weight:600;'
        f'color:#2d2120;">{html.escape(sender_name)}</div>'
        f'<div style="font-family:{_FONT_STACK};font-size:12px;color:#7a6865;">'
        f"{html.escape(sender_email)}</div>"
        "</td>"
        "</tr>"
        "</table>"
        '<div style="height:18px;line-height:18px;font-size:0;">&nbsp;</div>'
        "</td></tr>"
    )


def _footer(
    wordmark: str,
    business_name: str = "",
    extra_lines: Optional[list] = None,
) -> str:
    lines = list(extra_lines or [])
    if business_name:
        lines.append(business_name)
    lines.append(f"© {_BRAND_WORDMARK} · {_BRAND_SUPTITLE}")
    body = "<br/>".join(html.escape(line) for line in lines)
    return (
        '<tr><td style="padding:24px 32px 28px 32px;">'
        '<div style="border-top:1px solid #ecdcd9;margin-bottom:16px;">'
        "&nbsp;</div>"
        f'<div style="font-family:{_FONT_STACK};font-size:11px;color:#7a6865;'
        f'line-height:1.6;">{body}</div>'
        "</td></tr>"
    )


def _dark_mode_style() -> str:
    """Overrides de dark mode via media query + data-ogsc (Gmail Outlook)."""
    return (
        "@media (prefers-color-scheme: dark){"
        ".alpha-eml-body{background-color:#1c1414 !important;}"
        ".alpha-eml-card{background-color:#241b1b !important;}"
        ".alpha-eml-ink{color:#f0e6e4 !important;}"
        ".alpha-eml-muted{color:#b6a5a2 !important;}"
        "}"
    )


def _shell(
    preheader: str,
    content: str,
    card_background: str = "#ffffff",
    body_background: str = "#fffaf8",
) -> str:
    return (
        "<!DOCTYPE html>"
        '<html xmlns="http://www.w3.org/1999/xhtml" lang="pt-BR">'
        "<head>"
        '<meta name="viewport" content="width=device-width, initial-scale=1.0"/>'
        '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>'
        '<meta name="color-scheme" content="light dark"/>'
        '<meta name="supported-color-schemes" content="light dark"/>'
        f"<title>{html.escape(preheader)}</title>"
        f"<style>{_dark_mode_style()}</style>"
        "</head>"
        f'<body class="alpha-eml-body" style="background-color:{body_background};'
        f'margin:0;padding:0;-webkit-text-size-adjust:none;'
        f'font-family:{_FONT_STACK};">'
        f"{_preheader(preheader)}"
        '<table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" border="0" '
        f'style="background-color:{body_background};">'
        '<tr><td align="center" style="padding:24px 12px;">'
        f'<table role="presentation" class="alpha-eml-card" width="100%" '
        f'style="max-width:600px;background-color:{card_background};'
        "border-radius:8px;border:1px solid #ecdcd9;"
        'border-collapse:separate;overflow:hidden;">'
        f"{content}"
        "</table>"
        "</td></tr>"
        "</table>"
        "</body></html>"
    )


def render_outreach_email(
    content_html: str,
    sender_name: str,
    sender_email: str = "",
    preheader: str = "",
    footer_note: Optional[str] = None,
) -> str:
    """Template de cadência — discreto, centrado no texto do vendedor.

    Recebe o corpo já em HTML (com links rastreados e pixel, se houver).
    """
    footer_extra = [footer_note] if footer_note else []
    content = (
        _outreach_header(sender_name, sender_email)
        + f'<tr><td class="alpha-eml-ink" style="padding:0 32px;font-size:15px;'
        f'color:#2d2120;line-height:1.65;">{content_html}</td></tr>'
        + _footer(_BRAND_WORDMARK, extra_lines=footer_extra)
    )
    return _shell(preheader, content)


def _cta_button(label: str, url: str, width: int = 260) -> str:
    mso = (
        '<!--[if mso]>'
        '<v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:w="urn:schemas-microsoft-com:office:word" href="%s" '
        'style="height:44px;v-text-anchor:middle;width:%dpx;" '
        'arcsize="12%%" stroke="f" fillcolor="#910001">'
        '<w:anchorlock/><center style="color:#ffffff;font-family:Arial,'
        'sans-serif;font-size:15px;font-weight:600;">%s</center>'
        '</v:roundrect><![endif]-->' % (html.escape(url, quote=True), width, html.escape(label))
    )
    modern = (
        '<!--[if !mso]><!-->'
        '<a href="%s" style="display:inline-block;background-color:#910001;'
        'color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:6px;'
        'font-family:%s;font-size:15px;font-weight:600;">%s</a>'
        '<!--<![endif]-->' % (html.escape(url, quote=True), _FONT_STACK, html.escape(label))
    )
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f"<tr><td style=\"padding:6px 0;\">{mso}{modern}</td></tr>"
        "</table>"
    )


def render_transactional_email(
    title: str,
    body_html: str,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    fallback_url: Optional[str] = None,
    footnote: Optional[str] = None,
    preheader: str = "",
    wordmark: str = _BRAND_WORDMARK,
    subtitle: str = _BRAND_SUPTITLE,
) -> str:
    """Template transacional (reset de senha, convite) com CTA em destaque."""
    cta = ""
    if cta_label and cta_url:
        cta = (
            '<tr><td style="padding:8px 32px 0 32px;">'
            f"{_cta_button(cta_label, cta_url)}</td></tr>"
        )
    if fallback_url:
        cta += (
            '<tr><td style="padding:10px 32px 0 32px;">'
            '<div class="alpha-eml-muted" style="font-family:%s;font-size:12px;'
            'color:#7a6865;">Se o botão não funcionar, copie este link: '
            '<a href="%s" style="color:#910001;word-break:break-all;">%s</a>'
            "</div></td></tr>" % (_FONT_STACK, html.escape(fallback_url, quote=True),
                                  html.escape(fallback_url))
        )
    foot = ""
    if footnote:
        foot = (
            '<tr><td style="padding:16px 32px 0 32px;">'
            '<div class="alpha-eml-muted" style="font-family:%s;font-size:12px;'
            "color:#7a6865;\">%s</div></td></tr>"
            % (_FONT_STACK, html.escape(footnote))
        )
    content = (
        _header(wordmark, subtitle)
        + f'<tr><td style="padding:0 32px;">'
        '<div class="alpha-eml-ink" style="font-family:%s;font-size:20px;'
        'font-weight:700;color:#2d2120;line-height:1.25;margin-bottom:12px;">%s'
        "</div>"
        '<div class="alpha-eml-ink" style="font-family:%s;font-size:15px;'
        'color:#2d2120;line-height:1.65;">%s</div>'
        "</td></tr>" % (_FONT_STACK, html.escape(title), _FONT_STACK, body_html)
    )
    content += cta + foot + _footer(wordmark)
    return _shell(preheader, content)


def render_divider() -> str:
    return (
        '<tr><td style="padding:0 32px;"><div style="border-top:1px solid '
        '#ecdcd9;font-size:0;line-height:0;">&nbsp;</div></td></tr>'
    )