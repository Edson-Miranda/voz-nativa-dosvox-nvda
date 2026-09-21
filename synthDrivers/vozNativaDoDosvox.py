# -*- coding: UTF-8 -*-
import addonHandler
import config
import logHandler
import os
import queue
import re
import threading
import time
import unicodedata

import nvwave
import synthDriverHandler
from autoSettingsUtils.driverSetting import BooleanDriverSetting, DriverSetting
from speech.commands import (
    BreakCommand,
    CallbackCommand,
    CharacterModeCommand,
    EndUtteranceCommand,
    IndexCommand,
    SynthCommand,
)
from speech.extensions import filter_speechSequence

addonHandler.initTranslation()
log = logHandler.log

MODULE_DIR = os.path.dirname(__file__)
# dosvox_native_core.py mora dentro de dosvox_data, junto com os dados que ele
# le. O que ele NAO pode e' ficar solto na raiz de synthDrivers: todo .py ali
# e' tratado pelo NVDA como candidato a driver de sintese e precisa ter uma
# classe SynthDriver -- e o nucleo nao e um driver, e' a biblioteca de apoio.
# Qualquer subpasta serve, e a importacao e relativa de pacote (nao mexe em
# sys.path), porque e' assim que o NVDA carrega os modulos de um complemento.
#
# MODULE_DIR continua sendo synthDrivers, e nao dosvox_data: e' a partir dele
# que o nucleo monta os caminhos de dosvox_data, Letras e LetrasRapidas.

# Do nucleo vem TUDO o que nao e' NVDA: a sessao (que cuida do dosvox.ini, do
# banco de difones, dos tres ajustes de voz e do fatiamento do texto) e os
# utilitarios de simbolos, que trabalham em cima do texto cru.
from .dosvox_data.dosvox_native_core import SessaoDosvox, get_available_voices  # noqa: E402
from .dosvox_data.dosvox_native_core import get_available_voice_variants  # noqa: E402
from .dosvox_data.dosvox_native_core import DIFONES_PADRAO  # noqa: E402
# Tabelas que o nucleo usa e o codigo de NVDA abaixo tambem precisa.
from .dosvox_data.dosvox_native_core import SYMBOL_SPEAK_LEVELS  # noqa: E402
from .dosvox_data.dosvox_native_core import PONTUACAO_COM_PAUSA_PROPRIA  # noqa: E402
from .dosvox_data.dosvox_native_core import PAUSAS_PADRAO  # noqa: E402
from .dosvox_data.dosvox_native_core import SYMBOL_WORDS, TYPED_SYMBOL_NAMES  # noqa: E402
from .dosvox_data.dosvox_native_core import normalize_text  # noqa: E402





# O NVDA, em certas situacoes, separa uma palavra com transicao de
# maiuscula para minuscula (tipo "PDFs") em dois itens de texto adjacentes
# na sequencia de fala, como se fossem duas palavras diferentes --
# comportamento pensado para leitura de identificadores de codigo
# (camelCase/PascalCase, tipo "minhaVariavel"), mas que atrapalha plurais
# comuns de sigla como "PDFs", "CDs", "IDs". "PDFS" (tudo maiusculo) nao
# tem essa transicao e por isso nunca e dividido, o que confirma a causa.
#
# So junta de volta quando o primeiro pedaco tem 2 letras ou mais e e TODO
# maiusculo (uma sigla de verdade, nao um artigo como "A" ou "O" sozinho,
# que tambem termina em maiuscula mas nao deveria se juntar com a palavra
# seguinte), e o segundo pedaco e curto e todo minusculo (um sufixo tipo
# "s", "es", nao uma palavra comum inteira).
_SUFIXO_MINUSCULO_CURTO_RE = re.compile(r"^[a-zà-öø-ÿ]{1,3}$")

# Aspas retas, curvas e "chevrons" (aspas em angulo, usadas em alguns
# idiomas/fontes).
_ASPAS = "\"'\u201c\u201d\u2018\u2019\u00ab\u00bb"


# ==========================================================================
#  O QUE O NVDA FAZ COM O TEXTO, E QUE PRECISA SER DESFEITO
# --------------------------------------------------------------------------
#  Tudo o que vem abaixo existe por UMA razao: o NVDA nao entrega o texto cru.
#  Ele ja o mastigou antes -- trocou "..." pela palavra "reticencias", trocou
#  "!" por "exclamacao", desmontou "1.234" e "R$ 5,00", e chama as teclas por
#  nome ("space", "f5") em vez de por caractere.
#
#  Estas funcoes desfazem isso, para que a voz possa tocar as GRAVACOES de 1993
#  em vez de sintetizar as palavras que o NVDA colocou no lugar delas.
#
#  Elas moravam no nucleo, e nao deviam. O nucleo agora nao sabe nada de NVDA:
#  entregue a ele um texto cru e ele soa igual, com ou sem este arquivo. Isso
#  importa porque o SAPI 5 entrega uma lista de fragmentos crus e o Android
#  entrega uma string crua -- nenhum dos dois vai querer nada daqui, e ter isto
#  no nucleo faria a proxima casca herdar, sem perceber, comportamento que so
#  faz sentido dentro do NVDA.
# ==========================================================================

# O NVDA tambem troca "." por "ponto" e "/" por "barra" em coisas como
# "site.com" ou "pasta/arquivo", nao so entre numeros. Reconstruir isso de
# forma ampla (qualquer "ponto" entre duas palavras) seria perigoso --
# "ponto" e uma palavra comum de verdade em portugues ("um ponto
# importante"), e viraria bagunca. Por isso, so reconstroi quando o que
# vem DEPOIS de "ponto" e um final de dominio ou extensao de arquivo bem
# conhecido -- contexto em que ninguem diria a palavra "ponto" de verdade
# como parte normal de uma frase.
_DOMINIOS_E_EXTENSOES = (
    "com", "com br", "br", "org", "net", "gov", "edu", "io", "app",
    "info", "biz", "co",
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    "html", "htm", "zip", "rar", "exe", "png", "jpg", "jpeg", "gif",
    "mp3", "mp4", "py", "js", "json", "xml",
)


def normalize_lookup_text(text):
    text = normalize_text(text).strip().lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped)

_DOMINIO_OU_EXTENSAO_RE = re.compile(
    r"(?<=[A-Za-zÀ-ÖØ-öø-ÿ])\s+ponto\s+(" + "|".join(re.escape(t) for t in _DOMINIOS_E_EXTENSOES) + r")\b",
    re.IGNORECASE | re.UNICODE,
)

# "R$" (simbolo do real) e substituido pela palavra "Reais", sempre que
# aparecer no texto, no lugar exato onde aparece.
_REAIS_RE = re.compile(r"R\$", re.IGNORECASE)


