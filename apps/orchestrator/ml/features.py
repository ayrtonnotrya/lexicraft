"""Feature engineering para o detector humano-vs-IA.

Fonte única das métricas facilmente calculáveis sobre o texto. Os notebooks de
pesquisa importam `extract_features` deste arquivo (e não o contrário), para que
o modelo treinado e o pipeline de produção usem exatamente os mesmos vetores.

Todas as métricas são determinísticas e dependem apenas da stdlib Python
(`re`, `math`, `collections`), então rodam sem overhead no worker do Celery.
"""
import math
import re
from collections import Counter
from typing import Dict, List, Sequence

# ---------------------------------------------------------------------------
# Pré-processamento
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> List[str]:
    """Quebra o texto em sentenças usando sinais de pontuação terminais."""
    return [s for s in re.split(r"[.!?…]+", text) if s.strip()]


def _tokenize(text: str) -> List[str]:
    """Tokeniza o texto em palavras (lowercase, sem pontuação)."""
    return re.findall(r"\b[\wÀ-ÿ']+\b", text.lower())


def _n_grams(tokens: List[str], n: int) -> List[tuple]:
    """Gera n-gramas a partir de uma lista de tokens."""
    if n <= 0 or len(tokens) < n:
        return []
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


# ---------------------------------------------------------------------------
# Métricas individuais (exportadas para uso direto nos notebooks também)
# ---------------------------------------------------------------------------


def lexical_entropy(words: List[str]) -> float:
    """Entropia de Shannon da distribuição de palavras (bits).

    Textos com vocabulário mais rico e distribuído têm entropia maior. IAs
    costumam concentrar em palavras de alto score, reduzindo a entropia.
    """
    if not words:
        return 0.0
    counts = Counter(words)
    total = len(words)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def type_token_ratio(words: List[str]) -> float:
    """TTR (Type-Token Ratio): razão entre palavras distintas e totais."""
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def hapax_ratio(words: List[str]) -> float:
    """Proporção de hapax legomena (palavras que aparecem exatamente 1 vez).

    Hapax alto sugere produção léxica variada (típico de escrita humana);
    IAs tendem a repetir vocabulário.
    """
    if not words:
        return 0.0
    counts = Counter(words)
    hapax = sum(1 for c in counts.values() if c == 1)
    return hapax / len(words)


def burstiness(sentence_lengths: List[int]) -> float:
    """Burstiness = desvio-padrão / média do comprimento das sentenças.

    Mede a irregularidade do ritmo de escrita. Textos de IA tendem a frases de
    comprimento uniforme (burstiness baixo); humanos variam (burstiness alto).
    """
    if not sentence_lengths:
        return 0.0
    mean = sum(sentence_lengths) / len(sentence_lengths)
    if mean == 0:
        return 0.0
    variance = sum((x - mean) ** 2 for x in sentence_lengths) / len(sentence_lengths)
    return math.sqrt(variance) / mean


def sentence_length_std(sentence_lengths: List[int]) -> float:
    """Desvio-padrão absoluto do comprimento das sentenças (em tokens)."""
    if not sentence_lengths:
        return 0.0
    mean = sum(sentence_lengths) / len(sentence_lengths)
    variance = sum((x - mean) ** 2 for x in sentence_lengths) / len(sentence_lengths)
    return math.sqrt(variance)


def punctuation_density(text: str) -> float:
    """Densidade de sinais de pontuação por caractere.

    Captura o uso de vírgulas, dois-pontos, travessões, aspas etc., que IAs
    tendem a subutilizar.
    """
    if not text:
        return 0.0
    punctuation = re.findall(r"[,;:!?—–\"'()«»…]", text)
    return len(punctuation) / len(text)


def stopword_ratio(words: List[str]) -> float:
    """Proporção de stopwords comuns em português.

    IAs muitas vezes sobrecarregam com conectivos/formulaic transitions.
    """
    if not words:
        return 0.0
    stopwords = {
        "de", "da", "do", "das", "dos", "a", "o", "as", "os", "um", "uma",
        "e", "que", "em", "com", "para", "por", "se", "mais", "mas", "como",
        "é", "não", "na", "no", "ao", "à", "os", "mas", "então", "assim",
        "também", "muito", "podemos", "podemos", "cada", "sobre", "até",
        "entre", "quando", "porque", "pois", "sua", "seu", "ser", "ter",
        "está", "estão", "seja", "ou", "isto", "isso", "aquilo",
    }
    return sum(1 for w in words if w in stopwords) / len(words)


