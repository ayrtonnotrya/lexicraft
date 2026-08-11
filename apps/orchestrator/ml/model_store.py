"""Carregamento e versionamento do modelo treinado.

Segue o padrão do `model_catalog.py`: o caminho do artefato é resolvido por
settings (ex.: `ML_MODEL_PATH`), nunca hardcoded, e degrada graciosamente quando
o modelo não está disponível (ex.: ambiente de teste ou dev sem artefato).
"""
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict = {}


def load_model(path: Optional[str] = None):
    """Carrega o classificador serializado em disco (cache em memória).

    Retorna `None` (e loga warning) caso o artefato não exista, permitindo que
    o pipeline rode sem o modelo até que o estudo seja promovido a produção.
    """
    import os

    global _MODEL_CACHE

    model_path = path or getattr(settings, "ML_MODEL_PATH", None)
    if not model_path:
        logger.debug("ML_MODEL_PATH não configurado; detector inativo.")
        return None

    cached = _MODEL_CACHE.get(model_path)
    if cached is not None:
        return cached

    if not os.path.exists(model_path):
        logger.warning("Artefato de modelo não encontrado em %s; detector inativo.", model_path)
        return None

    try:
        import joblib

        model = joblib.load(model_path)
        _MODEL_CACHE[model_path] = model
        return model
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao carregar o modelo em %s.", model_path)
        return None