KEY_NAME_TO_CHAR = {
    # "space" e o nome interno/ingles que o NVDA pode entregar mesmo quando
    # a interface usa outro idioma; as formas portuguesas cobrem a fala
    # localizada de teclas.
    "space": " ",
    "espaco": " ",
    "espaço": " ",
    "zero": "0",
    "um": "1",
    "uma": "1",
    "dois": "2",
    "duas": "2",
    "tres": "3",
    "três": "3",
    "quatro": "4",
    "cinco": "5",
    "seis": "6",
    "sete": "7",
    "oito": "8",
    "nove": "9",
    "igual": "=",
    "sinal de igual": "=",
    "mais": "+",
    "sinal de mais": "+",
    "menos": "-",
    "sinal de menos": "-",
    "hifen": "-",
    "sublinhado": "_",
    "barra": "/",
    "barra normal": "/",
    "barra invertida": "\\",
    "contra barra": "\\",
    "arroba": "@",
    "cerquilha": "#",
    "numero": "#",
    "número": "#",
    "cifrao": "$",
    "cifrão": "$",
    "por cento": "%",
    "porcento": "%",
    "porcentagem": "%",
    "percentual": "%",
    "asterisco": "*",
    "e comercial": "&",
    "eh comercial": "&",
    "comercial e": "&",
    "abre parenteses": "(",
    "abre parentesis": "(",
    "abre parênteses": "(",
    "parentese esquerdo": "(",
    "parêntese esquerdo": "(",
    "fecha parenteses": ")",
    "fecha parentesis": ")",
    "fecha parênteses": ")",
    "parentese direito": ")",
    "parêntese direito": ")",
    "abre colchetes": "[",
    "abre colchete": "[",
    "colchete esquerdo": "[",
    "fecha colchetes": "]",
    "fecha colchete": "]",
    "colchete direito": "]",
    "abre chaves": "{",
    "abre chave": "{",
    "chave esquerda": "{",
    "fecha chaves": "}",
    "fecha chave": "}",
    "chave direita": "}",
    "ponto": ".",
    "ponto final": ".",
    "virgula": ",",
    "vírgula": ",",
    "dois pontos": ":",
    "ponto e virgula": ";",
    "ponto e vírgula": ";",
    "interrogacao": "?",
    "interrogação": "?",
    "exclamacao": "!",
    "exclamação": "!",
    "aspas": "\"",
    "aspas duplas": "\"",
    "apostrofo": "'",
    "apóstrofo": "'",
    "aspa simples": "'",
    "aspas simples": "'",
    "crase": "`",
    "grave": "`",
    "til": "~",
    "trema": "¨",
    "circunflexo": "^",
    "sublinha": "_",
    "grau": "º",
    "ordinal feminino": "ª",
    "ordinal masculino": "º",
    "a ordinal": "\u00aa",
    "feminino ordinal": "\u00aa",
    "ordinal feminina": "\u00aa",
    "o ordinal": "\u00ba",
    "masculino ordinal": "\u00ba",
    "abre angulo": "<",
    "abre ângulo": "<",
    "menor que": "<",
    "menor": "<",
    "fecha angulo": ">",
    "fecha ângulo": ">",
    "maior que": ">",
    "maior": ">",
    "barra vertical": "|",
    "pipe": "|",
    "euro": "\u20ac",
    "simbolo do euro": "\u20ac",
    "símbolo do euro": "\u20ac",
    "marcador": "\u2022",
    "bolinha": "\u2022",
    "bullet": "\u2022",
}

# Quais caracteres, num dado nivel de simbolos, de fato seriam separados do
# texto por split_source_symbols. Montada sob demanda e guardada por nivel: a
# tabela nao muda enquanto o nivel nao muda.
_CANDIDATOS_POR_NIVEL = {}


def _regex_de_candidatos(symbol_level):
    regex = _CANDIDATOS_POR_NIVEL.get(symbol_level)
    if regex is None:
        caracteres = sorted({
            ch
            for ch in set(TYPED_SYMBOL_NAMES) | set(SYMBOL_WORDS)
            if isinstance(ch, str)
            and len(ch) == 1
            and ch not in PONTUACAO_COM_PAUSA_PROPRIA
            and symbol_level >= SYMBOL_SPEAK_LEVELS.get(ch, 300)
        })
        regex = (
            re.compile("[" + re.escape("".join(caracteres)) + "]")
            if caracteres
            else False
        )
        _CANDIDATOS_POR_NIVEL[symbol_level] = regex
    return regex or None


def split_source_symbols(text, symbol_level=300):
    """Split real source symbols from text before NVDA expands their names."""
    source_text = str(text or "")
    if not source_text:
        return []
    # REJEICAO BARATA, PRIMEIRO.
    #
    # O laco abaixo percorre a string caractere a caractere em bytecode Python,
    # e ele rodava para TODA fala, na thread principal do NVDA. Numa linha longa
    # de leitura continua isso e' trabalho interpretado proporcional ao tamanho
    # do texto antes de qualquer audio existir. Uma unica varredura em C decide
    # se ha' sequer um candidato; quando nao ha', que e' o caso da prosa comum,
    # o texto sai inteiro sem laco nenhum.
    regex = _regex_de_candidatos(symbol_level)
    if regex is None or not regex.search(source_text):
        return [("text", source_text)]
    parts = []
    text_buffer = []
    for index, character in enumerate(source_text):
        # Keep numeric separators inside the text so the numeric preprocessor
        # can recognize dates, times and decimal/grouped values before symbol
        # pronunciation is considered. This is required even at "all symbols".
        is_numeric_separator = (
            character in ".,:/-"
            and index > 0
            and index + 1 < len(source_text)
            and source_text[index - 1].isdigit()
            and source_text[index + 1].isdigit()
        )
        if is_numeric_separator:
            text_buffer.append(character)
            continue
        is_known_symbol = character in TYPED_SYMBOL_NAMES or character in SYMBOL_WORDS
        should_speak = (
            character not in PONTUACAO_COM_PAUSA_PROPRIA
            and symbol_level >= SYMBOL_SPEAK_LEVELS.get(character, 300)
        )
        if is_known_symbol and should_speak:
            if text_buffer:
                parts.append(("text", "".join(text_buffer)))
                text_buffer = []
            parts.append(("symbol", character))
        else:
            text_buffer.append(character)
    if text_buffer:
        parts.append(("text", "".join(text_buffer)))
    return parts

# No original, "?", "!" e "..." sao ecoados com o wav gravado de cada
# caractere (pelo codigo ascii, na pasta de letras), nao com a palavra
# sintetizada. O NVDA, porem, ja troca esses simbolos pelo nome falado
# ("interrogacao", "exclamacao", "reticencias") antes do texto chegar ao
# O NVDA troca separadores numericos por palavra ("/" vira "barra", ":"
# vira "dois pontos") antes do texto chegar aqui, o que desmonta datas e
# horas como "07/07/2026" ou "14:30". Reconstroi o caractere original
# sempre que a palavra aparecer ENTRE DOIS NUMEROS, um contexto especifico
# o bastante para nao confundir com o uso comum dessas palavras (uma
# "barra de chocolate", um "traco no rosto"). Numeros sao a unica excecao
# tratada aqui: qualquer outra palavra (aspas, arroba, cifrao etc.) que
# apareca em texto corrido deve ser falada normalmente pelo sintetizador,
# como a palavra que e -- so na soletracao isolada (ver resolve_named_key
# e o uso de next_is_spelling_end no driver) essas palavras viram o
# caractere e o wav gravado correspondente.
_NUMERIC_SEPARATOR_WORDS_RE = re.compile(
    r"(?<=\d)\s*(barra|tra[çc]o|h[ií]fen|dois\s+pontos)\s*(?=\d)",
    re.IGNORECASE | re.UNICODE,
)

_NUMERIC_SEPARATOR_REPLACEMENTS = {
    "barra": "/",
    "traco": "-",
    "traço": "-",
    "hifen": "-",
    "hífen": "-",
}

def reconstruct_numeric_separators(text):
    def _replace(match):
        word = match.group(1).lower()
        if word.startswith("dois"):
            return ":"
        return _NUMERIC_SEPARATOR_REPLACEMENTS.get(word, match.group(0))

    return _NUMERIC_SEPARATOR_WORDS_RE.sub(_replace, text)

def reconstruct_domain_dots(text):
    return _DOMINIO_OU_EXTENSAO_RE.sub(lambda m: "." + m.group(1), text)

def reconstruct_reais(text):
    return _REAIS_RE.sub("Reais ", text)

# Reticencias (tres pontos ou mais, ou o glifo unico "…") sao um simbolo
# tipografico de verdade, presente diretamente no texto -- diferente de
# "aspas"/"arroba" que so fariam sentido reconstruir se fossem uma
# substituicao de palavra. Por isso reticencias sao tratadas aqui, sempre,
# como no dvwin.pas original: cada ponto e ecoado com o wav gravado (nunca
# apenas uma pausa, ao contrario de um ponto final isolado).
_ELLIPSIS_RE = re.compile(r"\.{3,}|\u2026")

# Caso o NVDA substitua "..." pela palavra falada "reticências" antes de
# chegar aqui (em vez de manter os pontos literais), reconhece essa palavra
# tambem -- mas so ela, nao a lista inteira de nomes de simbolos, que
# causava falsos positivos em frases comuns como "entre aspas".
_ELLIPSIS_WORD_RE = re.compile(r"\breticências\b|\breticencias\b", re.IGNORECASE | re.UNICODE)
_TEM_DIGITO_RE = re.compile(r"\d")

