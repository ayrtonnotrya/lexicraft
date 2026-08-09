"""Filtros customizados para templates do Dashboard."""
from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Lookup seguro de chave em dict (int ou str), retornando '' se ausente.

    Necessário porque o lookup nativo ``dict.chave`` do Django não interpreta
    variáveis como chave — apenas literais — inviabilizando acesso a índices
    dinâmicos dentro de ``{% for %}``.
    """
    if not mapping:
        return ''
    if key in mapping:
        return mapping[key]
    # Tenta normalização de tipo (int <-> str) — JSONField devolve chaves str.
    if str(key) in mapping:
        return mapping[str(key)]
    try:
        if int(key) in mapping:
            return mapping[int(key)]
    except (TypeError, ValueError):
        pass
    return ''


@register.filter
def strip(value):
    """Remove espaços e quebras de linha nas pontas do texto (safe p/ display)."""
    if value is None:
        return ''
    return str(value).strip()