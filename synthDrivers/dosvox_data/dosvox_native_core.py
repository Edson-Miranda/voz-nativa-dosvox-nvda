# -*- coding: UTF-8 -*-
import collections
import configparser
from decimal import Decimal
import os
import re
import struct
import unicodedata
import wave


# TUDO o que o nucleo le mora dentro de UMA pasta so: dosvox_data. Difones,
# indices, regras, excecoes, dosvox.ini, e as duas pastas de gravacoes de
# letras. Quem for portar o nucleo so precisa apontar para essa pasta.
VOICE_DIR_NAME = "dosvox_data"
DEFAULT_VOICE_ID = "Difones2"
LETTERS_DIR_NAME = "Letras"
LETTERS_DIR_RAPIDO_NAME = "LetrasRapidas"


def cp1252_code(character):
    """Converte um caractere para o codigo da pagina 1252 (o Pascal
    original le e escreve texto direto em CP1252, e ord(c) ali ja da o
    byte certo). Em Python, ord() da o codepoint Unicode, que so bate com
    o byte CP1252 para os caracteres comuns (0 a 127) e para a maior parte
    dos acentuados (160 a 255); diverge exatamente na faixa 128 a 159, que
    na CP1252 tem aspas curvas, travessao, reticencias tipograficas etc.
    """
    try:
        encoded = character.encode("cp1252")
    except (UnicodeEncodeError, LookupError):
        return None
    if len(encoded) != 1:
        return None
    return encoded[0]


VOGAIS_DOSVOX = set("aeiouwyAEIOU")
CONSOANTES_DOSVOX = set("bcdfgjklmnpqrstvxz")
SEMIVOGAIS_DOSVOX = set("yw")
ACENTOS_DOSVOX = set("^~")

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+$", re.UNICODE)