_ELLIPSIS_OR_WORD_RE = re.compile(
    "(?:" + _ELLIPSIS_RE.pattern + ")|(?:" + _ELLIPSIS_WORD_RE.pattern + ")",
    re.IGNORECASE | re.UNICODE,
)

def split_literal_symbols(text, pausa_ponto=PAUSAS_PADRAO.ponto):
    """Reconstroi, em qualquer lugar do texto, apenas o que e seguro
    reconstruir sem risco de falso positivo em prosa comum: separadores
    numericos (barra, dois pontos) entre digitos, e reticencias (tres
    pontos ou mais, o glifo "…", ou a palavra "reticências"). Qualquer
    outra palavra de simbolo (aspas, arroba, cifrao, abre parenteses...)
    e deixada intacta aqui e falada normalmente como palavra -- ela so
    vira caractere/wav gravado no caminho estrito de soletracao isolada.
    Devolve uma lista de tuplas ("text", trecho) e ("character", ".").
    """
    text = str(text or "")
    # Cada uma destas reconstrucoes so' e' tentada quando ha' chance real de
    # casar. Antes as tres substituicoes rodavam sempre, inclusive nas frases
    # (a maioria) onde nao ha digito, nem cifrao, nem a palavra "ponto".
    if _TEM_DIGITO_RE.search(text):
        text = reconstruct_numeric_separators(text)
    if "onto" in text or "ONTO" in text:
        text = reconstruct_domain_dots(text)
    if "$" in text:
        text = reconstruct_reais(text)
    parts = []
    pos = 0
    for match in _ELLIPSIS_OR_WORD_RE.finditer(text):
        if match.start() > pos:
            parts.append(("text", text[pos:match.start()]))
        # Replica trataPontuacao (dvwin.pas) para "...": cada ponto so eh
        # ecoado quando o PROXIMO caractere nao e espaco. Nos dois
        # primeiros pontos de "...", o proximo caractere e outro ponto,
        # entao ecoam; no terceiro, o proximo e espaco (ou fim de frase),
        # entao ele so pausa, nunca eco -- "ponto ponto" e depois uma
        # pausa muda, nao "ponto ponto ponto".
        parts.append(("character", "."))
        parts.append(("character", "."))
        parts.append(("pause", pausa_ponto))
        pos = match.end()
    if pos < len(text):
        parts.append(("text", text[pos:]))
    if not parts:
        parts.append(("text", text))
    return parts

def resolve_named_key(text):
    token = normalize_lookup_text(text)
    if not token:
        return None
    if token in KEY_NAME_TO_CHAR:
        return ("character", KEY_NAME_TO_CHAR[token])
    if re.fullmatch(r"[a-zà-öø-ÿ]", token, re.IGNORECASE):
        return ("character", text.strip())
    if re.fullmatch(r"[0-9]", token):
        return ("character", token)
    if re.fullmatch(r"f[0-9]{1,2}", token):
        return ("fkey", token[1:])
    return None


def resolver_caractere(valor):
    """Converte o nome de tecla do NVDA ("space", "f5") no caractere que a voz
    deve tocar. Era o _coerce_character_token do nucleo."""
    if not isinstance(valor, str):
        return valor
    limpo = valor.strip()
    if len(limpo) == 1:
        return limpo
    resolvido = resolve_named_key(limpo)
    if resolvido is None:
        return valor
    tipo, caractere = resolvido
    return caractere if tipo == "character" else valor



def _esta_entre_aspas(speech_sequence, index, total):
    # Uma palavra que por acaso tem o mesmo nome de um simbolo (tipo
    # "espaço", "aspas", "arroba") deve ser FALADA normalmente quando
    # aparece entre aspas de verdade no texto -- e' uma mencao a palavra
    # em si, nao um pedido para ecoar o simbolo. Aspas sao um sinal visivel
    # no proprio texto, entao checar isso diretamente e' mais confiavel do
    # que tentar adivinhar pela estrutura de comandos do NVDA. Olha tanto
    # dentro do proprio item (caso o NVDA entregue as aspas coladas na
    # palavra) quanto nos itens vizinhos (caso venham como pedacos de
    # texto proprios ao redor dela).
    item = speech_sequence[index]
    if isinstance(item, str):
        stripped = item.strip()
        if len(stripped) > 1 and stripped[0] in _ASPAS and stripped[-1] in _ASPAS:
            return True
    abre = False
    if index > 0:
        anterior = speech_sequence[index - 1]
        if isinstance(anterior, str) and anterior.rstrip()[-1:] in _ASPAS:
            abre = True
    if not abre:
        return False
    j = index + 1
    while j < total:
        proximo = speech_sequence[j]
        if isinstance(proximo, str):
            return bool(proximo) and proximo.lstrip()[:1] in _ASPAS
        j += 1
    return False


def _juntar_itens_da_sequencia(speech_sequence):
    """Desfaz, numa unica passada, as duas fragmentacoes que o NVDA introduz.

    Antes eram duas funcoes, cada uma reconstruindo a lista inteira: duas
    alocacoes por fala, na thread principal. Agora e' uma passada so', e a
    lista original e' devolvida intacta quando nada precisou mudar, que e' o
    caso comum.

    1. SIGLA MAIS SUFIXO. O NVDA, em certas situacoes, separa uma palavra com
       transicao de maiuscula para minuscula (tipo "PDFs") em dois itens
       adjacentes, comportamento pensado para identificadores de codigo
       (camelCase), mas que atrapalha plurais de sigla. So junta quando o
       primeiro pedaco tem duas letras ou mais e e' TODO maiusculo (uma sigla
       de verdade, nao um artigo como "A" sozinho) e o segundo e' um sufixo
       curto e todo minusculo.

    2. HIFEN MAIS NUMERO. Se o NVDA entregar o hifen (ou a palavra substituta)
       como um ITEM SEPARADO, a reconstrucao textual do nucleo, que so olha
       dentro de uma string, nunca chega a ver os dois juntos. Aqui a juncao
       acontece direto na lista bruta.
    """
    total = len(speech_sequence)
    resultado = None
    i = 0
    while i < total:
        item = speech_sequence[i]
        juntado = None
        if isinstance(item, str) and i + 1 < total:
            proximo = speech_sequence[i + 1]
            if isinstance(proximo, str):
                if (
                    len(item) >= 2
                    and item.isalpha()
                    and item.isupper()
                    and _SUFIXO_MINUSCULO_CURTO_RE.match(proximo)
                ):
                    juntado = item + proximo
                elif item.strip().lower() in _PALAVRAS_HIFEN and proximo[:1].isdigit():
                    juntado = "-" + proximo
        if juntado is not None:
            if resultado is None:
                resultado = list(speech_sequence[:i])
            resultado.append(juntado)
            i += 2
            continue
        if resultado is not None:
            resultado.append(item)
        i += 1
    return speech_sequence if resultado is None else resultado


# Palavras que o NVDA pode entregar no lugar do hifen, como item proprio.
_PALAVRAS_HIFEN = {"-", "traco", "traço", "hifen", "hífen", "menos"}


# O motor de fonetica ja reduz qualquer palavra para minusculo antes de
# aplicar as regras, entao normalizar a caixa do texto aqui nao tem como
# estragar nenhuma regra fonetica. Quando o NVDA fragmenta uma palavra por
# transicao de maiuscula para minuscula, pode sobrar um pedaco de caixa mista
# esquisito (por exemplo "Fs" dentro de "PDFs") que soa errado se processado
# como se fosse uma palavra normal. Palavras totalmente minusculas ou
# totalmente maiusculas ficam como estao.
_LETRAS_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")


def _normalizar_fragmentos_de_caixa_mista(texto):
    # Guarda barata: sem nenhuma maiuscula nao ha o que normalizar, e a
    # comparacao abaixo e' feita inteira em C, enquanto a substituicao chama
    # uma funcao Python uma vez por palavra.
    if texto == texto.lower():
        return texto

    def _normalizar(match):
        fragmento = match.group(0)
        if fragmento.isupper() or fragmento.islower():
            return fragmento
        return fragmento.lower()

    return _LETRAS_RE.sub(_normalizar, texto)