def perplexity(text: str) -> float:
    """Perplexidade n-grama (bigrama) com suavização de Laplace.

    Perplexidade baixa = texto previsível (padrão de IA). Como não há modelo
    de linguagem externo, treinamos um LM bigrama *no próprio texto* com
    backoff para unigrama e suavização +1. Útil como proxy de variabilidade
    local, não como perplexidade absoluta de um corpus.

    Menor é melhor em texto humano; IAs costumam ter perplexidade baixa.
    """
    tokens = _tokenize(text)
    if len(tokens) < 2:
        return 0.0

    vocab = set(tokens)
    unigram = Counter(tokens)
    bigram = Counter(_n_grams(tokens, 2))

    log_prob = 0.0
    n = len(tokens)
    for i in range(1, n):
        prev, curr = tokens[i - 1], tokens[i]
        # Probabilidade bigrama com Laplace smoothing e backoff a unigrama.
        p_bi = (bigram[(prev, curr)] + 1) / (unigram[prev] + len(vocab))
        p_uni = (unigram[curr] + 1) / (n + len(vocab))
        # Blend simples: pondera bigrama, com fallback total a unigrama se o
        # bigrama nunca foi visto (prev OOV na prática).
        prob = p_bi if unigram[prev] > 0 else p_uni
        log_prob += -math.log2(prob)

    return 2 ** (log_prob / (n - 1))


def bigram_type_token_ratio(tokens: List[str]) -> float:
    """TTR dos bigramas — captura repetição de frases/colocações.

    IAs repetem padrões de co-ocorrência; TTR de bigrama baixo indica isso.
    """
    bigrams = _n_grams(tokens, 2)
    if not bigrams:
        return 0.0
    return len(set(bigrams)) / len(bigrams)


# ---------------------------------------------------------------------------
# Vetor completo
# ---------------------------------------------------------------------------


def extract_features(text: str) -> Dict[str, float]:
    """Extrai o vetor de features de um texto.

    O retorno é um dict com chaves estáveis — a ordem e as chaves são o
    contrato com o modelo treinado (ver `feature_order()`).
    """
    sentences = _split_sentences(text)
    words = _tokenize(text)
    sentence_lengths = [len(_tokenize(s)) for s in sentences]

    features: Dict[str, float] = {
        # Tamanho e estrutura
        "n_words": float(len(words)),
        "n_sentences": float(len(sentences)),
        "avg_sentence_len": float(len(words) / len(sentences)) if sentences else 0.0,
        "avg_word_len": float(sum(len(w) for w in words) / len(words)) if words else 0.0,
        "sentence_length_std": sentence_length_std(sentence_lengths),
        # Riqueza léxica
        "lexical_entropy": lexical_entropy(words),
        "type_token_ratio": type_token_ratio(words),
        "hapax_ratio": hapax_ratio(words),
        "bigram_type_token_ratio": bigram_type_token_ratio(words),
        "stopword_ratio": stopword_ratio(words),
        # Ritmo / estilo
        "burstiness": burstiness(sentence_lengths),
        "punctuation_density": punctuation_density(text),
        # Previsibilidade
        "perplexity": perplexity(text),
    }
    return features


def feature_order() -> List[str]:
    """Retorna a ordem estável das chaves produzidas por `extract_features`.

    Usado para alinhar o vetor do DataFrame de treino com o `np.ndarray`
    esperado pelo modelo em `predict`.
    """
    return [
        "n_words",
        "n_sentences",
        "avg_sentence_len",
        "avg_word_len",
        "sentence_length_std",
        "lexical_entropy",
        "type_token_ratio",
        "hapax_ratio",
        "bigram_type_token_ratio",
        "stopword_ratio",
        "burstiness",
        "punctuation_density",
        "perplexity",
    ]


def features_to_vector(text: str) -> Sequence[float]:
    """Converte as features em vetor ordenado para o classificador.

    Garante a ordem definida por `feature_order()` independente da ordem de
    inserção no dict, evitando erro silencioso de alinhamento de colunas.
    """
    features = extract_features(text)
    return [features[key] for key in feature_order()]