UNITS = [
    "",
    "um",
    "dois",
    "tres",
    "quatro",
    "cinco",
    "seis",
    "sete",
    "oito",
    "nove",
]
TEENS = {
    10: "dez",
    11: "onze",
    12: "doze",
    13: "treze",
    14: "quatorze",
    15: "quinze",
    16: "dezesseis",
    17: "dezessete",
    18: "dezoito",
    19: "dezenove",
}
TENS = {
    20: "vinte",
    30: "trinta",
    40: "quarenta",
    50: "cinquenta",
    60: "sessenta",
    70: "setenta",
    80: "oitenta",
    90: "noventa",
}
HUNDREDS = {
    100: "cem",
    200: "duzentos",
    300: "trezentos",
    400: "quatrocentos",
    500: "quinhentos",
    600: "seiscentos",
    700: "setecentos",
    800: "oitocentos",
    900: "novecentos",
}
MONTH_NAMES = {
    1: "janeiro",
    2: "fevereiro",
    3: "marco",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

# Palavras que, dentro da leitura de um numero (nunca em prosa comum),
# representam na verdade um simbolo com gravacao propria por codigo
# CP1252 na pasta de letras -- devem tocar esse wav, nao ser sintetizadas.
NUMBER_SYMBOL_WORD_TO_CHAR = {
    "ponto": ".",
    "virgula": ",",
    "menos": "-",
    "mais": "+",
    "igual": "=",
    "barra": "/",
    "hifen": "-",
}

SYMBOL_WORDS = {
    "@": "arroba",
    "#": "cerquilha",
    "$": "cifrao",
    "%": "por cento",
    "&": "e comercial",
    "*": "asterisco",
    "+": "mais",
    "=": "igual",
    "/": "barra",
    "\\": "barra invertida",
    "_": "sublinhado",
    "|": "barra vertical",
    "<": "menor que",
    ">": "maior que",
    "\"": "aspas",
    "`": "crase",
    "~": "til",
    "^": "circunflexo",
    "\u00aa": "ordinal feminino",
    "\u00ba": "ordinal masculino",
    "\u20ac": "euro",
    "\u2022": "marcador",
}

PAUSE_CHARS = set(".,;:!?()[]{}-")

CHARACTER_NAMES = {
    "a": "a",
    "b": "bê",
    "c": "cê",
    "d": "dê",
    "e": "e",
    "f": "éfe",
    "g": "gê",
    "h": "agá",
    "i": "i",
    "j": "jota",
    "k": "cá",
    "l": "éle",
    "m": "eme",
    "n": "ene",
    "o": "o",
    "p": "pê",
    "q": "quê",
    "r": "erre",
    "s": "éssi",
    "t": "tê",
    "u": "u",
    "v": "vê",
    "w": "dáblio",
    "x": "xis",
    "y": "ípsilon",
    "z": "zê",
    "0": "zero",
    "1": "um",
    "2": "dois",
    "3": "três",
    "4": "quatro",
    "5": "cinco",
    "6": "seis",
    "7": "sete",
    "8": "oito",
    "9": "nove",
    "á": "a agudo",
    "à": "a crase",
    "â": "a circunflexo",
    "ã": "a til",
    "ä": "a trema",
    "é": "e agudo",
    "è": "e crase",
    "ê": "e circunflexo",
    "ë": "e trema",
    "í": "i agudo",
    "ì": "i crase",
    "î": "i circunflexo",
    "ï": "i trema",
    "ó": "o agudo",
    "ò": "o crase",
    "ô": "o circunflexo",
    "õ": "o til",
    "ö": "o trema",
    "ú": "u agudo",
    "ù": "u crase",
    "û": "u circunflexo",
    "ü": "u trema",
    "ç": "cê cedilha",
}

TYPED_SYMBOL_NAMES = {
    ".": "ponto",
    ",": "virgula",
    ";": "ponto e virgula",
    ":": "dois pontos",
    "!": "exclamação",
    "?": "interrogacao",
    "(": "abre parenteses",
    ")": "fecha parenteses",
    "[": "abre colchetes",
    "]": "fecha colchetes",
    "{": "abre chaves",
    "}": "fecha chaves",
    "<": "menor que",
    ">": "maior que",
    "/": "barra",
    "\\": "barra invertida",
    "+": "mais",
    "-": "hifen",
    "_": "sublinhado",
    "=": "igual",
    "*": "asterisco",
    "\"": "aspas",
    "'": "apostrofo",
    "`": "crase",
    "~": "til",
    "^": "circunflexo",
    "@": "arroba",
    "#": "cerquilha",
    "$": "cifrao",
    "%": "por cento",
    "&": "e comercial",
    "|": "barra vertical",
    "\u00aa": "ordinal feminino",
    "\u00ba": "ordinal masculino",
    "\u20ac": "euro",
    "\u2022": "marcador",
}


# No dvwin.pas original, sintFalaPont vem fixo em "true" no codigo (nao e
# lido de nenhum arquivo de configuracao) e faz TODA pontuacao ser ecoada
# com o wav gravado, sem checar nivel de simbolo nenhum - esse conceito de
# "nivel" e uma convencao do NVDA, nao existe no dosvox original. Por isso,
# os simbolos abaixo usam limiar zero: sempre sao ecoados, nao importa o
# nivel de pontuacao configurado no NVDA. ".", ",", ";", ":", "(", ")" e
# "-" sao excecao aqui, pois tem uma pausa contextual propria depois do
# eco (ver _pause_duration_for_token) e ficam de fora da extracao
# preferencial em split_source_symbols para nao perder essa pausa; seus
# limiares ficam como estavam.
SYMBOL_SPEAK_LEVELS = {
    ".": 100,
    ",": 100,
    "!": 0,
    "?": 0,
    ":": 200,
    ";": 200,
    "(": 0,
    ")": 0,
    "[": 0,
    "]": 0,
    "{": 0,
    "}": 0,
    "<": 0,
    ">": 0,
    "/": 0,
    "\\": 0,
    "+": 0,
    "-": 200,
    "_": 0,
    "=": 0,
    "*": 0,
    "\"": 0,
    "'": 0,
    "`": 0,
    "~": 0,
    "^": 0,
    "@": 0,
    "#": 0,
    "$": 0,
    "%": 0,
    "&": 0,
    "|": 0,
    "\u00aa": 0,
    "\u00ba": 0,
    "\u20ac": 0,
    "\u2022": 0,
}

# Simbolos que ja tem uma pausa contextual propria depois do eco (a mesma
# logica de trataPontuacao no dvwin.pas). Ficam de fora da extracao
# preferencial de split_source_symbols, para continuar passando pelo
# caminho normal do texto, que e quem aplica essa pausa; sao sempre
# ecoados de qualquer forma, so que por esse outro caminho.
PONTUACAO_COM_PAUSA_PROPRIA = set(".,;:()-")



DIRECT_WORD_SOUND_KEYS = {
    "e",
    "de",
    "zero",
    "um",
    "uma",
    "dois",
    "duas",
    "tres",
    "quatro",
    "cinco",
    "seis",
    "sete",
    "oito",
    "nove",
    "dez",
    "onze",
    "doze",
    "treze",
    "quatorze",
    "quinze",
    "dezesseis",
    "dezessete",
    "dezoito",
    "dezenove",
    "vinte",
    "trinta",
    "quarenta",
    "cinquenta",
    "sessenta",
    "setenta",
    "oitenta",
    "noventa",
    "cem",
    "cento",
    "duzentos",
    "trezentos",
    "quatrocentos",
    "quinhentos",
    "seiscentos",
    "setecentos",
    "oitocentos",
    "novecentos",
    "mil",
    "milhao",
    "milhoes",
    "bilhao",
    "bilhoes",
    "trilhao",
    "trilhoes",
    "menos",
    "hora",
    "horas",
    "minuto",
    "minutos",
    "virgula",
    "ponto",
    "por",
    "cento",
    "janeiro",
    "fevereiro",
    "marco",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
}

# Several original Dosvox recordings use DOS-era, shortened filenames.
DIRECT_WORD_SOUND_ALIASES = {
    "trilhoes": ("_trilhoe",),
    "quatorze": ("_quatorz",),
    "dezesseis": ("_dezesse",),
    "dezessete": ("_dezeset",),
    "dezenove": ("_dezenov",),
    "quarenta": ("_quarent",),
    "cinquenta": ("_cinquen",),
    "sessenta": ("_sessent",),
    "duzentos": ("_duzento", "_duzent"),
    "trezentos": ("_trezent",),
    "quatrocentos": ("_quatroc",),
    "quinhentos": ("_quinhen",),
    "seiscentos": ("_seiscen",),
    "setecentos": ("_setecen",),
    "oitocentos": ("_oitocen",),
    "novecentos": ("_novecen",),
    "fevereiro": ("_feverei",),
    "abril": ("abril",),
    "setembro": ("_setembr",),
    "novembro": ("_novembr",),
    "dezembro": ("_dezembr",),
}

DIRECT_CHARACTER_SOUND_KEYS = {
    " ": ("32", "_32", "032", "_032"),
    "\"": ("_34", "_vo34"),
    "%": ("37", "_37"),
    "&": ("38", "_38"),
    "(": ("40", "_40", "_vo40"),
    ")": ("41", "_41", "_vo41"),
    ":": ("_58", "_vo58"),
    ";": ("_59", "_vo59"),
    "<": ("60", "_60"),
    ">": ("62", "_62"),
    "_": ("95", "_95"),
    "`": ("96", "_96"),
    "{": ("123", "_123"),
    "|": ("124", "_124"),
    "}": ("125", "_125"),
    "\u20ac": ("128", "_128"),
    "\u2022": ("149", "_149"),
    "[": ("_91", "_vo91"),
    "]": ("_93", "_vo93"),
}

def normalize_text(text):
    text = unicodedata.normalize("NFC", text)
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00a0": " ",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def _eh_invisivel(character):
    """Replica Descricoes.kt: controles/formato e faixas de largura zero sao mudos."""
    cp = ord(character)
    if cp in (0x20, 0x09, 0x0A, 0x0B, 0x0C, 0x0D):
        return False
    if cp < 0x20 or cp == 0x7F or 0x80 <= cp <= 0x9F:
        return True
    if cp in (0x00AD, 0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180E, 0x3164, 0xFEFF, 0xFFA0):
        return True
    if 0x200B <= cp <= 0x200F or 0x202A <= cp <= 0x202E or 0x2060 <= cp <= 0x206F:
        return True
    if 0xFE00 <= cp <= 0xFE0F or 0xFFF9 <= cp <= 0xFFFB or 0x1D173 <= cp <= 0x1D17A or 0xE0000 <= cp <= 0xE0FFF:
        return True
    return unicodedata.category(character) in ("Cf", "Cc")


class DescricoesCP1252:
    def __init__(self, path):
        self.mapa = {}
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                for raw in f:
                    line = raw.rstrip("\r\n")
                    if not line or line.startswith("#") or "\t" not in line:
                        continue
                    key, value = line.split("\t", 1)
                    value = value.strip()
                    if len(key) != 1 or not value or _eh_invisivel(key):
                        continue
                    self.mapa[ord(key)] = value
        except OSError:
            pass

    def aplicar(self, texto_in):
        texto = normalize_text(texto_in)
        if not texto:
            return texto
        invisiveis = [_eh_invisivel(ch) for ch in texto]
        if any(invisiveis) and all(invisiveis):
            return ""
        out = []
        for ch in texto:
            if _eh_invisivel(ch):
                out.append(" ")
                continue
            value = self.mapa.get(ord(ch))
            if value is not None:
                out.extend((" ", value, " "))
            elif cp1252_code(ch) is not None:
                out.append(ch)
            else:
                out.append(" ")
        return "".join(out)


def normalize_sound_key(text):
    text = normalize_text(text).lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    stripped = stripped.replace("ç", "c")
    return re.sub(r"[^a-z0-9]+", "", stripped)




# O Dosvox nunca teve controle de volume nem de tom: sintParam (dvwin.pas)
# so recebe quanto, minimo, intervalo, corta e acelera. O volume e do
# sistema, e o tom simplesmente nao existe num sintetizador concatenativo
# de difones gravados. Este modulo, portanto, nao reamostra, nao muda ganho
# e nao muda tom: o PCM que sai daqui e' a concatenacao crua das gravacoes,
# com o cortafala quando pedido, e mais nada.
RAPIDINHO_FATOR = 1.5

# Taxa nativa dos difones e das gravacoes de letras: geraCabWav, em
# dvinter.pas, escreve o cabecalho como 11025 Hz, 8 bits, 1 canal.
TAXA_BASE = 11025

# Taxa com o rapidinho ligado. O Pascal NAO reamostra nada: em wavePlay
# (dvwav.pas) ele so manda o dispositivo de audio tocar as MESMAS amostras
# mais depressa, com "veloc := trunc (veloc * 1.5)". A versao anterior deste
# modulo decimava as amostras por 1,5 e continuava tocando a 11025 Hz, o que
# joga fora uma amostra a cada tres e introduz um chiado de reconstrucao que
# o Dosvox nao tem. Agora a saida sai intacta e quem muda de taxa e' o
# tocador -- exatamente como no original, inclusive na subida de tom.
TAXA_RAPIDINHO = int(TAXA_BASE * RAPIDINHO_FATOR)


# Porte fiel do "cortafala" de dvwav.pas (waveCompact + o laco de blocos de
# wavePlay). A fala inteira ja concatenada e fatiada em blocos de
# MAXBUFSIZE_CORTAFALA bytes (mesmo valor de MAXBUFSIZE no Pascal), cada
# bloco e comprimido de forma independente, buscando pontos de amplitude
# maxima e descartando o trecho entre um pico e o proximo, exatamente como
# o Pascal faz durante a reproducao. Os difones ja sao 8 bits sem sinal,
# silencio = 128, 11025 Hz, entao a conversao de 16 para 8 bits do Pascal
# nao se aplica aqui.
MAXBUFSIZE_CORTAFALA = 8192


def _wave_compact_block(pmem, size, fator=1):
    if size < 1000:
        return size
    d1, d2, d3 = 200 * fator, 80 * fator, 50 * fator
    if size <= d1 + d2 + d3:
        return size
    maximo = 0
    posmax = 0
    for i in range(d1, min(d1 + d2 + d3, size - 1) + 1):
        if pmem[i] > maximo:
            maximo, posmax = pmem[i], i
    origem = destino = posmax
    while origem < size - 2 * (d2 + d3):
        maximo = 0
        origem += d2
        for i in range(origem, min(origem + d3, size - 1) + 1):
            if pmem[i] > maximo:
                maximo, posmax = pmem[i], i
        origem = posmax
        maximo = 0
        for i in range(origem + d2, min(origem + d2 + d3, size - 1) + 1):
            if pmem[i] > maximo:
                maximo, posmax = pmem[i], i
        tam = posmax - origem + 1
        snap = pmem[origem:origem + tam]
        pmem[destino:destino + tam] = snap
        origem = posmax
        destino += tam
    while origem < size and abs(pmem[min(destino, size - 1)] - 128) > 20:
        pmem[destino] = pmem[origem]
        destino += 1
        origem += 1
    return destino


def apply_cortafala_to_pcm(pcm_bytes, rapidinho=False):
    if not pcm_bytes:
        return pcm_bytes
    fator = 4 if rapidinho else 1
    out = bytearray()
    for pos in range(0, len(pcm_bytes), MAXBUFSIZE_CORTAFALA):
        block = bytearray(pcm_bytes[pos:pos + MAXBUFSIZE_CORTAFALA])
        novo = _wave_compact_block(block, len(block), fator)
        out.extend(block[:novo])
    return bytes(out)


def _silencio_amostras(segundos):
    espaco = int(TAXA_BASE * max(0.0, segundos))
    return (espaco // 100) * 100


# --- leitura fiel do dosvox.ini -------------------------------------------
# Replica sintAmbiente/val de dvwin.pas: um valor ausente ou invalido no INI
# cai no padrao, sem lancar erro.
#
# NAO HA MAIS NIVEIS DE VELOCIDADE. O Dosvox tinha cinco, escolhidos por um
# VELOCIDADE em [TRADUTOR], e cada um era um bloco de parametros numerados. Isso
# saiu inteiro: nao ha velocidade, nao ha nivel, nao ha bloco. Ha o banco de
# difones e os parametros dele, e mais nada.


def _val_int_dosvox(texto, default):
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return default


def aplicar_config_no_motor(synth, config):
    """Aplica no motor os parametros que vem do dosvox.ini e nao tem caixa de
    selecao no painel: o silencio entre silabas, o corte de difone atono
    (CORTEFON/SOBRAFON) e as tres pausas de pontuacao."""
    synth.definir_interpal(config["interpal"])
    synth.definir_cortefon(config["cortefon"])
    synth.definir_sobrafon(config["sobrafon"])
    synth.definir_pausas(Pausas.de_ms(
        config["pausaponto_ms"], config["pausavirg_ms"], config["pausadoispontos_ms"]
    ))


# ==========================================================================
#  O dosvox.ini
# --------------------------------------------------------------------------
#  Uma secao, dez chaves, tudo em maiuscula, sem comentario nenhum. Nada vai
#  para o nvda.ini.
#
#  Todos os parametros sao persistidos exclusivamente neste arquivo; o
#  nvda.ini nao se torna uma segunda fonte de verdade. O painel nativo do NVDA
#  expoe somente variante e opcoes booleanas. Parametros numericos avancados
#  permanecem aqui porque NumericDriverSetting seria apresentado como slider.
# ==========================================================================

DIFONES_PADRAO = "DIFONES2"
CORTEFON_MAX = 400
SOBRAFON_MAX = 1200
INTERPAL_MAX = 2000
PAUSA_MAX = 2000

CONFIG_PADRAO = {
    "difones": DIFONES_PADRAO,
    "interpal": 0,
    # CORTEFON/SOBRAFON de falaDifone (dvinter.pas): quantas amostras se tira do
    # fim de um difone atono e o piso que deve sobrar. O padrao atual do Kotlin
    # e 0/0; CORTEFON=0 desliga o corte.
    "cortefon": 0,
    "sobrafon": 0,
    "cortafala": False,
    "letras_rapidas": False,
    "rapidinho": False,
    "pausaponto_ms": 150,
    "pausavirg_ms": 50,
    "pausadoispontos_ms": 100,
    "reduzir_volume": False,
}

# Ordem exata das linhas do arquivo, e o nome de cada chave nele.
LINHAS_DOSVOX_INI = (
    ("difones", "DIFONES"),
    ("interpal", "INTERPAL"),
    ("cortefon", "CORTEFON"),
    ("sobrafon", "SOBRAFON"),
    ("cortafala", "CORTAFALA"),
    ("letras_rapidas", "LETRASRAPIDAS"),
    ("rapidinho", "RAPIDINHO"),
    ("pausaponto_ms", "PAUSAPONTO"),
    ("pausavirg_ms", "PAUSAVIRG"),
    ("pausadoispontos_ms", "PAUSADOISPONTOS"),
    ("reduzir_volume", "REDUZIRVOLUME"),
)

CHAVES_LIGA_DESLIGA = ("cortafala", "letras_rapidas", "rapidinho", "reduzir_volume")


def _sim_nao(valor):
    return "SIM" if valor else "NAO"


def _le_sim_nao(texto, padrao=False):
    texto = (texto or "").strip().upper()
    if texto in ("SIM", "S", "1", "TRUE", "YES"):
        return True
    if texto in ("NAO", "N\u00c3O", "N", "0", "FALSE", "NO"):
        return False
    return padrao


def _todas_as_chaves(caminho_ini):
    """Todas as chaves do arquivo num dicionario so, em maiuscula, ignorando em
    que secao estao. Ler por chave, e nao por secao, torna a leitura imune ao
    nome e a caixa da secao."""
    parser = configparser.ConfigParser()
    parser.optionxform = str.upper
    for codificacao in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(caminho_ini, "r", encoding=codificacao) as arquivo:
                parser.read_file(arquivo)
            break
        except UnicodeDecodeError:
            parser = configparser.ConfigParser()
            parser.optionxform = str.upper
            continue
        except (OSError, configparser.Error):
            return None
    else:
        return None
    chaves = {}
    for secao in parser.sections():
        for chave, valor in parser.items(secao):
            chaves[chave.upper()] = valor
    return chaves


def ler_dosvox_ini(caminho_ini):
    """Le o arquivo. O que faltar vira padrao de fabrica, entao um arquivo
    truncado, vazio ou inexistente nunca derruba nada."""
    config = dict(CONFIG_PADRAO)
    chaves = _todas_as_chaves(caminho_ini)
    if chaves is None:
        return config
    for chave, chave_ini in LINHAS_DOSVOX_INI:
        bruto = (chaves.get(chave_ini) or "").strip()
        if not bruto:
            continue
        if chave == "difones":
            config[chave] = bruto
        elif chave in CHAVES_LIGA_DESLIGA:
            config[chave] = _le_sim_nao(bruto, CONFIG_PADRAO[chave])
        else:
            valor = _val_int_dosvox(bruto, CONFIG_PADRAO[chave])
            if chave == "interpal": valor = max(0, min(INTERPAL_MAX, valor))
            elif chave == "cortefon": valor = max(0, min(CORTEFON_MAX, valor))
            elif chave == "sobrafon": valor = max(0, min(SOBRAFON_MAX, valor))
            else: valor = max(0, valor)
            config[chave] = valor
    return config


def escrever_dosvox_ini(caminho_ini, config):
    campos = dict(CONFIG_PADRAO)
    campos.update(config or {})
    linhas = ["[SINTETIZADOR]"]
    for chave, chave_ini in LINHAS_DOSVOX_INI:
        valor = campos[chave]
        if chave in CHAVES_LIGA_DESLIGA:
            valor = _sim_nao(valor)
        elif chave == "difones":
            valor = str(valor).upper()
        linhas.append("%s=%s" % (chave_ini, valor))
    # CRLF, sem BOM: e' um arquivo do Windows, e o Dosvox sempre o escreveu assim.
    texto = "\r\n".join(linhas) + "\r\n"

    # Grava num temporario e so entao troca, para que uma queda no meio da
    # escrita nunca deixe o usuario sem dosvox.ini.
    temporario = caminho_ini + ".novo"
    pasta = os.path.dirname(caminho_ini)
    if pasta and not os.path.isdir(pasta):
        os.makedirs(pasta, exist_ok=True)
    with open(temporario, "w", encoding="latin-1", newline="") as arquivo:
        arquivo.write(texto)
    os.replace(temporario, caminho_ini)


def garantir_dosvox_ini(caminho_ini):
    """Cria o dosvox.ini se ele faltar, e o reescreve no formato atual se o que
    estiver la nao for este formato -- inclusive um arquivo dos tempos dos cinco
    niveis, que e' simplesmente descartado, ja que nao ha mais niveis nem
    CORTEFON nem SOBRAFON para migrar. Devolve True se escreveu."""
    chaves = _todas_as_chaves(caminho_ini)
    if chaves is None:
        escrever_dosvox_ini(caminho_ini, CONFIG_PADRAO)
        return True
    esperadas = {chave_ini for _, chave_ini in LINHAS_DOSVOX_INI}
    if not esperadas.issubset(chaves):
        escrever_dosvox_ini(caminho_ini, ler_dosvox_ini(caminho_ini))
        return True
    return False


def split_hundreds(value):
    if value == 0:
        return ""
    if value == 100:
        return "cem"
    parts = []
    hundreds = (value // 100) * 100
    remainder = value % 100
    if hundreds:
        parts.append("cento" if hundreds == 100 else HUNDREDS[hundreds])
    if remainder:
        if parts:
            parts.append("e")
        if remainder < 10:
            parts.append(UNITS[remainder])
        elif remainder < 20:
            parts.append(TEENS[remainder])
        else:
            tens = (remainder // 10) * 10
            unit = remainder % 10
            parts.append(TENS[tens])
            if unit:
                parts.append("e")
                parts.append(UNITS[unit])
    return " ".join(parts)


def number_to_words(value):
    if value == 0:
        return "zero"
    if value < 0:
        return "menos " + number_to_words(-value)
    # numeroParaString (dvlenum.pas) recebe um longint de 32 bits, entao o
    # Pascal original nunca conseguia representar nada na casa dos
    # trilhoes de verdade (o parametro estoura antes disso). Esta tabela,
    # do trilhao para cima, e a extensao natural do mesmo padrao de 3 em 3
    # digitos que o original usa -- nao e fidelidade ao original, que
    # nunca chegava la, e sim preenchimento de lacuna, para nao dar um
    # resultado errado em numeros grandes.
    groups = [
        (1_000_000_000_000_000_000_000_000_000_000_000, "decilhao", "decilhoes"),
        (1_000_000_000_000_000_000_000_000_000_000, "nonilhao", "nonilhoes"),
        (1_000_000_000_000_000_000_000_000_000, "octilhao", "octilhoes"),
        (1_000_000_000_000_000_000_000_000, "septilhao", "septilhoes"),
        (1_000_000_000_000_000_000_000, "sextilhao", "sextilhoes"),
        (1_000_000_000_000_000_000, "quintilhao", "quintilhoes"),
        (1_000_000_000_000_000, "quatrilhao", "quatrilhoes"),
        (1_000_000_000_000, "trilhao", "trilhoes"),
        (1_000_000_000, "bilhao", "bilhoes"),
        (1_000_000, "milhao", "milhoes"),
        (1_000, "mil", "mil"),
        (1, "", ""),
    ]
    # Rede de seguranca: se o numero for maior do que ate a maior escala
    # nomeada consegue representar direito (mais de 999 decilhoes, um
    # numero absurdamente grande, que nunca deveria aparecer num texto de
    # verdade), evita produzir um multiplicador sem sentido tipo "um
    # milhao trilhoes" -- cai para leitura digito a digito, sempre
    # inambigua, mesmo que mais longa de ouvir.
    maior_divisor = groups[0][0]
    if value // maior_divisor >= 1000:
        return digits_to_words(str(value))
    parts = []
    remainder = value
    for divisor, singular, plural in groups:
        amount = remainder // divisor
        remainder %= divisor
        if not amount:
            continue
        if divisor == 1:
            parts.append(split_hundreds(amount))
        elif divisor == 1_000:
            # Replica numeroParaString (dvlenum.pas): o "um" antes de
            # "mil" some, mas so quando mil e o PRIMEIRO grupo nao vazio
            # do numero inteiro. A checagem real do Pascal olha so o
            # comeco da string inteira (copy(s,1,6)='um mil'), entao se
            # um milhao/bilhao/trilhao vier antes, o "um" fica: "um
            # milhao um mil e duzentos", nao "um milhao mil e duzentos".
            if amount == 1:
                parts.append("mil" if not parts else "um mil")
            else:
                parts.append(f"{split_hundreds(amount)} mil")
        else:
            label = singular if amount == 1 else plural
            parts.append(f"um {label}" if amount == 1 else f"{number_to_words(amount)} {label}")
    result = []
    for idx, part in enumerate(parts):
        if idx > 0:
            result.append("e" if idx == len(parts) - 1 else "")
        result.append(part)
    return " ".join(chunk for chunk in result if chunk).strip()


DIGIT_WORDS = ["zero", "um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove"]


def digits_to_words(text):
    # Leitura digito a digito (fracao decimal, telefone, sequencia
    # soletrada): usa uma tabela propria, com "zero" de verdade na
    # posicao 0 -- diferente de UNITS, cuja posicao 0 e vazia de
    # proposito, para nao falar "zero" dentro de um numero cardinal como
    # "vinte" (sem "e zero" no final).
    return " ".join(DIGIT_WORDS[int(ch)] for ch in text if ch.isdigit())


def digits_with_leading_zeros(digit_text):
    # "01" deve soar "zero um", nunca so "um": zeros a esquerda nunca sao
    # ignorados. Cada zero a esquerda vira um "zero" falado
    # individualmente, e o restante (se sobrar algo) e falado como um
    # numero cardinal normal. Um "0" sozinho (sem zeros de preenchimento
    # na frente) continua sendo so "zero", sem repetir.
    stripped = digit_text.lstrip("0")
    zero_count = len(digit_text) - len(stripped)
    words = []
    if zero_count and len(digit_text) > 1:
        words.extend(["zero"] * zero_count)
    if stripped:
        words.append(number_to_words(int(stripped)))
    elif not words:
        words.append("zero")
    return " ".join(words)


def expand_numeric_token(token):
    token = token.strip()
    if re.fullmatch(r"\d+", token):
        return digits_with_leading_zeros(token)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        integer, _, fraction = token.partition(",")
        integer = integer.replace(".", "")
        if fraction:
            return f"{digits_with_leading_zeros(integer)} \x01virgula {digits_with_leading_zeros(fraction)}"
        return digits_with_leading_zeros(integer)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
        integer, _, fraction = token.partition(".")
        integer = integer.replace(",", "")
        if fraction:
            return f"{digits_with_leading_zeros(integer)} ponto {digits_to_words(fraction)}"
        return digits_with_leading_zeros(integer)
    if re.fullmatch(r"\d+[.,]\d+", token):
        match = re.search(r"[.,]", token)
        integer = token[:match.start()]
        fraction = token[match.end():]
        if match.group() == ",":
            return f"{digits_with_leading_zeros(integer)} \x01virgula {digits_with_leading_zeros(fraction)}"
        return f"{digits_with_leading_zeros(integer)} ponto {digits_to_words(fraction)}"
    for sep, word in (("/", "barra"), ("-", "hifen"), (":", "dois pontos")):
        if sep in token and re.fullmatch(r"\d+(?:%s\d+)+" % re.escape(sep), token):
            ligacao = "\x01menos" if sep == "-" else word
            return f" {ligacao} ".join(expand_numeric_token(part) for part in token.split(sep))
    return digits_to_words(token)


def _emitir_numero(expanded, output, pausas):
    for word in expanded.split():
        if word == "\x01menos":
            output.append(("numberWord", "menos"))
        elif word == "\x01virgula":
            output.append(("pause", (_espera_dosvox(pausas.virgula), ",")))
        else:
            output.append(("numberWord", word))


# Duracoes de pausa por tipo de pontuacao, em segundos. Sao os padroes de
# fabrica; o dosvox.ini os sobrescreve via aplicar_config_no_motor.
class Pausas(collections.namedtuple("Pausas", "ponto virgula doispontos")):
    """As tres pausas de pontuacao, em segundos.

    Eram tres variaveis GLOBAIS do modulo, escritas com "global" pelo
    aplicar_config_no_motor. Funcionava porque so existe uma voz por processo --
    mas era a unica parte do estado que nao pertencia a um objeto, e bastaria
    uma segunda voz no mesmo processo (duas ISpVoice no mesmo cliente SAPI, ou
    um script gerando dois livros com configuracoes diferentes) para a segunda
    sobrescrever as pausas da primeira. Nao daria erro: a primeira voz
    simplesmente passaria a pausar errado, em silencio.
    """
    __slots__ = ()

    @classmethod
    def de_ms(cls, ponto_ms, virgula_ms, doispontos_ms):
        return cls(ponto_ms / 1000.0, virgula_ms / 1000.0, doispontos_ms / 1000.0)


PAUSAS_PADRAO = Pausas(0.150, 0.050, 0.100)
# QUANTIZACAO DE 50 ms. As pausas de pontuacao, no Pascal, sao produzidas por
# espera(), dentro de trataPontuacao (dvwin.pas):
#     for i := 1 to n div 50 do
#         if not keypressed then delay (50);
# Ou seja, o valor do dosvox.ini e' DIVIDIDO POR 50 e truncado: PAUSAPONTO=170
# nao da 170 ms, da 150. Sem isso, todas as pausas saiam um pouco mais longas
# que no Dosvox.
PASSO_ESPERA_MS = 50


def _espera_dosvox(segundos):
    passos = int(segundos * 1000) // PASSO_ESPERA_MS
    return passos * PASSO_ESPERA_MS / 1000.0


def _pause_duration_for_token(token, next_char, pausas=PAUSAS_PADRAO):
    # Porte literal de trataPontuacao (dvwin.pas). O case tem TRES ramos, e
    # so tres:
    #
    #     '.':                 se seguido de espaco -> espera (pausaPonto)
    #                          senao -> fala o proprio caractere (sem pausa)
    #     ',', '-':            se seguido de espaco -> espera (pausaVirg)
    #                          senao -> fala o proprio caractere (sem pausa)
    #     ';', ':', '(', ')':  sempre -> espera (pausaDoisPontos)
    #
    # Nao ha caso nenhum para "!", "?", "[", "]", "{", "}": eles nao pausam.
    # A versao anterior inventava 0,08 s para esses e 0,035 s para o ponto e a
    # virgula colados na palavra seguinte. Nada disso existe no Dosvox: quando
    # nao ha pausa, o caractere e' FALADO, e quem decide se ele e falado, aqui,
    # e' o nivel de simbolos do proprio NVDA.
    if token == ".":
        return _espera_dosvox(pausas.ponto) if next_char in (" ", '"', "'", ")", "]", "}") else 0.0
    if token in (",", "-"):
        # O hifen entra no MESMO ramo da virgula, e nao num ramo proprio.
        return _espera_dosvox(pausas.virgula) if next_char in (" ", '"', "'", ")", "]", "}") else 0.0
    if token in (";", ":", "(", ")"):
        return _espera_dosvox(pausas.doispontos)
    return 0.0


def eh_simbolo_do_clek(character):
    """Verdadeiro para os caracteres que caem no ramo "else" do laco de
    sintetiza (dvwin.pas) -- o unico ramo que mexe no contador do clique.

    O laco desvia antes para tres outros ramos: os zeros a esquerda, os numeros
    (comecados por 1 a 9) e o conjunto "alfa", que e' [' ', 'A'..'Z', 'a'..'z',
    #128..#255], ou seja, espaco e letras, acentuadas inclusive. Tudo o que
    sobra -- pontuacao e simbolos em geral -- cai no else."""
    return bool(character) and not character.isalnum() and not character.isspace()


def _eh_hora_de_relogio(token):
    """Replica TextNorm.kt: hora so e tratada como relogio se couber em hh:mm."""
    if not re.fullmatch(r"\d{1,2}:\d{2}", token):
        return False
    hour_text, minute_text = token.split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    return 0 <= hour <= 23 and 0 <= minute <= 59


def preprocess_text(text, symbol_level=300, pausas=PAUSAS_PADRAO, falar_tudo=True):
    text = normalize_text(text)
    text = re.sub(r"[ \t\n\v\f\r]+", " ", text)
    # Kotlin/Pascal: qualquer hifen entre duas letras vira separador de palavras.
    text = re.sub(r"(?<=[A-Za-zÀ-ÖØ-öø-ÿ])-(?=[A-Za-zÀ-ÖØ-öø-ÿ])", " ", text)
    matches = list(re.finditer(
        r"[Ff]\d{1,2}|-?\d+(?:[.,:/-]\d+)*%?|[A-Za-zÀ-ÖØ-öø-ÿ]+|[^\s]",
        text, re.UNICODE,
    ))
    output = []
    for match in matches:
        token = match.group(0)
        next_char = text[match.end():match.end() + 1] or " "

        # Hifen separado por espacos antes de digito e sinal de menos.
        if token == "-":
            i = match.end()
            while i < len(text) and text[i] == " ":
                i += 1
            if i < len(text) and text[i].isdigit():
                output.append(("numberWord", "menos"))
                continue

        tem_menos = False
        if len(token) > 1 and token[0] == "-" and re.fullmatch(r"-\d[\d.,:/-]*%?", token):
            tem_menos = True
            token = token[1:]
        if re.fullmatch(r"[Ff]\d{1,2}", token):
            output.append(("character", "F"))
            output.extend(("character", digit) for digit in token[1:])
            continue
        if tem_menos:
            output.append(("numberWord", "menos"))

        if WORD_RE.fullmatch(token):
            lowered = token.lower()
            if len(lowered) > 1 and len(set(lowered)) == 1:
                output.extend(("character", ch) for ch in token)
                continue
            output.append(("word", token))
        elif re.fullmatch(r"\d{4}[./-]\d{1,2}[./-]\d{1,2}", token):
            year_text, month_text, day_text = re.split(r"[./-]", token)
            day, month, year = int(day_text), int(month_text), int(year_text)
            if 1 <= day <= 31 and month in MONTH_NAMES:
                output.extend(("numberWord", w) for w in number_to_words(day).split())
                output.extend((("numberWord", "de"), ("numberWord", MONTH_NAMES[month]), ("numberWord", "de")))
                output.extend(("numberWord", w) for w in number_to_words(year).split())
            else:
                _emitir_numero(expand_numeric_token(token), output, pausas)
        elif re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", token):
            day_text, month_text, year_text = re.split(r"[./-]", token)
            day, month = int(day_text), int(month_text)
            if 1 <= day <= 31 and month in MONTH_NAMES:
                output.extend(("numberWord", w) for w in number_to_words(day).split())
                output.extend((("numberWord", "de"), ("numberWord", MONTH_NAMES[month]), ("numberWord", "de")))
                output.extend(("numberWord", w) for w in number_to_words(int(year_text)).split())
            else:
                _emitir_numero(expand_numeric_token(token), output, pausas)
        elif re.fullmatch(r"\d{1,2}[./-]\d{1,2}", token) and (token[0] == "0" or re.search(r"[./-]0\d", token)):
            day_text, month_text = re.split(r"[./-]", token)
            day, month = int(day_text), int(month_text)
            if 1 <= day <= 31 and month in MONTH_NAMES:
                output.extend(("numberWord", w) for w in number_to_words(day).split())
                output.extend((("numberWord", "de"), ("numberWord", MONTH_NAMES[month])))
            else:
                _emitir_numero(expand_numeric_token(token), output, pausas)
        elif _eh_hora_de_relogio(token):
            hour_text, minute_text = token.split(":", 1)
            hour, minute = int(hour_text), int(minute_text)
            hour_words = number_to_words(hour).split()
            if hour_words[-1] == "um": hour_words[-1] = "uma"
            elif hour_words[-1] == "dois": hour_words[-1] = "duas"
            output.extend(("numberWord", w) for w in hour_words)
            if falar_tudo or minute == 0:
                output.append(("numberWord", "horas" if hour > 1 else "hora"))
            if minute != 0:
                output.extend(("numberWord", w) for w in number_to_words(minute).split())
                if falar_tudo:
                    output.append(("numberWord", "minutos" if minute > 1 else "minuto"))
        elif re.fullmatch(r"\d[\d.,:/-]*%?", token):
            if token.endswith("%"):
                _emitir_numero(expand_numeric_token(token[:-1]), output, pausas)
                output.append(("symbol", "%"))
            else:
                _emitir_numero(expand_numeric_token(token), output, pausas)
        elif len(token) == 1 and token in PAUSE_CHARS:
            duracao = _pause_duration_for_token(token, next_char, pausas)
            if token in (".", ",") and duracao <= 0:
                output.append(("symbol", token))
            elif token in PONTUACAO_COM_PAUSA_PROPRIA:
                output.append(("pause", (duracao, token)))
            elif symbol_level >= SYMBOL_SPEAK_LEVELS.get(token, 300):
                output.append(("symbol", token))
            else:
                output.append(("pause", (_pause_duration_for_token(token, next_char, pausas), token)))
        else:
            mapped = SYMBOL_WORDS.get(token)
            if mapped is not None and symbol_level >= SYMBOL_SPEAK_LEVELS.get(token, 300):
                output.append(("symbol", token))
            else:
                output.append(("pause", (_pause_duration_for_token(token, next_char, pausas), token)))
    return output


class DifonesEngine:
    def __init__(self, ind_path, dif_path):
        self.ind_path = ind_path
        self.dif_path = dif_path
        # CORTEFON e SOBRAFON de dvinter.pas (paramFala): quantidade de
        # amostras cortadas do fim de um difone quando a silaba nao e a
        # tonica da palavra, e o piso minimo de amostras que devem sobrar.
        # Valores padrao aqui replicam CORTEFON4/SOBRAFON4 do dosvox.ini
        # fornecido (nivel de velocidade 4, o configurado como ativo).
        # Quanto se corta do fim de um difone atono, e o piso de amostras que
        # deve sobrar. Zero desliga o corte -- e' o que a casca poe quando o
        # dosvox.ini traz CORTEFON=0. A casca sobrescreve com o valor do arquivo
        # (300/300 de fabrica) via definir_cortefon/definir_sobrafon.
        self.cortefon = 0
        self.sobrafon = 0
        self.units = {}
        self._dif_data = b""
        self._unit_cache = {}
        self._clipped_unit_cache = {}
        self._load_index()

    def _load_index(self):
        with open(self.ind_path, "rb") as file_obj:
            data = file_obj.read()
        with open(self.dif_path, "rb") as file_obj:
            self._dif_data = file_obj.read()
        for i in range(0, len(data), 15):
            entry = data[i : i + 15]
            if len(entry) < 15:
                break
            name_len = entry[0]
            name = entry[1 : 1 + name_len].decode("ascii", errors="ignore").upper()
            length = struct.unpack("<H", entry[9:11])[0]
            offset = struct.unpack("<I", entry[11:15])[0]
            self.units[name] = (offset, length)

    def get_unit_audio(self, name, perc=1.0, forte=True):
        name = name.upper()
        if name not in self.units:
            return None
        offset, length = self.units[name]
        data = self._unit_cache.get(name)
        if data is None:
            data = self._dif_data[offset : offset + length]
            self._unit_cache[name] = data
        # CORTEFON/SOBRAFON de falaDifone (dvinter.pas), restaurado. Numa silaba
        # ATONA (forte=False) cujo NOME de difone tem mais de dois caracteres,
        # tira-se CORTEFON amostras do FIM da gravacao, respeitando o piso
        # SOBRAFON -- e se o proprio difone ja for menor que o piso, ele fica
        # inteiro. O difone de vogal pura (nome de dois caracteres, "$A", "$O")
        # NUNCA e' cortado: cortar ~130 ms de vogal a destruiria, e por isso o
        # "a" sozinho soa igual com ou sem corte; quem o encurta e' o cortafala.
        #
        # A ordem e' a do Pascal: corta-se a cauda ANTES de aplicar o perc
        #   tamArq := tamDifo - quantocorta;   ... piso ...
        #   tamArq := trunc (tamArq * perc);
        # O perc (0,6 na elisao de vogal, 0,7 antes do "s", 0,9 no difone
        # acentuado) vem das regras de concatenacao e multiplica o que sobrou.
        bruto = len(data)
        tam = bruto
        if (not forte) and self.cortefon > 0 and len(name) > 2:
            tam = bruto - self.cortefon
            if tam < self.sobrafon:
                tam = bruto if bruto < self.sobrafon else self.sobrafon
        tam = max(0, int(Decimal(tam) * Decimal(max(0.0, perc))))
        cache_key = (name, tam)
        cached = self._clipped_unit_cache.get(cache_key)
        if cached is not None:
            return cached
        clipped = data[:tam]
        if len(self._clipped_unit_cache) > 512:
            self._clipped_unit_cache.clear()
        self._clipped_unit_cache[cache_key] = clipped
        return clipped

    def synthesize(self, unit_names, cortafala=False, rapidinho=False):
        # O CORTAFALA E' APLICADO POR BUFFER, NAO NA FALA INTEIRA.
        #
        # O ponto critico de compatibilidade e que FIM DE PALAVRA NAO fecha o
        # buffer. No Pascal/Kotlin, falaFonemas acumula a corrida de fala e
        # descarrega em pausas, clek, PCM direto ou no fim da elocucao. Fechar
        # por palavra desloca as fronteiras de 8192 amostras do waveCompact e
        # muda audivelmente o resultado do Cortafala.
        #
        # Marcadores:
        #   __SIL__   silencio DENTRO do buffer (INTERPAL).
        #   __PAUSA__ pausa de pontuacao, FORA do buffer. Nunca e compactada.
        #   __CLEK__  estalo fora do Cortafala.
        #   __PCM__   som gravado (letra, numero, mes): buffer proprio.
        #   __FLUSH__ descarga explicita; nao e emitida por fim de palavra.
        saida = bytearray()
        buffer_atual = bytearray()

        def descarrega():
            if not buffer_atual:
                return
            dados = bytes(buffer_atual)
            if cortafala:
                dados = apply_cortafala_to_pcm(dados, rapidinho=rapidinho)
            saida.extend(dados)
            del buffer_atual[:]

        for item in unit_names:
            # Difone: (nome, perc, forte). Marcadores (__FLUSH__, __PCM__, ...):
            # (nome, valor) -- o forte nem se aplica a eles, sao tratados antes
            # de chegar em get_unit_audio.
            if isinstance(item, tuple):
                if len(item) == 3:
                    name, perc, forte = item
                else:
                    name, perc = item
                    forte = True
            else:
                name, perc, forte = item, 1.0, True

            if name == "__FLUSH__":
                descarrega()
                continue
            if name == "__CLEK__":
                descarrega()
                saida.extend(perc)
                continue
            if name == "__PAUSA__":
                descarrega()
                tamanho = _silencio_amostras(perc)
                if tamanho > 0:
                    saida.extend(b"\x80" * tamanho)
                continue
            if name == "__PCM__":
                descarrega()
                buffer_atual.extend(perc)
                descarrega()
                continue
            if name == "__SIL__":
                # perc aqui e' o numero de amostras (ja quantizado em multiplos
                # de 100 por quem inseriu), o INTERPAL entre palavras. Entra no
                # buffer, ANTES do cortafala, como o silencio() do pvetSom.
                tamanho = int(perc)
                if tamanho > 0:
                    buffer_atual.extend(b"\x80" * tamanho)
                continue
            data = self.get_unit_audio(name, perc, forte)
            if data:
                buffer_atual.extend(data)

        descarrega()
        return bytes(saida)

    def synthesize_streaming(self, unit_names, cortafala=False, rapidinho=False):
        """Produz os mesmos segmentos de synthesize, liberando cada buffer assim que fecha."""
        buffer_atual = bytearray()

        def descarrega():
            if not buffer_atual:
                return None
            dados = bytes(buffer_atual)
            del buffer_atual[:]
            return apply_cortafala_to_pcm(dados, rapidinho=rapidinho) if cortafala else dados

        for item in unit_names:
            if isinstance(item, tuple):
                if len(item) == 3:
                    name, perc, forte = item
                else:
                    name, perc = item; forte = True
            else:
                name, perc, forte = item, 1.0, True
            if name == "__FLUSH__":
                dados = descarrega()
                if dados: yield dados
                continue
            if name == "__CLEK__":
                dados = descarrega()
                if dados: yield dados
                if perc: yield bytes(perc)
                continue
            if name == "__PAUSA__":
                dados = descarrega()
                if dados: yield dados
                tamanho = _silencio_amostras(perc)
                if tamanho: yield b"\x80" * tamanho
                continue
            if name == "__PCM__":
                # Igual ao Kotlin: o PCM direto e um buffer proprio, mas passa
                # pelo MESMO descarrega() dos difones. Assim, com Cortafala
                # ligado, Letras/LetrasRapidas tambem recebem waveCompact no
                # caminho streaming. A versao anterior emitia perc cru aqui,
                # fazendo synthesize_streaming divergir de synthesize.
                dados = descarrega()
                if dados:
                    yield dados
                if perc:
                    buffer_atual.extend(perc)
                    dados = descarrega()
                    if dados:
                        yield dados
                continue
            if name == "__SIL__":
                tamanho = int(perc)
                if tamanho: buffer_atual.extend(b"\x80" * tamanho)
                continue
            data = self.get_unit_audio(name, perc, forte)
            if data: buffer_atual.extend(data)
        dados = descarrega()
        if dados: yield dados


class _SafeWordArray:
    # Traduz indices "estilo Pascal" (podem chegar a -2, replicando
    # palavra: array[-2..256] of char em dvtradut.pas) para uma lista
    # Python comum, deslocando pela margem. Qualquer indice fora da faixa
    # esperada devolve espaco em branco, nunca o fim da lista por engano
    # (que e' o que aconteceria com um indice negativo cru em Python).
    def __init__(self, margem, data):
        self._margem = margem
        self._data = data

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [self[k] for k in range(*i.indices(len(self._data) - self._margem))]
        j = i + self._margem
        if 0 <= j < len(self._data):
            return self._data[j]
        return " "

    def __setitem__(self, i, value):
        j = i + self._margem
        if 0 <= j < len(self._data):
            self._data[j] = value


class RegrasParser:
    def __init__(self, rgr_path, exc_path=None):
        self.rules_by_first = collections.defaultdict(list)
        self.exceptions = {}
        self.vog_maiuscula = set("AEIOU")
        self.vog_minuscula = set("aeiou")
        self.vogal = self.vog_maiuscula | self.vog_minuscula
        self.consoante = set("bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")
        self.vogal_cons = self.vogal | self.consoante
        self.acentos = set("'`^~\"")
        self.qg = set("qg")
        self.ao = set("AaOo")
        self.ei = set("EeIi")
        if exc_path:
            self._load_exceptions(exc_path)
        self._load_rules(rgr_path)

    def _load_exceptions(self, path):
        with open(path, "r", encoding="latin-1") as file_obj:
            for line in file_obj:
                raw = line.rstrip("\r\n")
                if not raw:
                    continue
                texto = raw + "|=|"
                i_igual = texto.find("=")
                key = texto[:i_igual]
                resto = texto[i_igual + 1:]
                i_barra = resto.find("|")
                value = resto[:i_barra] if i_barra >= 0 else resto
                self.exceptions[key.lower()] = value

    def _load_rules(self, path):
        with open(path, "r", encoding="latin-1") as file_obj:
            lines = file_obj.readlines()
        for raw in lines:
            # NAO use strip() aqui. O "|" no fim de cada regra existe
            # EXATAMENTE para proteger os espacos finais da traducao, e esses
            # espacos sao a QUEBRA DE SILABA. inicTradutor (dvtradut.pas) le
            # caractere a caractere depois do "=" ate encontrar o "|", sem
            # aparar coisa nenhuma:
            #
            #     for pos := pos+1 to length (linha) do
            #        if linha[pos] = '|' then goto 4
            #        else fonemas := fonemas + linha[pos];
            #
            # A regra padrao do L, por exemplo, e "(L)=w/ |": o L que nao vem
            # antes de vogal vira "w" MAIS UMA QUEBRA DE SILABA. Com o strip(),
            # a quebra sumia, e palavras como "falso", "bolsa", "valsa", "else"
            # e "false" viravam uma silaba unica gigante ("fAwsw"), que nao
            # existe no banco de difones. O "|" tambem aparece como operador de
            # contexto a esquerda (testa_antecessor_l), por isso o corte e' no
            # ULTIMO "|" da linha, nunca no primeiro.
            raw = raw.rstrip("\r\n")
            if not raw.strip() or raw.lstrip().startswith(";"):
                continue
            if "|" in raw:
                raw = raw[: raw.rfind("|")]
            match = re.match(r"^(.*?)\((.*?)\)(.*?)=(.*)$", raw)
            if not match:
                continue
            prefix, target, suffix, result = match.groups()
            rule = {
                "prefix": prefix[:5],
                "target": target[:5],
                "suffix": suffix[:5],
                "result": result[:11],
            }
            # Replica inicTradutor/traduz (dvtradut.pas): as regras formam
            # uma lista ligada por ordem de leitura do arquivo, e a
            # primeira da lista cujo contexto bate e' a usada -- nunca ha'
            # ordenacao por especificidade ou tamanho. A chave da lista e'
            # sempre o PRIMEIRO caractere do contexto (o "target"), que no
            # arquivo real e' sempre maiusculo.
            first_char = target[0].lower() if target else ""
            self.rules_by_first[first_char].append(rule)

    def separa_acentos(self, text):
        # Replica tabTrad (dvtradut.pas) o mais fielmente possivel. Alguns
        # mapeamentos podem parecer estranhos (a-trema vira "a~", igual a
        # a-til, em vez de um trema de verdade) mas e' exatamente o que a
        # tabela original faz -- nao e' um erro meu, e' fidelidade.
        mapping = {
            "À": "a`", "Á": "a'", "Â": "a^", "Ã": "a~", "Ä": "a~",
            "Å": "aa", "Æ": "ae", "Ç": "ss", "È": "e`", "É": "e'",
            "Ê": "e^", "Ë": 'e"', "Ì": "i`", "Í": "i'", "Î": "i^",
            "Ï": 'i"', "Ð": "", "Ñ": "nh", "Ò": "o`", "Ó": "o'",
            "Ô": "o^", "Õ": "o~", "Ö": "o`", "Ø": "oe", "Ù": "u`",
            "Ú": "u'", "Û": "u^", "Ü": "u", "Ý": "y", "Þ": "th",
            "ß": "ss", "à": "a`", "á": "a'", "â": "a^", "ã": "a~",
            "ä": "a~", "å": "aa", "æ": "ae", "ç": "ss", "è": "e`",
            "é": "e'", "ê": "e^", "ë": 'e"', "ì": "i`", "í": "i'",
            "î": "i^", "ï": 'i"', "ð": "", "ñ": "nh", "ò": "o`",
            "ó": "o'", "ô": "o^", "õ": "o~", "ö": "o`", "ø": "oe",
            "ù": "u`", "ú": "u'", "û": "u^", "ü": "u", "ý": "y",
            "þ": "th", "ÿ": "y",
        }
        chars = list(text)
        out = []
        for i, ch in enumerate(chars):
            prev_char = chars[i - 1] if i > 0 else " "
            next_char = chars[i + 1] if i + 1 < len(chars) else " "
            if ch.upper() == "W":
                if prev_char in self.vogal_cons or next_char in self.vogal_cons:
                    ch = "u"
            elif ch.upper() == "Y":
                if prev_char in self.vogal_cons or next_char in self.vogal_cons:
                    ch = "i"
                # No Pascal real (separaAcentos, dvtradut.pas), o "y"
                # isolado como palavra inteira tenta virar "i", mas essa
                # troca e' feita numa variavel que o trecho de codigo
                # seguinte sempre sobrescreve antes de usar -- entao, na
                # pratica, um "y" isolado nunca chega a virar "i" no
                # sistema original. Replicamos essa particularidade aqui
                # (nao convertendo) para soar identico, mesmo sendo uma
                # imperfeicao do original.
            out.append(mapping.get(ch, ch))
        return "".join(out)

    def _build_word_array(self, word):
        # O Pascal real declara palavra: array[-2..256] of char, porque
        # alguns testes de contexto podem recuar ate 2 posicoes alem do
        # inicio da palavra. Em Python, indice negativo tem outro
        # significado (conta a partir do fim da lista), o que seria
        # perigoso aqui -- por isso a margem de seguranca no inicio, para
        # qualquer indice ficar sempre dentro de uma posicao valida e
        # sempre ler um espaco em branco (inofensivo), nunca o fim do
        # vetor por engano.
        margem = 4
        arr = _SafeWordArray(margem, [" "] * (len(word) + margem + 4))
        for i, ch in enumerate(word, start=1):
            arr[i] = ch
        return arr

    def marca_tonica(self, word, tem_acento_in=None, num_vogais_in=None):
        # Replica le_palavra (dvtradut.pas): tem_acento so conta agudo,
        # grave, circunflexo e til -- o trema (") e' explicitamente
        # excluido dessa checagem no original (c <> '"').
        acentos_que_contam = self.acentos - {'"'}
        tem_acento = tem_acento_in if tem_acento_in is not None else any(c in acentos_que_contam for c in word)
        pos_letra = len(word)
        num_vogais = num_vogais_in if num_vogais_in is not None else sum(1 for c in word if c in self.vogal)
        if tem_acento or not ((num_vogais > 1) or ((num_vogais == 1) and pos_letra > 0 and word[-1] == "l")):
            return word
        palavra = self._build_word_array(word)
        estado = 0
        marcou = False
        letra_corrente = pos_letra
        while not marcou and letra_corrente > 0:
            ch = palavra[letra_corrente]
            if estado == 0:
                if ch in "nrxlz":
                    estado = 1
                elif ch == "m":
                    estado = 2
                elif ch in "iu":
                    estado = 3
                elif ch == "s":
                    estado = 4
                elif ch in "aeo":
                    estado = 5
            elif estado == 1 and ch in self.vogal:
                estado = 6
            elif estado == 2:
                if ch in "iu":
                    estado = 3
                elif ch in "ae":
                    estado = 5
                elif ch == "o":
                    estado = 6
            elif estado == 3:
                if (ch in self.consoante) or ((palavra[letra_corrente - 1] == "u") and (palavra[letra_corrente - 2] in self.qg)):
                    estado = 7
                else:
                    estado = 6
            elif estado == 4:
                if ch in "aeo":
                    estado = 5
                elif ch in "iu":
                    estado = 3
            elif estado == 5:
                if ch in "aeo":
                    estado = 6
                elif ch in "iu":
                    estado = 8
            elif estado == 6:
                palavra[letra_corrente + 1] = palavra[letra_corrente + 1].upper()
                marcou = True
            elif estado == 7:
                palavra[letra_corrente + 2] = palavra[letra_corrente + 2].upper()
                marcou = True
            elif estado == 8:
                prox2 = palavra[letra_corrente + 2]
                prox3 = palavra[letra_corrente + 3]
                cond = (
                    (ch in self.consoante)
                    or ((ch == "u") and (palavra[letra_corrente - 1] in self.qg))
                    or (
                        prox2 in "lmnrz"
                        and (
                            ((prox2 == "n") and (prox3 == "h"))
                            or ((prox2 == "r") and (prox3 == "r"))
                            or ((prox3 in self.consoante) and (prox3 != "h"))
                        )
                    )
                )
                estado = 7 if cond else 6
            letra_corrente -= 1
        return "".join(palavra[1 : pos_letra + 1])

    def trata_excessoes(self, word):
        if word in self.exceptions:
            return self.exceptions[word]
        removed = ""
        base = word
        while base and base[-1] in "sm":
            removed = base[-1] + removed
            base = base[:-1]
            if base in self.exceptions:
                return self.exceptions[base] + removed
        return word

    def _testa_lim_palavra(self, idx, pos_letra):
        return idx in (0, pos_letra + 1), idx

    def _testa_a_ou_o(self, palavra, idx, pos_letra):
        if idx in (0, pos_letra + 1):
            return False, idx
        if palavra[idx] in self.ao:
            return True, idx - 1
        if palavra[idx] in self.acentos and idx > 0 and palavra[idx - 1] in self.ao:
            return True, idx - 2
        return False, idx

    def _testa_fim_silaba(self, palavra, idx, pos_letra):
        if idx != pos_letra + 1 and ((palavra[idx] not in self.consoante) or palavra[idx] == "h"):
            return False, idx
        return True, idx

    def _testa_consoante_muda(self, palavra, idx, pos_letra):
        if idx in (0, pos_letra + 1):
            return False, idx
        if (palavra[idx] not in self.consoante) or palavra[idx] in "rlRL":
            return False, idx
        return True, idx + 1

    def _testa_e_ou_i(self, palavra, idx, pos_letra):
        if idx in (0, pos_letra + 1):
            return False, idx
        if palavra[idx] not in self.ei:
            return False, idx
        if palavra[idx + 1] in self.acentos:
            return True, idx + 2
        return True, idx + 1

    def _testa_vogal(self, palavra, idx, pos_letra, incremento):
        if idx in (0, pos_letra + 1):
            return False, idx
        if (palavra[idx] not in self.vogal) and (palavra[idx] not in self.acentos):
            return False, idx
        while idx not in (0, pos_letra + 1) and (palavra[idx] in self.vogal or palavra[idx] in self.acentos):
            idx += incremento
        return True, idx

    def _testa_s(self, palavra, idx, pos_letra):
        if idx <= pos_letra and palavra[idx] == "s":
            return True, idx + 1
        return True, idx

    def _testa_lnmrz(self, palavra, idx, pos_letra):
        if idx >= pos_letra + 1:
            return False, idx
        if palavra[idx] not in "lnmrzLNMRZ":
            return False, idx
        return True, idx + 1

    def _testa_vogal_ou_inic_palavra(self, palavra, idx):
        if idx == 0:
            return True, idx
        if palavra[idx] in self.vogal:
            return True, idx - 1
        if palavra[idx] in self.acentos and idx > 0 and palavra[idx - 1] in self.vogal:
            return True, idx - 2
        return False, idx

    def _testa_antecessor_l(self, palavra, idx):
        if idx != 0 and palavra[idx] in "nrsNRS":
            return True, idx - 1
        return False, idx

    def _contexto_satisfaz(self, palavra, pos_i, pos_letra, rule):
        target = rule["target"]
        for j, ch in enumerate(target):
            if (pos_i + j) > pos_letra or ch != palavra[pos_i + j].upper():
                return False
        return True

    def _contexto_a_direita_satisfaz(self, palavra, pos_i, pos_letra, rule):
        idx = pos_i + len(rule["target"])
        for ch in rule["suffix"]:
            if ch == "[":
                ok, idx = self._testa_fim_silaba(palavra, idx, pos_letra)
            elif ch == "*":
                ok, idx = self._testa_consoante_muda(palavra, idx, pos_letra)
            elif ch == "+":
                ok, idx = self._testa_e_ou_i(palavra, idx, pos_letra)
            elif ch == "%":
                ok, idx = self._testa_lim_palavra(idx, pos_letra)
            elif ch == "#":
                ok, idx = self._testa_vogal(palavra, idx, pos_letra, 1)
            elif ch == "\\":
                ok, idx = self._testa_s(palavra, idx, pos_letra)
            elif ch == "&":
                ok, idx = self._testa_lnmrz(palavra, idx, pos_letra)
            else:
                ok = idx < pos_letra + 1 and ch == palavra[idx].upper()
                if ok:
                    idx += 1
            if not ok:
                return False
        return True

    def _contexto_a_esquerda_satisfaz(self, palavra, pos_i, pos_letra, rule):
        idx = pos_i - 1
        for ch in reversed(rule["prefix"]):
            if ch == "%":
                ok, idx = self._testa_lim_palavra(idx, pos_letra)
            elif ch == "#":
                ok, idx = self._testa_vogal(palavra, idx, pos_letra, -1)
            elif ch == "]":
                ok, idx = self._testa_a_ou_o(palavra, idx, pos_letra)
            elif ch == "_":
                ok, idx = self._testa_vogal_ou_inic_palavra(palavra, idx)
            elif ch == "|":
                ok, idx = self._testa_antecessor_l(palavra, idx)
            else:
                ok = idx != 0 and ch == palavra[idx].upper()
                if ok:
                    idx -= 1
            if not ok:
                return False
        return True

    def tem_vogal(self, word):
        # Equivalente a soConsoantes (dvtradut.pas), simplificado: nesta
        # arquitetura, pontuacao e delimitadores nunca chegam misturados
        # dentro de um token de palavra (isso ja foi separado antes, em
        # preprocess_text), entao a checagem se reduz a "existe alguma
        # vogal nas letras desta palavra".
        return any(c in self.vogal for c in word)

    def preparar_palavra_completa(self, word):
        w = self.separa_acentos(normalize_text(word)).lower()
        acentos_que_contam = self.acentos - {'"'}
        tem_acento = any(c in acentos_que_contam for c in w)
        num_vogais = sum(1 for c in w if c in self.vogal)
        return self.trata_excessoes(w), tem_acento, num_vogais

    def preparar_palavra(self, word):
        return self.preparar_palavra_completa(word)[0]

    def phonetize_word(self, word, preparada=None):
        prep = preparada if preparada is not None else self.preparar_palavra_completa(word)
        if isinstance(prep, tuple):
            word, tem_acento, num_vogais = prep
        else:
            # Compatibilidade para chamadas externas antigas.
            word = prep
            tem_acento = num_vogais = None
        word = self.marca_tonica(word, tem_acento, num_vogais)
        palavra = self._build_word_array(word)
        pos_letra = len(word)
        pos_i = 1
        fonemas = ["["]
        while pos_i <= pos_letra:
            ind_regra = palavra[pos_i].lower()
            seq_fonemas = f" /_{ind_regra.upper()}"
            selected_rule = None
            for rule in self.rules_by_first.get(ind_regra, []):
                if (
                    self._contexto_satisfaz(palavra, pos_i, pos_letra, rule)
                    and self._contexto_a_esquerda_satisfaz(palavra, pos_i, pos_letra, rule)
                    and self._contexto_a_direita_satisfaz(palavra, pos_i, pos_letra, rule)
                ):
                    selected_rule = rule
                    seq_fonemas = rule["result"]
                    break
            if palavra[pos_i] in self.vogal and palavra[pos_i].isupper():
                # Replica traduz (dvtradut.pas): procura a PRIMEIRA vogal
                # em seq_fonemas, de qualquer caso (maiuscula ou
                # minuscula) -- nao so minuscula. Se a regra escolhida ja
                # devolveu uma vogal maiuscula (como em "U/", da regra
                # %SA(U)DA=U), upcase nela e' um no-op inofensivo, exatamente
                # como no original.
                chars = list(seq_fonemas)
                for j, ch in enumerate(chars):
                    if ch in self.vogal:
                        chars[j] = ch.upper()
                        break
                seq_fonemas = "".join(chars)
            fonemas.append(seq_fonemas)
            pos_i += len(selected_rule["target"]) if selected_rule else 1
            if pos_i <= pos_letra:
                fonemas.append("/")
        fonemas.append("]")
        return "".join(fonemas).strip("[]")


class DosvoxNativeSynth:
    # INTERPAL: silencio ENTRE SILABAS de uma mesma palavra (falaFonemas,
    # dvinter.pas) -- nunca entre palavras. Em amostras a 11025 Hz. A casca
    # sobrescreve isto com o valor do dosvox.ini.
    INTERPAL_PADRAO = 0

    # CORTEFON/SOBRAFON: o corte de cauda do difone atono (falaDifone,
    # dvinter.pas). 300/300 e' o valor do dosvox.ini de fabrica. A casca
    # sobrescreve com o que vier do arquivo.
    CORTEFON_PADRAO = 0
    SOBRAFON_PADRAO = 0

    # Silencio extra depois de cada palavra. O Dosvox nao tem nada disso: e'
    # zero, e as palavras encostam. Fica aqui, exposto, apenas para quem
    # quiser afrouxar a leitura de proposito fora do NVDA.
    PAUSA_ENTRE_PALAVRAS_PADRAO = 0.0

    def __init__(self, module_dir, voice_id):
        data_dir = os.path.join(module_dir, VOICE_DIR_NAME)
        self._data_dir = data_dir
        self._voice_id = voice_id
        ind_path = os.path.join(data_dir, f"{voice_id}.ind")
        dif_path = os.path.join(data_dir, f"{voice_id}.dif")
        rules_path = os.path.join(data_dir, "Regras.rgr")
        exc_path = os.path.join(data_dir, "portug.exc")
        descricoes_path = os.path.join(data_dir, "descricoes.dic")
        # Letras e LetrasRapidas moram DENTRO de dosvox_data, junto com os
        # difones, as regras e o ini. Uma pasta so, para que uma casca futura
        # (SAPI 5, Android) precise apontar para um lugar so.
        self.letters_dir_normal = os.path.join(data_dir, LETTERS_DIR_NAME)
        self.letters_dir_rapido = os.path.join(data_dir, LETTERS_DIR_RAPIDO_NAME)
        self._letter_sound_map_normal = self._build_letter_sound_map(self.letters_dir_normal)
        self._letter_sound_map_rapido = self._build_letter_sound_map(self.letters_dir_rapido)
        self._ascii_sound_map_normal = self._build_ascii_sound_map(self._letter_sound_map_normal)
        self._ascii_sound_map_rapido = self._build_ascii_sound_map(self._letter_sound_map_rapido)
        self.letters_dir = self.letters_dir_normal
        self._letter_sound_map = self._letter_sound_map_normal
        self._ascii_sound_map = self._ascii_sound_map_normal
        self._wav_cache = {}
        self._phoneme_cache = {}
        self._text_pcm_cache = {}
        self._character_pcm_cache = {}
        self.engine = DifonesEngine(ind_path, dif_path)
        self.engine.cortefon = self.CORTEFON_PADRAO
        self.engine.sobrafon = self.SOBRAFON_PADRAO
        self.interpal = self.INTERPAL_PADRAO
        self.intervalo_segundos = self.INTERPAL_PADRAO / TAXA_BASE
        self.pausas = PAUSAS_PADRAO
        self.pausa_entre_palavras = self.PAUSA_ENTRE_PALAVRAS_PADRAO
        # Os TRES ajustes de voz do Dosvox moram aqui, no motor, e nao na casca.
        # Padrao de fabrica: os tres desligados.
        self.rapidinho = False
        self.cortafala = False
        self.usar_letras_rapidas = False
        # Replica o mecanismo de "cleck" em pontuacao repetida (sintetiza,
        # dvwin.pas): ultLetra/nrepUlt rastreiam a ultima pontuacao vista
        # (palavras no meio nao mexem nisso) e, depois da quarta repeticao
        # seguida da MESMA pontuacao, toca um clique curto no lugar da
        # pausa, ate aparecer uma pontuacao diferente. O buffer do clique
        # e gerado uma unica vez aqui, como o Pascal faz uma unica vez na
        # inicializacao do programa (nao um som novo a cada clique).
        self._ultimo_simbolo_repetido = None
        self._repeticoes_simbolo = 0
        self._clek_pcm = self._gerar_clek()
        self.g2p = RegrasParser(rules_path, exc_path)
        self.descricoes = DescricoesCP1252(descricoes_path)

    def definir_banco(self, voice_id):
        if voice_id == self._voice_id:
            return
        ind_path = os.path.join(self._data_dir, f"{voice_id}.ind")
        dif_path = os.path.join(self._data_dir, f"{voice_id}.dif")
        novo = DifonesEngine(ind_path, dif_path)
        novo.cortefon = self.engine.cortefon
        novo.sobrafon = self.engine.sobrafon
        self.engine = novo
        self._voice_id = voice_id
        self._text_pcm_cache.clear()
        self._character_pcm_cache.clear()

    def definir_pausas(self, pausas):
        if pausas == self.pausas:
            return
        self.pausas = pausas
        self._text_pcm_cache.clear()
        self._character_pcm_cache.clear()

    def definir_interpal(self, interpal):
        self.interpal = max(0, min(INTERPAL_MAX, int(interpal)))
        self.intervalo_segundos = self.interpal / TAXA_BASE
        self._text_pcm_cache.clear()
        self._character_pcm_cache.clear()

    def _interpal_amostras(self):
        # silencio (dvinter.pas) escreve "espaco div 100" blocos de 100
        # amostras: o total e' SEMPRE multiplo de 100, e um INTERPAL entre 1 e
        # 99 vira zero. Quem chama silencio(intervalo) e' falaFonemas, ao passar
        # de uma palavra para a proxima dentro de uma mesma corrida de fala.
        return (self.interpal // 100) * 100

    def definir_cortefon(self, cortefon):
        # Quantas amostras se tira do fim do difone atono. Mexer nisto muda o
        # comprimento das unidades ja recortadas, entao limpa tanto o cache de
        # recorte do motor de difones quanto o de PCM montado.
        self.engine.cortefon = max(0, min(CORTEFON_MAX, int(cortefon)))
        self.engine._clipped_unit_cache.clear()
        self._text_pcm_cache.clear()
        self._character_pcm_cache.clear()

    def definir_sobrafon(self, sobrafon):
        # Piso de amostras que o corte de CORTEFON deve deixar sobrar.
        self.engine.sobrafon = max(0, min(SOBRAFON_MAX, int(sobrafon)))
        self.engine._clipped_unit_cache.clear()
        self._text_pcm_cache.clear()
        self._character_pcm_cache.clear()

    def definir_cortafala(self, ativo):
        # O cortafala era o unico dos tres ajustes que NAO morava aqui: o driver
        # do NVDA guardava o valor e o passava como argumento em cada chamada.
        # Isso obrigaria toda casca futura (SAPI 5, Android, gerador de livro
        # falado) a saber que o argumento existe e a lembrar de passa-lo -- e
        # esquecer dele significaria falar sem cortafala sem ninguem notar. Agora
        # ele e' estado do motor, como o rapidinho e as letras rapidas: a casca
        # so avisa quando muda, e nunca mais precisa se lembrar disso.
        ativo = bool(ativo)
        if ativo == self.cortafala:
            return
        self.cortafala = ativo
        self._text_pcm_cache.clear()
        self._character_pcm_cache.clear()

    def definir_rapidinho(self, ativo):
        # Unico lugar que liga/desliga o rapidinho. Ele NAO mexe nas amostras:
        # muda a taxa em que elas devem ser tocadas (ver taxa_saida) e o fator
        # de janela do cortafala (ver apply_cortafala_to_pcm). Quem chama
        # precisa reabrir o tocador na taxa nova.
        ativo = bool(ativo)
        if ativo == self.rapidinho:
            return
        self.rapidinho = ativo
        self._text_pcm_cache.clear()
        self._character_pcm_cache.clear()

    @property
    def taxa_saida(self):
        """Taxa em que o PCM devolvido deve ser tocado: 11025 Hz normalmente,
        16537 Hz com o rapidinho ligado -- o mesmo trunc(veloc * 1.5) que o
        wavePlay (dvwav.pas) manda para o dispositivo de audio."""
        return TAXA_RAPIDINHO if self.rapidinho else TAXA_BASE

    def _gerar_clek(self):
        # Replica a inicializacao do buffer "clek", no fim de dvwin.pas:
        #
        #     for i := 0 to (TAMCLEK div divisorTempoBipsCleks) div 4 do
        #         clek[i] := $80 + random(60);
        #     for i := (TAMCLEK div divisorTempoBipsCleks) div 4 to ... do
        #         clek[i] := $80;
        #
        # Um quarto do buffer e' ruido curto (128 a 187), o resto e' silencio:
        # um estalo, nao um som gravado.
        #
        # E O ESTALO E' SEMPRE O MESMO, byte a byte, em toda execucao.
        #
        # O "random" do Pascal so e' imprevisivel depois de um Randomize -- e o
        # Dosvox NUNCA chama Randomize, em lugar nenhum. Sem ele, o RandSeed do
        # Delphi nasce em zero e a sequencia e' identica em todo arranque. A
        # versao anterior usava o random do Python, semeado pelo relogio, o que
        # tornava o estalo diferente a cada vez que o NVDA subia -- e, de
        # quebra, tornava impossivel comparar duas execucoes byte a byte.
        #
        # Aqui esta o gerador do Delphi, replicado (System._RandInt):
        #     RandSeed := RandSeed * $08088405 + 1;   { 32 bits, sem sinal }
        #     Result   := (Range * RandSeed) shr 32;
        TAMCLEK = 256
        buf = bytearray([0x80]) * TAMCLEK
        semente = 0
        for i in range(TAMCLEK // 4):
            semente = (semente * 0x08088405 + 1) & 0xFFFFFFFF
            buf[i] = 0x80 + ((60 * semente) >> 32)
        return bytes(buf)

    def resetar_contador_pontuacao(self):
        # No Pascal, sintetiza comeca SEMPRE com "ultLetra := ' '" e
        # "nrepUlt := 0": o contador vale por elocucao, e nunca atravessa de
        # uma fala para a proxima. Quem chama precisa fazer o mesmo -- zerar no
        # comeco de cada elocucao, e nao so quando a fala e' interrompida.
        self._ultimo_simbolo_repetido = None
        self._repeticoes_simbolo = 0

    def _zerar_repeticao(self):
        self._ultimo_simbolo_repetido = None
        self._repeticoes_simbolo = 0

    # O PONTO NUNCA CLICA, E ZERA A FILA.
    #
    # Este e' o unico desvio deliberado do Pascal no contador do clique.
    #
    # No original, o contador so e' mexido no ramo dos simbolos: palavras e
    # numeros no meio do caminho NAO zeram a contagem. Simulei o laco de
    # sintetiza linha a linha para confirmar, e o resultado e' este:
    #
    #     "a. b. c. d. e. f. g."  ->  clica no 5o, 6o e 7o PONTOS
    #
    # Ou seja, lendo prosa, a cada cinco frases o ponto final vira um estalo.
    # Nao incomodava no Dosvox por um motivo circunstancial: la, sintetiza e'
    # chamado UMA VEZ POR LINHA, e uma linha raramente tem cinco pontos. O NVDA
    # entrega paragrafos inteiros, e o defeito aparece.
    #
    # A excecao vale SO para o ponto, e nao para os outros simbolos, porque so
    # com o ponto e' normal haver muitos numa mesma leitura. Vinte virgulas ou
    # vinte iguais empilhados nao acontecem em prosa -- quando acontecem, sao
    # uma linha de separacao, e e' exatamente para isso que o clique existe.
    # Entao a virgula, o igual, o traco e o resto continuam com a regra do
    # Pascal, ao pe da letra: quatro falados, e do quinto em diante, clique.
    SIMBOLO_QUE_NUNCA_CLICA = "."

    def _notar_simbolo(self, character):
        # Porte literal de ultLetra/nrepUlt, no laco de sintetiza (dvwin.pas):
        #
        #     if ultLetra = c then
        #         begin
        #             nrepUlt := nrepUlt + 1;
        #             if nrepUlt > 3 then
        #                 begin  sintClek;  c := ' ';  end;
        #         end
        #     else
        #         begin  nrepUlt := 0;  ultLetra := c;  end;
        #
        # Contando: a 1a ocorrencia zera o contador, a 2a leva a 1, a 3a a 2, a
        # 4a a 3 (ainda nao passa de 3) e a 5a leva a 4 -- e ai sim clica. Ou
        # seja: AS QUATRO PRIMEIRAS SAO FALADAS, E DA QUINTA EM DIANTE CADA UMA
        # VIRA UM CLIQUE, ate aparecer um caractere diferente. O "c := ' '"
        # depois do clique e' justamente o que impede o caractere de ser falado
        # ou pausado tambem: o clique entra NO LUGAR dele, nao alem dele.
        #
        # Duas coisas costumam surpreender, e as duas sao do original:
        #
        #   * O contador so e' mexido no ramo "else" do laco, que e' o ramo dos
        #     caracteres que NAO sao letra, digito nem espaco. Palavras, numeros
        #     e espacos passam ao largo e NAO zeram a contagem. Entao
        #     "a, b, c, d, e," clica na quinta virgula, mesmo com palavras no
        #     meio. So um simbolo DIFERENTE zera.
        #   * A regra nao e' de pontuacao: e' de QUALQUER simbolo. Uma linha de
        #     "=====", "-----", "*****" ou "#####" clica a partir do quinto,
        #     que e' exatamente o que o Dosvox faz ao ler uma linha de separacao
        #     num arquivo de texto.
        #
        # Devolve True quando este caractere deve virar clique.
        if character == self.SIMBOLO_QUE_NUNCA_CLICA:
            self._zerar_repeticao()
            return False
        if character == self._ultimo_simbolo_repetido:
            self._repeticoes_simbolo += 1
        else:
            self._repeticoes_simbolo = 0
            self._ultimo_simbolo_repetido = character
        return self._repeticoes_simbolo > 3

    def _pausa_ou_clek(self, character, duration):
        if self._notar_simbolo(character):
            return ("__CLEK__", self._clek_pcm)
        return ("__PAUSA__", duration)

    def _build_letter_sound_map(self, directory):
        mapping = {}
        if not os.path.isdir(directory):
            return mapping
        for name in os.listdir(directory):
            lower_name = name.lower()
            if lower_name.endswith(".wav"):
                mapping[os.path.splitext(lower_name)[0]] = os.path.join(directory, name)
        return mapping

    def _build_ascii_sound_map(self, letter_sound_map):
        mapping = {}
        for code in range(256):
            for key in (
                f"_{code}",
                f"_{code:03d}",
                f"_fon{code}",
                f"_vo{code}",
            ):
                path = letter_sound_map.get(key.lower())
                if path:
                    mapping[code] = path
                    break
        return mapping

    def definir_letras_rapidas(self, ativo):
        # Caixa de selecao "Acelerar letras": toca os wavs de uma pasta
        # alternativa (mais rapida) no lugar dos da pasta Letras normal,
        # processando o audio exatamente igual, so muda de onde ele vem.
        ativo = bool(ativo)
        if ativo == self.usar_letras_rapidas:
            return
        self.usar_letras_rapidas = ativo
        if ativo:
            self.letters_dir = self.letters_dir_rapido
            self._letter_sound_map = self._letter_sound_map_rapido
            self._ascii_sound_map = self._ascii_sound_map_rapido
        else:
            self.letters_dir = self.letters_dir_normal
            self._letter_sound_map = self._letter_sound_map_normal
            self._ascii_sound_map = self._ascii_sound_map_normal
        self._text_pcm_cache.clear()
        self._character_pcm_cache.clear()

    def _read_letter_wav(self, path, allow_truncated=False):
        cache_key = (path, bool(allow_truncated))
        cached = self._wav_cache.get(cache_key)
        if cached is not None:
            return cached if cached is not False else None
        try:
            with wave.open(path, "rb") as wav_file:
                if (
                    wav_file.getnchannels() != 1
                    or wav_file.getsampwidth() != 1
                    or wav_file.getframerate() != 11025
                ):
                    self._wav_cache[cache_key] = False
                    return None
                pcm = wav_file.readframes(wav_file.getnframes())
                expected_len = wav_file.getnframes() * wav_file.getnchannels() * wav_file.getsampwidth()
                if len(pcm) < expected_len and not allow_truncated:
                    self._wav_cache[cache_key] = False
                    return None
                if len(self._wav_cache) > 512:
                    self._wav_cache.clear()
                self._wav_cache[cache_key] = pcm
                return pcm
        except Exception:
            self._wav_cache[cache_key] = False
            return None

    def _get_direct_sound_by_keys(self, keys, allow_truncated=False):
        for key in keys:
            path = self._letter_sound_map.get(key.lower())
            if not path:
                continue
            pcm = self._read_letter_wav(path, allow_truncated=allow_truncated)
            if pcm:
                return pcm
        return None

    def _get_direct_character_sound(self, character):
        if not character:
            return None
        character = self._coerce_character_token(character)
        if not character:
            return None
        direct_keys = DIRECT_CHARACTER_SOUND_KEYS.get(character[0])
        if direct_keys:
            pcm = self._get_direct_sound_by_keys(direct_keys, allow_truncated=True)
            if pcm:
                return pcm
        code = cp1252_code(character[0])
        if code is None:
            return None
        path = self._ascii_sound_map.get(code)
        if path:
            pcm = self._read_letter_wav(path)
            if pcm:
                return pcm
        return None

    def _coerce_character_token(self, character):
        # O NUCLEO SO CONHECE CARACTERES, NAO NOMES DE TECLA.
        #
        # Antes, isto chamava resolve_named_key para traduzir "space", "f5" ou
        # "backspace" -- palavras que o NVDA usa para nomear teclas -- de volta
        # para o caractere correspondente. Nada disso e' do Dosvox: e' do NVDA.
        # A traducao passou para o driver, que e' quem fala a lingua do NVDA, e
        # o que chega aqui ja e' um caractere.
        if not isinstance(character, str):
            return character
        stripped = character.strip()
        return stripped if len(stripped) == 1 else character

    def _get_direct_word_sound(self, word):
        if not word:
            return None
        normalized = normalize_sound_key(word)
        if normalized not in DIRECT_WORD_SOUND_KEYS:
            return None
        keys = ("_" + normalized,) + DIRECT_WORD_SOUND_ALIASES.get(normalized, ())
        return self._get_direct_sound_by_keys(keys)

    def _normalize_unit_name(self, raw_name):
        return raw_name.upper().replace("^", "CIRC").replace("~", "TIL")

    def _append_exact_or_fallback_unit(self, units, raw_name, perc=1.0, forte=True):
        # forte diz se esta silaba e a tonica da palavra. E' o silabaForte de
        # carregaBufFala (dvinter.pas): so o difone atono (forte=False) e' que o
        # get_unit_audio corta. Viaja junto do difone na tripla (nome, perc,
        # forte); os marcadores continuam duplas.
        unit_name = self._normalize_unit_name(raw_name)
        if unit_name in self.engine.units:
            units.append((unit_name, perc, forte))
            return True
        return False

    def _append_buffer_units(self, raw_name, units, perc=1.0, forte=True):
        if self._append_exact_or_fallback_unit(units, raw_name, perc, forte):
            return
        if len(raw_name) <= 2:
            return
        last_char = raw_name[-1]
        if last_char in VOGAIS_DOSVOX:
            self._append_buffer_units(raw_name[:-1], units, perc * 0.9, forte)
            self._append_buffer_units("$" + last_char, units, perc, forte)
            return
        if raw_name.endswith("CIRC") and len(raw_name) > 6:
            self._append_buffer_units(raw_name[:-5], units, perc * 0.9, forte)
            self._append_buffer_units("$" + raw_name[-5:], units, perc, forte)
            return
        if raw_name.endswith("TIL"):
            base_name = raw_name[:-3]
            if not base_name:
                return
            vogal = base_name[-1].upper()
            if vogal in ("I", "U"):
                self._append_buffer_units(base_name, units, perc * 0.9, forte)
            else:
                # carregaBufFala forca silabaForte=2 (tonica) no pedaco CIRC e
                # silabaForte=1 (atona) no "$nn". Reproduzimos: CIRC vira forte,
                # o $NN nasal vira atono.
                self._append_buffer_units(base_name + "CIRC", units, perc * 0.9, True)
            self._append_buffer_units("$NN", units, 0.9, False)

    def _append_carrega_fala_units(self, syllable, units, perc=1.0):
        # A vogal MAIUSCULA marca a silaba tonica no texto de fonemas -- e' assim
        # que as regras a escrevem (o "A" de "gata", o "O" de "cachorro"). E'
        # dela que sai o silabaForte de carregaFala (dvinter.pas): basta UMA
        # vogal maiuscula no pedaco para a silaba inteira contar como tonica, e
        # entao nenhum de seus difones e' cortado pelo get_unit_audio. Como no
        # Pascal, a marca vale para todas as chamadas geradas por este pedaco.
        # O nome do arquivo continua indo em minuscula; a maiuscula so decide o
        # forte.
        if not syllable:
            return
        forte = any(ch in "AEIOU" for ch in syllable)
        nomearq = "$"
        for ch in syllable:
            if ch == "^":
                self._append_buffer_units(nomearq + "CIRC", units, perc, forte)
                nomearq = "$"
            elif ch == "~":
                self._append_buffer_units(nomearq + "TIL", units, perc, forte)
                nomearq = "$"
            else:
                nomearq += ch.lower()
        if nomearq != "$":
            self._append_buffer_units(nomearq, units, perc, forte)

    def _append_traduz_silaba_units(self, syllable, units, perc=1.0):
        if not syllable:
            return
        if len(syllable) == 1:
            self._append_carrega_fala_units(syllable, units, perc)
            return
        syllable_lower = syllable.lower()
        if len(syllable) > 2:
            if (
                syllable_lower[0] in CONSOANTES_DOSVOX
                and syllable_lower[1] in CONSOANTES_DOSVOX
                and not syllable_lower.startswith(("dj", "nh", "rr", "ks", "tch"))
            ):
                self._append_carrega_fala_units(syllable[0], units, 1.0)
                self._append_traduz_silaba_units(syllable[1:], units, perc)
                return
            if syllable_lower.endswith("rr"):
                self._append_traduz_silaba_units(syllable[:-2], units, perc)
                self._append_carrega_fala_units("rr", units, perc)
                return
            if syllable_lower[-1] in CONSOANTES_DOSVOX:
                self._append_traduz_silaba_units(syllable[:-1], units, perc)
                self._append_traduz_silaba_units(syllable[-1], units, perc)
                return
        if syllable_lower[-1] in SEMIVOGAIS_DOSVOX:
            if len(syllable) > 2 and syllable[-2] in VOGAIS_DOSVOX:
                self._append_traduz_silaba_units(syllable[:-1], units, 0.6)
                self._append_carrega_fala_units(syllable[-2:], units, perc)
                return
            if len(syllable) > 2 and syllable[-2] in ACENTOS_DOSVOX:
                if len(syllable) > 3:
                    if syllable[-2] == "~":
                        self._append_traduz_silaba_units(syllable[:-2] + "^", units, 0.6)
                    else:
                        self._append_traduz_silaba_units(syllable[:-1], units, 0.6)
                    self._append_carrega_fala_units(syllable[-3] + syllable[-1] + syllable[-2], units, perc)
                    return
                self._append_carrega_fala_units(syllable[0] + syllable[2] + syllable[1], units, perc)
                return
        if syllable != "_s" and syllable_lower.endswith("s"):
            self._append_traduz_silaba_units(syllable[:-1], units, 0.7)
            self._append_carrega_fala_units("s", units, perc)
            return
        self._append_carrega_fala_units(syllable, units, perc)

    def map_phonemes_to_units(self, ph_string):
        units = []
        syllables = [chunk for chunk in ph_string.strip().split() if chunk]
        for syllable in syllables:
            syllable = syllable.replace("/", "")
            if syllable:
                self._append_traduz_silaba_units(syllable, units, 1.0)
        # NAO se insere silencio entre as silabas de uma palavra. Em falaFonemas
        # (dvinter.pas) o silencio(intervalo) so entra quando o caractere ANTES
        # de pf nao e' espaco -- e dentro de uma palavra as silabas SAO
        # separadas por espaco no texto de fonemas (' /k/a/ /x/O^/ /rr/w/'),
        # entao ali nunca ha silencio. O unico ponto sem espaco antes e' o ']'
        # que fecha a palavra: por isso o INTERPAL cai ENTRE PALAVRAS de uma
        # mesma corrida, e e' inserido em units_from_text, nao aqui.
        return units

    def units_from_text(self, text, symbol_level=300):
        units = []
        tokens = preprocess_text(text, symbol_level=symbol_level, pausas=self.pausas, falar_tudo=not self.usar_letras_rapidas)

        def fim_de_palavra():
            # Igual ao Kotlin atual e ao Pascal: fim de palavra NAO descarrega
            # o buffer. Se algum dia PAUSA_ENTRE_PALAVRAS for diferente de
            # zero, ela e uma pausa externa e portanto fecha o buffer.
            if self.pausa_entre_palavras > 0:
                units.append(("__PAUSA__", self.pausa_entre_palavras))

        for idx, (kind, token) in enumerate(tokens):
            # Kotlin: INTERPAL entra entre tokens Word consecutivos, inclusive
            # quando uma dessas palavras depois cair em soletracao.
            if self.intervalo_segundos > 0 and idx > 0 and kind == "word" and tokens[idx - 1][0] == "word":
                units.append(("__SIL__", _silencio_amostras(self.intervalo_segundos)))

            if kind == "pause":
                duration, character = token
                units.append(self._pausa_ou_clek(character, duration))
                continue
            if kind == "character":
                direct_pcm = self._get_direct_character_sound(token)
                if direct_pcm:
                    units.append(("__PCM__", direct_pcm)); fim_de_palavra()
                else:
                    units.extend(self.units_from_character(token))
                continue
            if kind == "symbol":
                if self._notar_simbolo(token):
                    units.append(("__CLEK__", self._clek_pcm))
                else:
                    direct_pcm = self._get_direct_character_sound(token)
                    if direct_pcm:
                        units.append(("__PCM__", direct_pcm))
                    else:
                        mapped = TYPED_SYMBOL_NAMES.get(token) or SYMBOL_WORDS.get(token, token)
                        units.extend(self.units_from_text(mapped, symbol_level=0))
                continue
            if kind == "numberWord":
                handled = False
                if token in ("menos", "hifen"):
                    direct_pcm = self._get_direct_sound_by_keys(("_menos",), allow_truncated=True) or self._get_direct_word_sound("menos")
                    if direct_pcm:
                        units.append(("__PCM__", direct_pcm)); fim_de_palavra(); handled = True
                if not handled:
                    simbolo = NUMBER_SYMBOL_WORD_TO_CHAR.get(token)
                    if simbolo is not None:
                        direct_pcm = self._get_direct_character_sound(simbolo)
                        if direct_pcm:
                            units.append(("__PCM__", direct_pcm)); fim_de_palavra(); handled = True
                if not handled:
                    direct_pcm = self._get_direct_word_sound(token)
                    if direct_pcm:
                        units.append(("__PCM__", direct_pcm)); fim_de_palavra(); handled = True
                if handled:
                    continue

            preparada = self.g2p.preparar_palavra_completa(token)
            if not self.g2p.tem_vogal(preparada[0]):
                for letra in preparada[0]:
                    direct_pcm = self._get_direct_character_sound(letra)
                    if direct_pcm:
                        units.append(("__PCM__", direct_pcm))
                    else:
                        units.extend(self.units_from_character(letra))
                fim_de_palavra()
                continue
            ph = self._phonetize_word(token, preparada)
            units.extend(self.map_phonemes_to_units(ph))
            fim_de_palavra()
        return units

    def _phonetize_word(self, token, preparada=None):
        key = token.lower()
        cached = self._phoneme_cache.get(key)
        if cached is not None:
            return cached
        ph = self.g2p.phonetize_word(token, preparada=preparada)
        if len(self._phoneme_cache) > 2048:
            self._phoneme_cache.clear()
        self._phoneme_cache[key] = ph
        return ph

    def _get_cached_pcm(self, cache, key):
        return cache.get(key)

    def _put_cached_pcm(self, cache, key, pcm, max_items=512):
        if len(cache) > max_items:
            cache.clear()
        cache[key] = pcm
        return pcm

    def units_from_character(self, character):
        if not character:
            return []
        character = self._coerce_character_token(character)
        spoken = CHARACTER_NAMES.get(character.lower())
        if spoken is None:
            spoken = TYPED_SYMBOL_NAMES.get(character)
        if spoken is None:
            spoken = SYMBOL_WORDS.get(character, character)
        return self.units_from_text(spoken)

    def synthesize_text(self, text, symbol_level=300):
        text = self.descricoes.aplicar(text)
        if not text:
            return b""
        cortafala = self.cortafala
        # Texto com pontuacao que participa do contador de repeticao do
        # clique (ver _pausa_ou_clek) nunca usa cache: o mesmo texto pode
        # precisar de pausa numa fala e de clique na proxima, dependendo
        # do que foi falado antes -- cache aqui congelaria a decisao
        # errada.
        # Qualquer simbolo pode virar clique dependendo do que veio antes, entao
        # qualquer simbolo torna o resultado dependente do contador -- e nao so
        # a pontuacao, como antes.
        tem_pontuacao_stateful = any(eh_simbolo_do_clek(ch) for ch in text)
        cache_key = (text, int(symbol_level), bool(cortafala))
        pcm = None if tem_pontuacao_stateful else self._get_cached_pcm(self._text_pcm_cache, cache_key)
        if pcm is None:
            units = self.units_from_text(text, symbol_level=symbol_level)
            pcm = self.engine.synthesize(units, cortafala=cortafala, rapidinho=self.rapidinho)
            if not tem_pontuacao_stateful:
                pcm = self._put_cached_pcm(self._text_pcm_cache, cache_key, pcm)
        return pcm

    def synthesize_text_streaming(self, text, symbol_level=300):
        text = self.descricoes.aplicar(text)
        if not text:
            return
        units = self.units_from_text(text, symbol_level=symbol_level)
        yield from self.engine.synthesize_streaming(units, cortafala=self.cortafala, rapidinho=self.rapidinho)

    def synthesize_character(self, character):
        sanitized = self.descricoes.aplicar(character).strip()
        if len(sanitized) != 1:
            return self.synthesize_text(character)
        character = sanitized
        cortafala = self.cortafala
        # Os simbolos que o NVDA manda como caractere isolado (tudo o que nao e'
        # ponto, virgula, ponto e virgula, dois pontos, parenteses ou hifen --
        # ver PONTUACAO_COM_PAUSA_PROPRIA) chegam por aqui, e nao por
        # units_from_text. Sao justamente "=", "*", "#", "!", "?", aspas... os
        # que mais aparecem repetidos numa linha de separacao. O contador do
        # clique precisa valer aqui tambem, e e' o MESMO contador, porque no
        # Pascal ha um so, dentro do laco de sintetiza.
        #
        # Letras e digitos (modo de soletracao, revisao de tela) nunca entram na
        # contagem, exatamente como no Pascal: eles desviam para outros ramos do
        # laco antes de chegar ao else.
        if eh_simbolo_do_clek(character):
            if self._notar_simbolo(character):
                # Nunca vai para o cache: o mesmo caractere pode precisar de eco
                # numa posicao e de clique na seguinte.
                return self._clek_pcm
        cache_key = (character, bool(cortafala))
        pcm = self._get_cached_pcm(self._character_pcm_cache, cache_key)
        if pcm is not None:
            return pcm
        direct_pcm = self._get_direct_character_sound(character)
        if direct_pcm:
            pcm = direct_pcm
            if cortafala:
                pcm = apply_cortafala_to_pcm(pcm, rapidinho=self.rapidinho)
            return self._put_cached_pcm(self._character_pcm_cache, cache_key, pcm)
        units = self.units_from_character(character)
        pcm = self.engine.synthesize(units, cortafala=cortafala, rapidinho=self.rapidinho)
        return self._put_cached_pcm(self._character_pcm_cache, cache_key, pcm)

    def som_de_caractere_resolvido(self, caractere):
        """Toca a gravacao de um caractere que a plataforma ja resolveu.

        Espelha DosvoxNativeSynth.somDeCaractereResolvido do Kotlin: nao passa
        por descricoes.dic nem por strip(). Isso e essencial para o espaco
        literal, cuja gravacao e _32.WAV e seria perdida por " ".strip().
        Retorna None quando nao existe gravacao direta, para o chamador poder
        recorrer ao caminho normal de fala.
        """
        direct_pcm = self._get_direct_character_sound(caractere)
        if direct_pcm is None:
            return None
        if self.cortafala:
            return apply_cortafala_to_pcm(direct_pcm, rapidinho=self.rapidinho)
        return direct_pcm


def get_available_voice_variants(module_dir):
    data_dir = os.path.join(module_dir, VOICE_DIR_NAME)
    if not os.path.isdir(data_dir):
        return {}
    variants = {}
    labels = {
        "Difones": "Difones",
        "Difones2": "Difones 2",
        "Difones3": "Difones 3",
        "difones5": "Difones 5",
        "novodifo": "Novo difo",
    }
    for entry in os.listdir(data_dir):
        if not entry.lower().endswith(".ind"):
            continue
        voice_id = entry[:-4]
        ind_path = os.path.join(data_dir, f"{voice_id}.ind")
        dif_path = os.path.join(data_dir, f"{voice_id}.dif")
        if os.path.exists(ind_path) and os.path.exists(dif_path):
            variants[voice_id] = labels.get(voice_id, voice_id)
    return dict(sorted(variants.items(), key=lambda item: (item[0] != DEFAULT_VOICE_ID, item[0].lower())))


def get_available_voices(module_dir):
    if get_available_voice_variants(module_dir):
        return {"dosvoxNative": "Dosvox nativa"}
    return {}





















# ==========================================================================
#  SessaoDosvox -- tudo o que uma casca precisa, menos a casca
# --------------------------------------------------------------------------
#  A ideia e' que uma casca (o driver do NVDA, um motor SAPI 5, um servico de
#  TTS do Android, um gerador de livro falado) so precise saber TRES coisas:
#
#      sessao = SessaoDosvox(pasta_do_complemento)
#      pcm    = sessao.falar(texto)          # ou falar_caractere(ch)
#      taxa   = sessao.taxa_saida            # com que taxa tocar esse pcm
#
#  Tudo o mais -- ler e gravar o dosvox.ini, vigiar a data do arquivo, escolher
#  o banco de difones, reconstruir o motor quando o banco muda, guardar o
#  cortafala, o rapidinho e as letras rapidas, fatiar o texto em pedacos para
#  nao demorar a comecar a falar -- mora AQUI, e nao na casca.
#
#  Isso importa porque o que mora na casca precisa ser reescrito uma vez por
#  plataforma, e cada reescrita e' uma chance nova de errar em silencio. Foi
#  exatamente o que aconteceu com o cortafala, que morava no driver do NVDA e
#  era passado como argumento: esquecer de passa-lo nao dava erro nenhum, so
#  fazia a voz sair errada.
# ==========================================================================

# Pedaco maximo de texto entregue de uma vez ao sintetizador. Nao e' uma
# limitacao do motor: e' latencia. Falar comeca assim que o primeiro pedaco
# esta pronto, em vez de esperar a frase inteira ficar pronta.
TAMANHO_TRECHO_PADRAO = 40

DOSVOX_INI_NOME = "dosvox.ini"


class SessaoDosvox:
    def __init__(self, pasta_raiz, tamanho_trecho=TAMANHO_TRECHO_PADRAO):
        self.pasta_raiz = pasta_raiz
        self.tamanho_trecho = tamanho_trecho
        self.caminho_ini = os.path.join(pasta_raiz, VOICE_DIR_NAME, DOSVOX_INI_NOME)
        self.criou_o_ini = garantir_dosvox_ini(self.caminho_ini)

        self.variantes = get_available_voice_variants(pasta_raiz)
        if not self.variantes:
            raise RuntimeError("Nenhum banco de difones encontrado.")

        self._mtime = None
        self.motor = None
        self.config = dict(CONFIG_PADRAO)
        self.recarregar(forcar=True)

    # ---- os quatro ajustes -------------------------------------------------

    @property
    def difones(self):
        # O painel do NVDA precisa do nome do banco como ele aparece na lista.
        return self.difones_resolvido()

    @property
    def cortafala(self):
        return self.config["cortafala"]

    @property
    def rapidinho(self):
        return self.config["rapidinho"]

    @property
    def letras_rapidas(self):
        return self.config["letras_rapidas"]

    @property
    def reduzir_volume(self):
        return self.config.get("reduzir_volume", False)

    @property
    def interpal(self):
        return int(self.config.get("interpal", 0))

    @property
    def cortefon(self):
        return int(self.config.get("cortefon", 0))

    @property
    def sobrafon(self):
        return int(self.config.get("sobrafon", 0))

    @property
    def pausa_ponto(self):
        return int(self.config.get("pausaponto_ms", 150))

    @property
    def pausa_virgula(self):
        return int(self.config.get("pausavirg_ms", 50))

    @property
    def pausa_dois_pontos(self):
        return int(self.config.get("pausadoispontos_ms", 100))

    def definir_difones(self, valor):
        if valor not in self.variantes or valor == self.difones_resolvido():
            return False
        self.config["difones"] = valor
        self._reconstruir_motor()
        self.gravar()
        return True

    def difones_resolvido(self):
        """O DIFONES do arquivo e' comparado sem ligar para maiuscula e
        minuscula: o dosvox.ini original traz "difones2", e o banco se chama
        "Difones2". Se nao casar com nenhum banco, cai no padrao."""
        pedido = str(self.config.get("difones", "")).strip().lower()
        for nome in self.variantes:
            if nome.lower() == pedido:
                return nome
        for nome in self.variantes:
            if nome.lower() == DIFONES_PADRAO.lower():
                return nome
        return next(iter(self.variantes))

    def definir_cortafala(self, valor):
        self.config["cortafala"] = bool(valor)
        self.motor.definir_cortafala(self.config["cortafala"])
        self.gravar()

    def definir_rapidinho(self, valor):
        """Devolve True se a taxa de saida mudou -- ou seja, se quem chamou
        precisa reabrir o dispositivo de audio."""
        antes = self.taxa_saida
        self.config["rapidinho"] = bool(valor)
        self.motor.definir_rapidinho(self.config["rapidinho"])
        self.gravar()
        return self.taxa_saida != antes

    def definir_letras_rapidas(self, valor):
        self.config["letras_rapidas"] = bool(valor)
        self.motor.definir_letras_rapidas(self.config["letras_rapidas"])
        self.gravar()

    def definir_reduzir_volume(self, valor):
        # Como no Android, e uma opcao de saida: nao altera o motor nem seus caches.
        self.config["reduzir_volume"] = bool(valor)
        self.gravar()


    def definir_interpal(self, valor):
        self.config["interpal"] = max(0, min(INTERPAL_MAX, int(valor)))
        self.motor.definir_interpal(self.config["interpal"])
        self.gravar()

    def definir_cortefon(self, valor):
        self.config["cortefon"] = max(0, min(CORTEFON_MAX, int(valor)))
        self.motor.definir_cortefon(self.config["cortefon"])
        self.gravar()

    def definir_sobrafon(self, valor):
        self.config["sobrafon"] = max(0, min(SOBRAFON_MAX, int(valor)))
        self.motor.definir_sobrafon(self.config["sobrafon"])
        self.gravar()

    def _definir_pausa_ms(self, chave, valor):
        ms = max(0, min(PAUSA_MAX, int(valor)))
        self.config[chave] = ms
        aplicar_config_no_motor(self.motor, self.config)
        self.gravar()

    def definir_pausa_ponto(self, valor):
        self._definir_pausa_ms("pausaponto_ms", valor)

    def definir_pausa_virgula(self, valor):
        self._definir_pausa_ms("pausavirg_ms", valor)

    def definir_pausa_dois_pontos(self, valor):
        self._definir_pausa_ms("pausadoispontos_ms", valor)



    # ---- o arquivo ---------------------------------------------------------

    def gravar(self):
        escrever_dosvox_ini(self.caminho_ini, self.config)
        # Anota a data nova, para que recarregar() nao releia (e desfaca) o que
        # acabamos de gravar.
        try:
            self._mtime = os.path.getmtime(self.caminho_ini)
        except OSError:
            self._mtime = None

    def recarregar(self, forcar=False):
        """Relê o dosvox.ini se ele mudou no disco, e aplica tudo no motor.
        Devolve True se a taxa de saida mudou (o dispositivo de audio precisa
        ser reaberto). Chame no comeco de cada fala: e' so um os.path.getmtime
        quando nada mudou."""
        try:
            mtime = os.path.getmtime(self.caminho_ini)
        except OSError:
            return False
        if not forcar and mtime == self._mtime:
            return False
        self._mtime = mtime

        taxa_antes = self.taxa_saida if self.motor is not None else None
        banco_antes = self.difones_resolvido() if self.motor is not None else None
        self.config = ler_dosvox_ini(self.caminho_ini)
        if self.motor is None or self.difones_resolvido() != banco_antes:
            self._reconstruir_motor()
        else:
            self._aplicar_no_motor()
        return taxa_antes is not None and self.taxa_saida != taxa_antes

    def _reconstruir_motor(self):
        # Igual ao Kotlin: regras, excecoes, descricoes e gravacoes ficam
        # carregadas; numa troca de voz muda apenas o banco .ind/.dif.
        if self.motor is None:
            self.motor = DosvoxNativeSynth(self.pasta_raiz, self.difones_resolvido())
        else:
            self.motor.definir_banco(self.difones_resolvido())
        self._aplicar_no_motor()

    def _aplicar_no_motor(self):
        self.motor.definir_cortafala(self.config["cortafala"])
        self.motor.definir_rapidinho(self.config["rapidinho"])
        self.motor.definir_letras_rapidas(self.config["letras_rapidas"])
        aplicar_config_no_motor(self.motor, self.config)
        self.limpar_cache()

    def limpar_cache(self):
        self.motor._text_pcm_cache.clear()
        self.motor._character_pcm_cache.clear()

    # ---- falar -------------------------------------------------------------

    @property
    def taxa_saida(self):
        return self.motor.taxa_saida if self.motor is not None else TAXA_BASE

    @property
    def pausas(self):
        return self.motor.pausas if self.motor is not None else PAUSAS_PADRAO

    def trechos(self, texto):
        """Fatia o texto em pedacos entregaveis: nunca corta palavra ao meio, e
        prefere cortar depois de uma pontuacao, que e' onde a fala ja teria uma
        pausa natural -- assim a emenda entre um pedaco e o seguinte nao se
        ouve. Porte literal do que estava no driver do NVDA."""
        texto = str(texto or "")
        if len(texto) <= self.tamanho_trecho:
            if texto:
                yield texto
            return
        atual = []
        tamanho = 0
        for palavra in re.findall(r"\S+\s*", texto, re.UNICODE):
            n = len(palavra)
            if atual and tamanho + n > self.tamanho_trecho:
                yield "".join(atual)
                atual = []
                tamanho = 0
            atual.append(palavra)
            tamanho += n
            if tamanho >= 20 and re.search(r"[.!?;:]\s*$", palavra, re.UNICODE):
                yield "".join(atual)
                atual = []
                tamanho = 0
        if atual:
            yield "".join(atual)

    def falar(self, texto, symbol_level=300):
        return self.motor.synthesize_text(texto, symbol_level=symbol_level)

    def falar_em_fluxo(self, texto, symbol_level=300):
        yield from self.motor.synthesize_text_streaming(texto, symbol_level=symbol_level)

    def falar_caractere(self, caractere):
        return self.motor.synthesize_character(caractere)

    def falar_caractere_resolvido(self, caractere):
        return self.motor.som_de_caractere_resolvido(caractere)

    def silencio(self, segundos):
        return b"\x80" * max(1, int(self.taxa_saida * max(0.0, segundos)))

    def comecar_elocucao(self):
        # sintetiza (dvwin.pas) comeca sempre com ultLetra := ' ' e nrepUlt := 0:
        # o contador do clique vale por elocucao, e nunca atravessa de uma fala
        # para a proxima.
        self.motor.resetar_contador_pontuacao()