class DosvoxSourceSymbolCommand(SynthCommand):
    """Carries a real source symbol past NVDA's name expansion."""

    def __init__(self, character):
        self.character = character

    def __repr__(self):
        return "DosvoxSourceSymbolCommand(%r)" % self.character


# ==========================================================================
#  COMO ESTE DRIVER CONVERSA COM O NVDA
# --------------------------------------------------------------------------
#  Tres papeis, e nenhum deles invade o do outro:
#
#  1. A thread principal do NVDA so' ENFILEIRA. speak() copia a sequencia e
#     volta; cancel() incrementa um contador, esvazia a fila e manda o tocador
#     parar. Nenhuma sintese, nenhum regex pesado, nenhuma abertura de
#     dispositivo de audio acontece aqui. Era isto que fazia o teclado parecer
#     pesado: o NVDA chama cancel() uma vez por tecla.
#
#  2. A thread de sintese e' a UNICA dona do motor de voz e do tocador. Ela
#     sintetiza, entrega o audio e cria ou troca o tocador quando preciso.
#     Como ninguem mais toca nesses objetos, nao ha corrida nenhuma a
#     proteger -- inclusive as mudancas de ajuste (variante, cortafala,
#     rapidinho) viajam ate' aqui como comandos na mesma fila da fala, e por
#     isso nunca acontecem no meio de uma elocucao.
#
#  3. A thread vigia existe para uma coisa so': garantir que um indice nunca
#     se perca. Ver _Rastreador abaixo.
#
#  O QUE NUNCA SE FAZ AQUI:
#
#  * player.sync() na thread de sintese. Bloquear ate' o audio drenar deixava
#    a thread parada durante toda a reproducao (nada era preparado adiante, e
#    as pausas entre trechos cresciam), e criava a corrida classica entre
#    sync() e o stop() da thread principal, que ja' travou o proprio NVDA no
#    passado. O fim da fala agora e' avisado pelo retorno de chamada do ultimo
#    bloco de audio, que e' exatamente o momento certo.
#
#  * Trocar o tocador periodicamente. A versao anterior abria um dispositivo
#    de audio novo a cada 40 trechos para mascarar o crescimento das pausas.
#    Isso descartava, junto com o tocador velho, os retornos de chamada de
#    indice ainda pendentes -- e um indice perdido e' exatamente uma leitura
#    continua que para sozinha. A causa das pausas era o sync(); sem ele, a
#    troca periodica nao tem mais razao de existir e saiu.
# ==========================================================================

# Quanto audio se acumula antes de entregar ao dispositivo. O PRIMEIRO bloco e'
# pequeno porque e' o unico que alguem espera antes de ouvir qualquer coisa; os
# seguintes sao grandes, porque ja' sao preparados enquanto o anterior toca, e
# blocos grandes significam menos chamadas ao dispositivo de audio.
_PRIMEIRO_BLOCO = 1024
_BLOCO_ALVO = 8192

# Quantas vezes insistir na entrega de um bloco antes de desistir dele. Copiado
# do driver do IBMTTS, que trata o dispositivo de audio como algo que falha de
# vez em quando e se recupera, em vez de algo que ou funciona ou perde a fala.
_TENTATIVAS_DE_ENTREGA = 10

# Folga, em segundos, somada a duracao do audio ainda por tocar antes de o
# vigia considerar que um retorno de chamada se perdeu.
_FOLGA_DO_VIGIA = 3.0

# De quanto em quanto tempo, no maximo, vale a pena perguntar ao sistema de
# arquivos se o dosvox.ini mudou. Antes isso era um os.path.getmtime por
# elocucao, ou seja, dezenas de idas ao disco por minuto de leitura.
_INTERVALO_CHECAGEM_INI = 2.0


class _Rastreador:
    """Garante que todo evento de sincronismo de uma elocucao seja disparado.

    Evento aqui e' um indice (synthIndexReached) ou um CallbackCommand. O NVDA
    nao tem outra forma de saber onde a fala esta: a leitura continua, o
    acompanhamento do cursor e o proprio enfileiramento da proxima frase
    dependem disso, mais o synthDoneSpeaking uma vez no fim. Um unico evento
    que nao chega faz a leitura parar em silencio, sem erro nenhum no log --
    que e' precisamente o sintoma que este objeto existe para tornar
    impossivel.

    A regra e' simples e nao tem excecao: enquanto a elocucao nao foi
    cancelada, todo evento registrado acontece, pelo caminho normal (o retorno
    de chamada do bloco de audio correspondente) ou pelo caminho de emergencia
    (falha na entrega, erro inesperado, ou o vigia percebendo que o retorno de
    chamada nunca veio). Acontece tarde, se preciso, mas acontece.
    """

    __slots__ = ("_driver", "_geracao", "_lock", "_pendentes", "_fim")

    def __init__(self, driver, geracao):
        self._driver = driver
        self._geracao = geracao
        self._lock = threading.Lock()
        self._pendentes = []
        self._fim = False

    def registrar(self, evento):
        with self._lock:
            if not self._fim:
                self._pendentes.append(evento)

    def liberar(self, quantos, final=False):
        with self._lock:
            if self._fim:
                return
            if final:
                saida = self._pendentes
                self._pendentes = []
                self._fim = True
            else:
                saida = self._pendentes[:quantos]
                del self._pendentes[:quantos]
        driver = self._driver
        if not driver._cancelado(self._geracao):
            for evento in saida:
                evento()
            if final:
                driver._avisar_fim()
        if final:
            driver._desarmar_vigia(self)

    def forcar_fim(self):
        self.liberar(0, final=True)

    @property
    def terminado(self):
        with self._lock:
            return self._fim


