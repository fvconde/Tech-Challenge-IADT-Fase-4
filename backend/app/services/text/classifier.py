"""
Classificador supervisionado de categoria de risco (scikit-learn).

Pipeline classico do material do curso: TfidfVectorizer + MultinomialNB.
Treinamos na inicializacao a partir de um pequeno dataset SINTETICO (sem PHII),
embutido neste arquivo. Em producao real, trocariamos por um dataset maior e
rotulado por especialistas.

Por que ter o classificador ALEM do lexico (risk_lexicon.py)?
- O lexico acerta o que esta na lista; o classificador generaliza para frases
  novas com vocabulario parecido. Os dois juntos ficam mais robustos.

O sklearn e importado de forma preguicosa: se nao estiver instalado, o sistema
continua funcionando so com o lexico (predicao = None).
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Rotulo usado quando o texto nao indica risco.
SEM_RISCO = "sem_risco"

# Dataset sintetico minimo (texto, categoria). SEM dados reais de paciente.
DADOS_TREINO: list[tuple[str, str]] = [
    # depressao_pos_parto
    ("nao paro de chorar desde que o bebe nasceu e me sinto um fracasso", "depressao_pos_parto"),
    ("me sinto vazia e sem vontade de cuidar do meu filho", "depressao_pos_parto"),
    ("tenho culpa o tempo todo e nao sinto amor pelo bebe", "depressao_pos_parto"),
    ("estou exausta triste e sem esperanca depois do parto", "depressao_pos_parto"),
    ("queria sumir, me sinto inutil como mae", "depressao_pos_parto"),
    # ansiedade
    ("meu coracao fica acelerado e sinto um aperto no peito", "ansiedade"),
    ("estou muito ansiosa e preocupada, nao consigo relaxar", "ansiedade"),
    ("tive um ataque de panico e falta de ar na consulta", "ansiedade"),
    ("nao durmo direito de tao nervosa e com pensamentos acelerados", "ansiedade"),
    ("sinto muita ansiedade antes dos exames", "ansiedade"),
    # violencia_domestica
    ("meu marido me empurrou e tenho medo dele em casa", "violencia_domestica"),
    ("ele grita comigo e me proibe de sair de casa", "violencia_domestica"),
    ("apanhei e tenho vergonha de contar para alguem", "violencia_domestica"),
    ("ele me controla e me ameacou ontem", "violencia_domestica"),
    ("fico com medo quando ele chega bravo e me xinga", "violencia_domestica"),
    # fadiga_hormonal
    ("estou cansada o tempo todo e sem energia", "fadiga_hormonal"),
    ("tenho ondas de calor e alteracao de humor", "fadiga_hormonal"),
    ("minha menstruacao esta irregular e sinto muito cansaco", "fadiga_hormonal"),
    ("sem disposicao e com calores frequentes", "fadiga_hormonal"),
    ("fadiga constante e variacao de humor neste mes", "fadiga_hormonal"),
    # sem_risco
    ("estou me sentindo bem e tranquila com a gravidez", SEM_RISCO),
    ("a consulta foi otima e estou animada", SEM_RISCO),
    ("vim buscar o resultado do exame de rotina", SEM_RISCO),
    ("me sinto saudavel e apoiada pela familia", SEM_RISCO),
    ("tudo certo, so quero tirar uma duvida sobre a vitamina", SEM_RISCO),
]


@lru_cache(maxsize=1)
def _get_modelo():
    """Treina (uma unica vez) e devolve o pipeline sklearn, ou None se indisponivel."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.pipeline import Pipeline
    except ImportError:
        logger.warning("scikit-learn indisponivel; classificador desativado (so lexico).")
        return None

    from backend.app.services.text.risk_lexicon import normalizar

    textos = [normalizar(t) for t, _ in DADOS_TREINO]
    rotulos = [c for _, c in DADOS_TREINO]

    modelo = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
        ("nb", MultinomialNB()),
    ])
    modelo.fit(textos, rotulos)
    logger.info("Classificador de risco treinado (%d exemplos).", len(textos))
    return modelo


def prever_categoria(texto: str) -> tuple[str | None, float]:
    """
    Devolve (categoria_prevista, probabilidade). categoria=None se sklearn ausente.
    Se a melhor classe for SEM_RISCO, devolve (None, prob) para nao gerar alerta falso.
    """
    modelo = _get_modelo()
    if modelo is None:
        return None, 0.0

    from backend.app.services.text.risk_lexicon import normalizar

    norm = normalizar(texto)
    probas = modelo.predict_proba([norm])[0]
    classes = modelo.classes_
    idx = probas.argmax()
    categoria = classes[idx]
    prob = float(probas[idx])

    if categoria == SEM_RISCO:
        return None, prob
    return categoria, prob
