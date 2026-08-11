"""Detector humano-vs-IA.

Produz a probabilidade de o texto ter sido escrito por um humano, a partir das
features extraídas e do classificador serializado. O valor retornado é um
número bruto em [0, 1]; a ponderação final com os demais eixos de qualidade é
responsabilidade do `math_engine.py`.
"""
from typing import Dict, Optional

from .features import features_to_vector
from .model_store import load_model


def detect_naturalness(text: str) -> Optional[float]:
    """Retorna P(humano) em [0, 1], ou `None` se o modelo não estiver pronto.

    `None` indica "detector inativo" e deve ser tratado pelo chamador como um
    eixo sem contribuição, nunca como um erro.
    """
    model = load_model()
    if model is None:
        return None

    try:
        vector = features_to_vector(text)
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba([vector])[0]
            # Indexa a classe "humano" (1) quando binário; senão usa [0][1].
            return float(proba[1]) if len(proba) > 1 else float(proba[0])
        return float(model.predict([vector])[0])
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("Falha ao executar o detector de naturalidade.")
        return None


def naturalness_feedback(text: str) -> Optional[Dict]:
    """Empacota o resultado para o feedback do Redator.

    Retorna dict com `score` e `suggestion`, ou `None` quando o detector está
    inativo. A string de `suggestion` é a que o `prompt_builder` injeta na
    próxima iteração do pipeline.
    """
    score = detect_naturalness(text)
    if score is None:
        return None

    return {
        "score": round(score, 4),
        "suggestion": (
            "O texto aparenta baixa naturalidade humana. Varie o ritmo das frases, "
            "alterne extensões e quebre padrões repetitivos de construção."
            if score < 0.5
            else "O texto apresenta boa naturalidade humana. Mantenha o estilo."
        ),
    }