class SynthDriver(synthDriverHandler.SynthDriver):
    name = "vozNativaDoDosvox"
    description = _("Voz nativa do DOSVOX")

    # Sem controle de velocidade. No Dosvox a velocidade nao e' um numero
    # proprio: ela E' o resultado do banco de difones escolhido, do cortafala e
    # do rapidinho. Um cursor de velocidade a mais so poderia significar
    # reamostrar o audio depois de pronto, coisa que o Dosvox nunca fez.
    # NADA VAI PARA O NVDA.INI.
    #
    # useConfig=False diz ao NVDA para nao guardar nem ler esta opcao na sua
    # propria configuracao: ela nao entra no configSpec, o loadSettings da
    # classe base a ignora e o saveSettings tambem. As quatro continuam
    # aparecendo normalmente no painel de voz -- so nao sao persistidas la.
    #
    # Quem persiste somos nos: tudo vai para o dosvox.ini, que e' a unica
    # memoria do complemento.
    supportedSettings = [
        # ATENCAO: NAO use SynthDriver.VariantSetting() aqui.
        #
        # As fabricas do NVDA (VoiceSetting, VariantSetting, RateSetting...) sao
        # classmethods SEM PARAMETRO NENHUM. Passar useConfig=False para elas
        # levanta um TypeError no CORPO DA CLASSE, o modulo inteiro deixa de
        # importar, e o sintoma e' o sintetizador sumir da lista.
        DriverSetting(
            "variant",
            _("V&ariante (banco de difones)"),
            availableInSettingsRing=True,
            defaultVal=DIFONES_PADRAO,
            displayName=_("Variante"),
            useConfig=False,
        ),
        BooleanDriverSetting(
            "cortafala",
            _("Cortar &fala (cortafala)"),
            availableInSettingsRing=True,
            defaultVal=False,
            useConfig=False,
        ),
        BooleanDriverSetting(
            "acelerarLetras",
            _("Acelerar &letras (letrasrapidas)"),
            availableInSettingsRing=True,
            defaultVal=False,
            useConfig=False,
        ),
        BooleanDriverSetting(
            "rapidinho",
            _("Aceleração e&xtra (rapidinho)"),
            availableInSettingsRing=True,
            defaultVal=False,
            useConfig=False,
        ),
        BooleanDriverSetting(
            "reduzirVolume",
            _("Reduzir &volume para 40%"),
            availableInSettingsRing=True,
            defaultVal=False,
            useConfig=False,
        ),
    ]

    # O gerenciador de fala do NVDA normalmente converte cada CallbackCommand
    # num indice proprio e executa a chamada de retorno ele mesmo quando esse
    # indice e' relatado, de modo que o driver nunca chega a ver uma. Declarar
    # suporte assim mesmo nao custa nada e cobre o caso contrario: se uma
    # versao do NVDA entregar a chamada de retorno diretamente, ela e' tratada
    # aqui com a MESMA garantia de entrega dos indices, em vez de ser
    # descartada por falta de suporte declarado.
    supportedCommands = {
        DosvoxSourceSymbolCommand,
        IndexCommand,
        CharacterModeCommand,
        BreakCommand,
        CallbackCommand,
    }
    supportedNotifications = {
        synthDriverHandler.synthIndexReached,
        synthDriverHandler.synthDoneSpeaking,
    }

    @classmethod
    def check(cls):
        return bool(get_available_voices(MODULE_DIR))

    # ---- construcao e destruicao -------------------------------------------

    def __init__(self):
        self._voice = "dosvoxNative"
        self._terminando = False
        self._state_lock = threading.RLock()
        self._player_lock = threading.RLock()
        self._generation = 0
        self._cancel_event = threading.Event()
        self._queue = queue.Queue()

        # A sessao nasce lendo (ou criando) o dosvox.ini, escolhendo o banco de
        # difones e aplicando os ajustes de voz. Depois disto o driver nao sabe
        # mais nada sobre nada disso: so pede PCM e pergunta a taxa.
        self._sessao = SessaoDosvox(MODULE_DIR)
        if self._sessao.criou_o_ini:
            log.info("vozNativaDoDosvox: dosvox.ini criado ou migrado em %s"
                     % self._sessao.caminho_ini)

        # Lidos do disco UMA vez. O painel de voz e o anel de configuracoes
        # consultam estas listas com frequencia, e varrer um diretorio a cada
        # consulta e' trabalho de disco na thread principal por nada.
        self._vozes = dict(get_available_voices(MODULE_DIR))
        self._variantes = dict(get_available_voice_variants(MODULE_DIR))
        self._sincronizar_sombras()

        self._sample_rate = self._sessao.taxa_saida
        self._output_device = self._dispositivo_configurado()
        self._player = self._criar_player(self._output_device)
        self._ultima_checagem_ini = time.monotonic()

        self._vigia_cond = threading.Condition(threading.Lock())
        self._vigia_itens = []
        self._vigia_parar = False
        self._vigia = threading.Thread(
            target=self._vigia_loop,
            name="vozNativaDoDosvox-vigia",
            daemon=True,
        )
        self._vigia.start()

        self._worker = threading.Thread(
            target=self._run,
            name="vozNativaDoDosvox-sintese",
            daemon=True,
        )
        self._worker.start()

        filter_speechSequence.register(self._preserve_source_symbols)

    def terminate(self):
        try:
            filter_speechSequence.unregister(self._preserve_source_symbols)
        except Exception:
            pass
        with self._state_lock:
            self._terminando = True
            self._generation += 1
            self._cancel_event.set()
        self._descartar_fila()
        self._desarmar_vigia(None)
        self._parar_tocador()
        self._queue.put(None)
        self._worker.join(timeout=3.0)
        if self._worker.is_alive():
            log.warning("vozNativaDoDosvox: thread de sintese nao encerrou a tempo")
        with self._vigia_cond:
            self._vigia_parar = True
            self._vigia_itens = []
            self._vigia_cond.notify_all()
        self._vigia.join(timeout=1.0)
        with self._player_lock:
            player = self._player
            self._player = None
        self._fechar_tocador(player)

    # ---- o que o NVDA chama na thread principal -----------------------------

    def speak(self, speechSequence):
        # Nada de trabalho pesado aqui. A sequencia e' copiada como veio e a
        # montagem dos segmentos (que envolve regex, normalizacao e resolucao
        # de nomes de tecla) acontece na thread de sintese.
        with self._state_lock:
            if self._terminando:
                return
            self._cancel_event.clear()
            geracao = self._generation
        self._queue.put(("falar", list(speechSequence), geracao))

    def cancel(self):
        # Chamado pelo NVDA antes de praticamente toda fala nova, ou seja, uma
        # vez por tecla digitada. Tudo aqui e' de custo constante.
        #
        # player.stop() continua sendo sincrono de proposito: e' ele que
        # garante a ordem entre o cancelamento e o speak() que o NVDA faz logo
        # em seguida, e e' ele que destrava a thread de sintese caso ela esteja
        # esperando espaco no dispositivo de audio. O que saiu daqui foi o que
        # podia bloquear de verdade: abrir dispositivo, mexer no motor e
        # esperar o audio drenar.
        with self._state_lock:
            self._generation += 1
            self._cancel_event.set()
        self._descartar_fila()
        self._desarmar_vigia(None)
        self._parar_tocador()

    def pause(self, switch):
        with self._player_lock:
            player = self._player
        if player is None:
            return
        try:
            player.pause(switch)
        except Exception:
            log.debugWarning("vozNativaDoDosvox: falha ao pausar", exc_info=True)

    # ---- ajustes: sombra na thread principal, aplicacao na de sintese -------
    #
    # Os leitores devolvem uma sombra guardada aqui, que e' so' uma leitura de
    # atributo. Os escritores enfileiram a mudanca como um comando na MESMA
    # fila da fala, entao ela e' aplicada pela thread dona do motor, entre uma
    # elocucao e outra. E' assim que trocar de banco de difones pelo anel de
    # configuracoes deixou de poder acontecer no meio de uma sintese.

    def _enfileirar_controle(self, funcao):
        with self._state_lock:
            if self._terminando:
                return
        self._queue.put(("ctl", funcao))

    def _sincronizar_sombras(self):
        sessao = self._sessao
        self._variant = sessao.difones
        self._cortafala = sessao.cortafala
        self._rapidinho = sessao.rapidinho
        self._acelerarLetras = sessao.letras_rapidas
        self._reduzirVolume = sessao.reduzir_volume
        self._interpal = sessao.interpal
        self._cortefon = sessao.cortefon
        self._sobrafon = sessao.sobrafon
        self._pausaPonto = sessao.pausa_ponto
        self._pausaVirgula = sessao.pausa_virgula
        self._pausaDoisPontos = sessao.pausa_dois_pontos
        # Usada pelo filtro, na thread principal, para as reticencias.
        self._pausa_ponto_segundos = sessao.pausas.ponto

    def _get_availableVoices(self):
        return {
            voice_id: synthDriverHandler.VoiceInfo(voice_id, label)
            for voice_id, label in self._vozes.items()
        }

    def _get_voice(self):
        return self._voice

    def _set_voice(self, value):
        if value in self._vozes:
            self._voice = value

    def _get_availableVariants(self):
        return {
            variant_id: synthDriverHandler.VoiceInfo(variant_id, label)
            for variant_id, label in self._variantes.items()
        }

    def _get_variant(self):
        return self._variant

    def _set_variant(self, value):
        if value not in self._variantes or value == self._variant:
            return
        self._variant = value
        self._enfileirar_controle(lambda: self._sessao.definir_difones(value))

    def _get_cortafala(self):
        return self._cortafala

    def _set_cortafala(self, value):
        value = bool(value)
        if value == self._cortafala:
            return
        self._cortafala = value
        self._enfileirar_controle(lambda: self._sessao.definir_cortafala(value))

    def _get_rapidinho(self):
        return self._rapidinho

    def _set_rapidinho(self, value):
        # O rapidinho nao mexe nas amostras: muda a TAXA em que elas sao tocadas
        # (11025 -> 16537 Hz), como o wavePlay do Pascal. Trocar a taxa exige
        # reabrir o dispositivo, entao a fala em curso e' interrompida (o que e'
        # o esperado ao mexer num ajuste de voz) e o tocador novo nasce na taxa
        # certa dentro da propria thread de sintese.
        value = bool(value)
        if value == self._rapidinho:
            return
        self._rapidinho = value
        self.cancel()
        self._enfileirar_controle(lambda: self._aplicar_rapidinho(value))

    def _aplicar_rapidinho(self, value):
        if self._sessao.definir_rapidinho(value):
            self._recriar_player(self._output_device)

    def _get_acelerarLetras(self):
        return self._acelerarLetras

    def _set_acelerarLetras(self, value):
        value = bool(value)
        if value == self._acelerarLetras:
            return
        self._acelerarLetras = value
        self._enfileirar_controle(lambda: self._sessao.definir_letras_rapidas(value))

    def _get_reduzirVolume(self):
        return self._reduzirVolume

    def _set_reduzirVolume(self, value):
        value = bool(value)
        if value == self._reduzirVolume:
            return
        self._reduzirVolume = value
        self._enfileirar_controle(lambda: self._sessao.definir_reduzir_volume(value))

    def _get_interpal(self):
        return self._interpal

    def _set_interpal(self, value):
        self._interpal = int(value)
        self._enfileirar_controle(lambda: self._sessao.definir_interpal(value))

    def _get_cortefon(self):
        return self._cortefon

    def _set_cortefon(self, value):
        self._cortefon = int(value)
        self._enfileirar_controle(lambda: self._sessao.definir_cortefon(value))

    def _get_sobrafon(self):
        return self._sobrafon

    def _set_sobrafon(self, value):
        self._sobrafon = int(value)
        self._enfileirar_controle(lambda: self._sessao.definir_sobrafon(value))

    def _get_pausaPonto(self):
        return self._pausaPonto

    def _set_pausaPonto(self, value):
        self._pausaPonto = int(value)
        self._enfileirar_controle(lambda: self._definir_pausa("ponto", value))

    def _get_pausaVirgula(self):
        return self._pausaVirgula

    def _set_pausaVirgula(self, value):
        self._pausaVirgula = int(value)
        self._enfileirar_controle(lambda: self._definir_pausa("virgula", value))

    def _get_pausaDoisPontos(self):
        return self._pausaDoisPontos

    def _set_pausaDoisPontos(self, value):
        self._pausaDoisPontos = int(value)
        self._enfileirar_controle(lambda: self._definir_pausa("doispontos", value))

    def _definir_pausa(self, qual, valor):
        if qual == "ponto":
            self._sessao.definir_pausa_ponto(valor)
        elif qual == "virgula":
            self._sessao.definir_pausa_virgula(valor)
        else:
            self._sessao.definir_pausa_dois_pontos(valor)
        self._pausa_ponto_segundos = self._sessao.pausas.ponto

    def loadSettings(self, onlyChanged=False):
        # O NVDA chama isto ao carregar o sintetizador e ao trocar de perfil. A
        # classe base leria do nvda.ini; nos lemos do dosvox.ini, e a leitura
        # vai para a thread dona do motor.
        #
        # Nao chamamos super() de proposito: como todas as opcoes tem
        # useConfig=False, nao ha nada no nvda.ini para ler. POReM, e' de dentro
        # do loadSettings da base que o NVDA chama changeVoice(), e e'
        # changeVoice() que reconstroi o anel de configuracoes para o
        # sintetizador atual. Sem repor essa chamada, o anel continuava
        # mostrando as definicoes do sintetizador anterior, ou lancava erro
        # quando nao havia anel anterior nenhum.
        self._enfileirar_controle(self._recarregar_do_arquivo)
        try:
            synthDriverHandler.changeVoice(self, self.voice)
        except Exception:
            log.error(
                "vozNativaDoDosvox: erro ao reconstruir o anel de configuracoes",
                exc_info=True,
            )

    def saveSettings(self):
        # A sessao ja grava a cada mudanca. O metodo precisa existir e nao pode
        # chamar super(), que escreveria no nvda.ini.
        pass

    # ---- a thread de sintese ------------------------------------------------

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            try:
                tipo = item[0]
                if tipo == "falar":
                    self._falar(item[1], item[2])
                elif tipo == "ctl":
                    item[1]()
                    self._sincronizar_sombras()
            except Exception:
                # _falar ja' garante, por conta propria, que os indices e o
                # aviso de fim saem mesmo quando algo da errado la dentro.
                log.error("vozNativaDoDosvox: erro na thread de sintese", exc_info=True)

    def _falar(self, sequencia, geracao):
        rastreador = _Rastreador(self, geracao)
        entregue = False
        total = 0
        try:
            if self._cancelado(geracao):
                return
            self._preparar_elocucao()
            nivel = self._nivel_de_simbolos()
            segmentos = self._montar_segmentos(sequencia)

            buffer_saida = bytearray()
            pendentes = 0
            primeiro = True

            def descarregar(final=False):
                nonlocal pendentes, primeiro, total, entregue
                dados = bytes(buffer_saida)
                del buffer_saida[:]
                if not dados:
                    if final:
                        # Elocucao sem audio nenhum (uma linha em branco na
                        # leitura continua, por exemplo). Os indices saem na
                        # hora, e a leitura segue sem esperar por um retorno de
                        # chamada que nunca viria.
                        rastreador.liberar(0, final=True)
                        pendentes = 0
                        entregue = True
                    return True
                quantos = pendentes
                if final:
                    ao_terminar = lambda: rastreador.liberar(quantos, final=True)
                elif quantos:
                    ao_terminar = lambda: rastreador.liberar(quantos)
                else:
                    ao_terminar = None
                if not self._entregar(dados, geracao, ao_terminar):
                    return False
                pendentes = 0
                primeiro = False
                total += len(dados)
                if final:
                    entregue = True
                return True

            for tipo, valor in segmentos:
                if self._cancelado(geracao):
                    return
                if tipo in ("index", "callback"):
                    if tipo == "index":
                        if valor is None:
                            continue
                        rastreador.registrar(lambda v=valor: self._avisar_indice(v))
                    else:
                        rastreador.registrar(lambda c=valor: self._executar_callback(c))
                    pendentes += 1
                    # Fecha o bloco aqui para que o evento caia o mais perto
                    # possivel da posicao real do audio.
                    if buffer_saida and not descarregar():
                        return
                    continue
                for pcm in self._pcm(tipo, valor, nivel):
                    if not pcm:
                        continue
                    if self._cancelado(geracao):
                        return
                    buffer_saida.extend(self._reduzir_volume_pcm(pcm) if self._reduzirVolume else pcm)
                    if len(buffer_saida) >= (_PRIMEIRO_BLOCO if primeiro else _BLOCO_ALVO):
                        if not descarregar():
                            return
            if self._cancelado(geracao):
                return
            descarregar(final=True)
        finally:
            if not entregue:
                # Cancelamento, falha de entrega ou erro inesperado. Se foi
                # cancelamento, isto nao notifica nada (o rastreador confere a
                # geracao); em qualquer outro caso, os indices pendentes e o
                # aviso de fim saem agora, e a leitura continua nao trava.
                rastreador.forcar_fim()
            elif total:
                taxa = float(self._sample_rate or self._sessao.taxa_saida)
                self._armar_vigia(rastreador, total / taxa + _FOLGA_DO_VIGIA)

    def _preparar_elocucao(self):
        # sintetiza (dvwin.pas) comeca sempre com "ultLetra := ' '" e
        # "nrepUlt := 0": o contador do clique vale por elocucao.
        self._sessao.comecar_elocucao()
        agora = time.monotonic()
        if agora - self._ultima_checagem_ini >= _INTERVALO_CHECAGEM_INI:
            self._ultima_checagem_ini = agora
            try:
                if self._sessao.recarregar():
                    self._sincronizar_sombras()
            except Exception:
                log.error("vozNativaDoDosvox: erro ao reler o dosvox.ini", exc_info=True)
        dispositivo = self._dispositivo_configurado()
        if dispositivo != self._output_device or self._sample_rate != self._sessao.taxa_saida:
            self._recriar_player(dispositivo)

    def _recarregar_do_arquivo(self):
        if self._sessao.recarregar(forcar=True):
            self._recriar_player(self._output_device)
        self._ultima_checagem_ini = time.monotonic()

    def _nivel_de_simbolos(self):
        try:
            return int(config.conf["speech"]["symbolLevel"])
        except Exception:
            return 300

    def _pcm(self, tipo, valor, nivel):
        if tipo == "pause":
            yield self._sessao.silencio(valor)
            return
        if tipo == "character":
            # O NVDA ja classificou este item como caractere ou tecla. Tenta
            # primeiro o caminho de caractere RESOLVIDO: ele nao reaplica trim
            # nem sanitizacao e, por isso, preserva o espaco literal (" ") e sua
            # gravacao _32.WAV. Sem gravacao direta, usa o caminho normal.
            caractere = resolver_caractere(valor)
            pcm = self._sessao.falar_caractere_resolvido(caractere)
            if pcm is None:
                pcm = self._sessao.falar_caractere(caractere)
            if pcm:
                yield pcm
            return
        # Fatiamento da sessao: nunca corta palavra ao meio e prefere uma
        # pontuacao natural. Cada trecho entra INTEIRO no streaming do motor.
        for texto in self._sessao.trechos(valor):
            yield from self._sessao.falar_em_fluxo(texto, symbol_level=nivel)

    @staticmethod
    def _reduzir_volume_pcm(pcm):
        return bytes(128 + int((sample - 128) * 2 / 5) for sample in pcm)

    # ---- entrega de audio ---------------------------------------------------

    def _entregar(self, dados, geracao, ao_terminar):
        tentativa = 0
        while tentativa < _TENTATIVAS_DE_ENTREGA:
            if self._cancelado(geracao):
                return False
            with self._player_lock:
                player = self._player
            if player is None:
                return False
            try:
                player.feed(dados, len(dados), onDone=ao_terminar)
                return True
            except FileNotFoundError:
                # O dispositivo de saida sumiu (fone desconectado, numero de
                # placas mudou). Reabrir e insistir e' melhor do que perder o
                # trecho, que e' o que a versao anterior fazia.
                log.debugWarning(
                    "vozNativaDoDosvox: dispositivo de audio indisponivel, reabrindo",
                    exc_info=True,
                )
                self._recriar_player(self._dispositivo_configurado())
            except TypeError:
                # Compatibilidade defensiva com um tocador sem o parametro
                # onDone. Entrega o audio e avisa na hora, como faz o driver do
                # IBMTTS: melhor um indice alguns milissegundos adiantado do que
                # um indice que nunca chega.
                try:
                    player.feed(dados)
                except Exception:
                    log.debugWarning(
                        "vozNativaDoDosvox: falha ao entregar audio ao tocador",
                        exc_info=True,
                    )
                    return False
                if ao_terminar is not None:
                    ao_terminar()
                return True
            except Exception:
                if self._cancelado(geracao):
                    return False
                log.debugWarning(
                    "vozNativaDoDosvox: falha ao entregar audio, tentando de novo",
                    exc_info=True,
                )
                time.sleep(0.01)
            tentativa += 1
        log.error("vozNativaDoDosvox: desisti de entregar um bloco de audio")
        return False

    # ---- o tocador ----------------------------------------------------------

    def _dispositivo_configurado(self):
        try:
            return config.conf["audio"]["outputDevice"]
        except Exception:
            pass
        try:
            return config.conf["speech"]["outputDevice"]
        except Exception:
            return None

    def _criar_player(self, dispositivo):
        # A taxa vem do motor: 11025 Hz, ou 16537 Hz com o rapidinho ligado.
        # E' assim que o Dosvox acelera a fala, tocando as mesmas amostras mais
        # depressa, sem tocar no audio.
        self._sample_rate = self._sessao.taxa_saida
        kwargs = {
            "channels": 1,
            "samplesPerSec": self._sample_rate,
            "bitsPerSample": 8,
        }
        if dispositivo is not None:
            kwargs["outputDevice"] = dispositivo
        return nvwave.WavePlayer(**kwargs)

    def _recriar_player(self, dispositivo):
        # So' e' chamado pela thread de sintese, e so' quando o tocador atual
        # realmente nao serve mais: taxa diferente ou dispositivo diferente.
        #
        # Trocar de tocador descarta os retornos de chamada ainda pendentes do
        # tocador velho, entao o trecho anterior e' encerrado a forca ANTES da
        # troca. Sem isso, a leitura continua ficaria esperando um indice que
        # morreu junto com o dispositivo antigo.
        self._encerrar_vigiado_agora()
        try:
            novo = self._criar_player(dispositivo)
        except Exception:
            log.error("vozNativaDoDosvox: erro ao abrir o dispositivo de audio", exc_info=True)
            return
        with self._player_lock:
            antigo = self._player
            self._player = novo
            self._output_device = dispositivo
        self._fechar_tocador(antigo)

    def _parar_tocador(self):
        with self._player_lock:
            player = self._player
        if player is None:
            return
        try:
            player.stop()
        except Exception:
            log.debugWarning("vozNativaDoDosvox: falha ao parar o tocador", exc_info=True)

    def _fechar_tocador(self, player):
        # A versao anterior so' chamava stop() e soltava a referencia, deixando
        # o fluxo de audio vivo ate' o coletor de lixo do Python passar por ele.
        if player is None:
            return
        try:
            player.stop()
        except Exception:
            pass
        try:
            player.close()
        except Exception:
            pass

    # ---- estado de cancelamento ---------------------------------------------

    def _cancelado(self, geracao):
        with self._state_lock:
            return self._cancel_event.is_set() or geracao != self._generation

    def _descartar_fila(self):
        # Esvazia a fila de FALA, mas preserva os comandos de ajuste e o
        # sentinela de encerramento: cancelar a fala nao pode engolir uma troca
        # de variante que o usuario acabou de pedir.
        guardados = []
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is None or item[0] == "ctl":
                guardados.append(item)
        for item in guardados:
            self._queue.put(item)

    # ---- notificacoes ao NVDA ------------------------------------------------

    def _avisar_indice(self, indice):
        try:
            synthDriverHandler.synthIndexReached.notify(synth=self, index=indice)
        except Exception:
            # Registrado, e nao apenas ignorado: e' este aviso que a leitura
            # continua usa para acompanhar a posicao do cursor no texto. Uma
            # falha muda aqui seria indistinguivel, para quem usa o NVDA, de a
            # leitura simplesmente parar sozinha.
            log.error(
                "vozNativaDoDosvox: erro ao notificar synthIndexReached",
                exc_info=True,
            )

    def _executar_callback(self, comando):
        try:
            if hasattr(comando, "run"):
                comando.run()
            elif callable(getattr(comando, "callback", None)):
                comando.callback()
        except Exception:
            log.error("vozNativaDoDosvox: erro executando CallbackCommand", exc_info=True)

    def _avisar_fim(self):
        try:
            synthDriverHandler.synthDoneSpeaking.notify(synth=self)
        except Exception:
            log.error(
                "vozNativaDoDosvox: erro ao notificar synthDoneSpeaking",
                exc_info=True,
            )

    # ---- o vigia -------------------------------------------------------------
    #
    # Uma unica thread, que dorme quase o tempo todo. Nada de criar um
    # temporizador por elocucao: numa leitura continua isso seria uma thread
    # nova por frase.
    #
    # Ela acompanha uma LISTA, e nao um trecho so'. Com a fala fluindo sem
    # interrupcao, a thread de sintese ja' pode estar preparando o trecho
    # seguinte enquanto o anterior ainda toca, entao mais de um trecho pode
    # estar esperando o seu aviso de fim ao mesmo tempo. Guardar so' o ultimo
    # deixaria o anterior sem rede.

    def _armar_vigia(self, rastreador, segundos):
        if rastreador.terminado:
            return
        with self._vigia_cond:
            if self._vigia_parar:
                return
            self._vigia_itens.append((time.monotonic() + segundos, rastreador))
            self._vigia_cond.notify_all()

    def _desarmar_vigia(self, rastreador):
        with self._vigia_cond:
            if rastreador is None:
                self._vigia_itens = []
            else:
                self._vigia_itens = [
                    item for item in self._vigia_itens if item[1] is not rastreador
                ]
            self._vigia_cond.notify_all()

    def _encerrar_vigiado_agora(self):
        with self._vigia_cond:
            vencidos = self._vigia_itens
            self._vigia_itens = []
            self._vigia_cond.notify_all()
        self._encerrar_a_forca(vencidos, avisar=False)

    def _encerrar_a_forca(self, itens, avisar=True):
        # A ordem importa: os trechos sao encerrados na mesma ordem em que
        # foram falados, para que os indices cheguem ao NVDA em ordem.
        for _prazo, rastreador in itens:
            if rastreador.terminado:
                continue
            if avisar:
                log.debugWarning(
                    "vozNativaDoDosvox: o tocador nao avisou o fim de um trecho; "
                    "liberando os eventos pendentes para nao travar a leitura"
                )
            rastreador.forcar_fim()

    def _vigia_loop(self):
        while True:
            with self._vigia_cond:
                while not self._vigia_itens and not self._vigia_parar:
                    self._vigia_cond.wait()
                if self._vigia_parar:
                    return
                agora = time.monotonic()
                proximo = min(prazo for prazo, _r in self._vigia_itens)
                if proximo > agora:
                    self._vigia_cond.wait(proximo - agora)
                    continue
                ultimo = max(
                    indice
                    for indice, (prazo, _r) in enumerate(self._vigia_itens)
                    if prazo <= agora
                )
                vencidos = self._vigia_itens[: ultimo + 1]
                del self._vigia_itens[: ultimo + 1]
            self._encerrar_a_forca(vencidos)

    # ---- do que o NVDA entrega ate' os segmentos de audio --------------------

    def _append_special_segments(self, segments, text, e_todo_o_texto):
        # A ajuda de teclado do NVDA manda o nome da tecla como texto seguido de
        # DOIS ESPACOS (por exemplo "a  "), sem CharacterModeCommand. E' o unico
        # sinal que ela da, e e' por isso que este metodo existe.
        #
        # O PROBLEMA: dois espacos no fim nao sao exclusividade da ajuda de
        # teclado. O NVDA separa com espaco os trechos de um texto formatado
        # (negrito, link, italico), e um trecho pode chegar aqui como "hifen  ".
        # Quando isso acontecia, a palavra virava a GRAVACAO do traco.
        #
        # A regra e' a mesma do _preserve_source_symbols: so troque uma palavra
        # pela gravacao se ela for TODO o texto da elocucao.
        if e_todo_o_texto and isinstance(text, str) and text.endswith("  "):
            stripped = text.strip()
            resolved = resolve_named_key(stripped) if stripped else None
            if resolved is not None:
                kind, value = resolved
                if kind == "character":
                    segments.append(("character", value))
                    return
                if kind == "fkey":
                    segments.append(("character", "F"))
                    segments.extend(("character", digit) for digit in value)
                    return
        segments.append(("text", text))

    def _montar_segmentos(self, speechSequence):
        segments = []
        character_mode = False
        # Quantos itens de TEXTO esta elocucao tem. Uma palavra so pode virar a
        # gravacao de um simbolo se for o texto inteiro.
        e_todo_o_texto = sum(1 for x in speechSequence if isinstance(x, str)) == 1
        for item in speechSequence:
            if isinstance(item, str):
                if character_mode:
                    stripped = item.strip()
                    if stripped:
                        resolved = resolve_named_key(stripped)
                        if resolved is not None:
                            kind, value = resolved
                            if kind == "character":
                                segments.append(("character", value))
                                continue
                            if kind == "fkey":
                                segments.append(("character", "F"))
                                for digit in value:
                                    segments.append(("character", digit))
                                continue
                    for char in item:
                        segments.append(("character", char))
                else:
                    self._append_special_segments(segments, item, e_todo_o_texto)
                continue

            if isinstance(item, DosvoxSourceSymbolCommand):
                segments.append(("character", item.character))
            elif isinstance(item, BreakCommand):
                # Pausa de verdade, inserida exatamente aqui na sequencia, nao
                # acumulada para o final (isso quebrava a posicao de toda pausa,
                # inclusive a dos parenteses).
                time_ms = max(0, int(getattr(item, "time", 0)))
                if time_ms:
                    segments.append(("pause", time_ms / 1000.0))
            elif isinstance(item, IndexCommand):
                # Fica intercalado na mesma sequencia dos segmentos de fala,
                # para o indice disparar no ponto certo do audio, e nao todos de
                # uma vez no comeco da fala.
                segments.append(("index", getattr(item, "index", None)))
            elif isinstance(item, CallbackCommand):
                segments.append(("callback", item))
            elif isinstance(item, CharacterModeCommand):
                character_mode = bool(
                    getattr(item, "state", getattr(item, "enable", getattr(item, "enabled", False)))
                )
        return segments

    # ---- o filtro, que roda na thread principal do NVDA ----------------------

    def _preserve_source_symbols(self, speech_sequence):
        """Marca os simbolos de verdade enquanto eles ainda diferem dos nomes
        escritos.

        Este e' o unico codigo deste complemento que roda na thread principal do
        NVDA, e ele roda para TODA fala, inclusive a cada tecla digitada. Por
        isso cada etapa aqui comeca por uma rejeicao barata: quando nao ha nada
        a fazer, que e' a esmagadora maioria das vezes, a sequencia sai como
        entrou sem nenhum laco em bytecode Python.
        """
        try:
            if synthDriverHandler.getSynth() is not self:
                return speech_sequence
        except Exception:
            pass
        speech_sequence = _juntar_itens_da_sequencia(speech_sequence)
        try:
            symbol_level = int(config.conf["speech"]["symbolLevel"])
        except Exception:
            symbol_level = 300
        marked = []
        character_mode = False
        total = len(speech_sequence)
        text_item_count = sum(1 for item in speech_sequence if isinstance(item, str))
        for index, item in enumerate(speech_sequence):
            if isinstance(item, CharacterModeCommand):
                character_mode = bool(
                    getattr(item, "state", getattr(item, "enable", getattr(item, "enabled", False)))
                )
                marked.append(item)
                continue
            if not isinstance(item, str) or character_mode:
                marked.append(item)
                continue
            # QUANDO UMA PALAVRA E' O NOME DE UM SIMBOLO, E QUANDO NAO E'.
            #
            # Ao soletrar um simbolo digitado, o NVDA nao manda o caractere:
            # manda o NOME dele, ja traduzido. Este filtro precisa reconhecer
            # esse nome e devolver o caractere, para que a voz toque a GRAVACAO
            # em vez de sintetizar a palavra. O sinal que o NVDA da e' que o
            # nome vem seguido de um EndUtteranceCommand -- mas isso sozinho nao
            # basta, porque o NVDA parte uma linha em varios pedacos sempre que
            # a formatacao muda, e uma frase que por acaso termina em "hifen"
            # cairia na mesma condicao.
            #
            # A regra certa e' a que o Dosvox precisa e nada alem dela: so troque
            # se a palavra for TODO o texto da elocucao.
            if (
                text_item_count == 1
                and index + 1 < total
                and isinstance(speech_sequence[index + 1], EndUtteranceCommand)
                and item.strip() == item
                and not _esta_entre_aspas(speech_sequence, index, total)
            ):
                resolved = resolve_named_key(item)
                if resolved is not None and resolved[0] == "character":
                    marked.append(DosvoxSourceSymbolCommand(resolved[1]))
                    continue
            item = _normalizar_fragmentos_de_caixa_mista(item)
            for word_kind, word_value in split_literal_symbols(item, self._pausa_ponto_segundos):
                if word_kind == "character":
                    marked.append(DosvoxSourceSymbolCommand(word_value))
                    continue
                if word_kind == "pause":
                    marked.append(BreakCommand(time=int(word_value * 1000)))
                    continue
                for kind, value in split_source_symbols(word_value, symbol_level):
                    if kind == "symbol":
                        marked.append(DosvoxSourceSymbolCommand(value))
                    elif value:
                        marked.append(value)
        return marked
