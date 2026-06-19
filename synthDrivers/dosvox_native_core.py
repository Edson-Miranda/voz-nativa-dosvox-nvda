# -*- coding: UTF-8 -*-
import collections
import os
import re
import struct
import unicodedata
import wave


VOICE_DIR_NAME = "dosvox_data"
DEFAULT_VOICE_ID = "Difones2"
LETTERS_DIR_NAME = "Letras"

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

PAUSE_CHARS = set(".,;:!?()[]{}")

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

KEY_NAME_TO_CHAR = {
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
    "fecha angulo": ">",
    "fecha ângulo": ">",
    "maior que": ">",
    "barra vertical": "|",
    "pipe": "|",
    "euro": "\u20ac",
    "simbolo do euro": "\u20ac",
    "símbolo do euro": "\u20ac",
    "marcador": "\u2022",
    "bolinha": "\u2022",
    "bullet": "\u2022",
}

SYMBOL_SPEAK_LEVELS = {
    ".": 100,
    ",": 100,
    "!": 100,
    "?": 100,
    ":": 200,
    ";": 200,
    "(": 300,
    ")": 300,
    "[": 300,
    "]": 300,
    "{": 300,
    "}": 300,
    "<": 300,
    ">": 300,
    "/": 300,
    "\\": 300,
    "+": 300,
    "-": 200,
    "_": 300,
    "=": 300,
    "*": 300,
    "\"": 300,
    "'": 300,
    "`": 300,
    "~": 300,
    "^": 300,
    "@": 300,
    "#": 300,
    "$": 300,
    "%": 300,
    "&": 300,
    "|": 300,
    "\u00aa": 300,
    "\u00ba": 300,
    "\u20ac": 300,
    "\u2022": 300,
}


def split_source_symbols(text, symbol_level=300):
    """Split real source symbols from text before NVDA expands their names."""
    parts = []
    text_buffer = []
    for character in str(text or ""):
        is_known_symbol = character in TYPED_SYMBOL_NAMES or character in SYMBOL_WORDS
        should_speak = symbol_level >= SYMBOL_SPEAK_LEVELS.get(character, 300)
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

PRONUNCIATION_OVERRIDES = {
    "tres": "treis",
    "três": "treis",
    "exclamação": "esclamação",
    "esquerda": "esquêrda",
    "esquerdo": "esquêrdo",
    "baixo": "baicho",
    "haha": "rárárá",
}

DIRECT_WORD_SOUND_KEYS = {
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
    "menos",
    "virgula",
    "ponto",
    "por",
    "cento",
}

DIRECT_CHARACTER_SOUND_KEYS = {
    " ": ("32", "_32", "032", "_032"),
    "\"": ("_vo34", "_34"),
    "%": ("37", "_37"),
    "&": ("38", "_38"),
    "(": ("40", "_40", "_vo40"),
    ")": ("41", "_41", "_vo41"),
    ":": ("_vo58", "_58"),
    ";": ("_vo59", "_59"),
    "<": ("60", "_60"),
    ">": ("62", "_62"),
    "_": ("95", "_95"),
    "`": ("96", "_96"),
    "{": ("123", "_123"),
    "|": ("124", "_124"),
    "}": ("125", "_125"),
    "\u20ac": ("128", "_128"),
    "\u2022": ("149", "_149"),
    "[": ("_vo91", "_91"),
    "]": ("_vo93", "_93"),
}

SPOKEN_NAME_SYMBOLS = set()


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


def normalize_sound_key(text):
    text = normalize_text(text).lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    stripped = stripped.replace("ç", "c")
    return re.sub(r"[^a-z0-9]+", "", stripped)


def normalize_lookup_text(text):
    text = normalize_text(text).strip().lower()
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped)


def rate_to_speed(rate):
    rate = max(0, min(100, int(rate)))
    # 50 is neutral. Keep the range conservative to preserve audio quality.
    return 0.7 + (rate / 100.0) * 0.6


def apply_speed_to_pcm(pcm_bytes, speed):
    if not pcm_bytes:
        return pcm_bytes
    speed = max(0.4, min(2.0, float(speed)))
    if abs(speed - 1.0) < 0.01:
        return pcm_bytes
    source = memoryview(pcm_bytes)
    target_length = max(1, int(len(source) / speed))
    output = bytearray(target_length)
    for out_idx in range(target_length):
        src_idx = min(len(source) - 1, int(out_idx * speed))
        output[out_idx] = source[src_idx]
    return bytes(output)


def apply_volume_to_pcm(pcm_bytes, volume):
    if not pcm_bytes:
        return pcm_bytes
    volume = max(0, min(100, int(volume)))
    gain = volume / 100.0
    if abs(gain - 1.0) < 0.01:
        return pcm_bytes
    output = bytearray(len(pcm_bytes))
    for i, sample in enumerate(pcm_bytes):
        centered = sample - 128
        adjusted = int(centered * gain)
        output[i] = max(0, min(255, adjusted + 128))
    return bytes(output)


def apply_pitch_to_pcm(pcm_bytes, pitch):
    if not pcm_bytes:
        return pcm_bytes
    pitch = max(0, min(100, int(pitch)))
    pitch_factor = 0.8 + (pitch / 100.0) * 0.4
    if abs(pitch_factor - 1.0) < 0.01:
        return pcm_bytes
    shifted = apply_speed_to_pcm(pcm_bytes, pitch_factor)
    return apply_speed_to_pcm(shifted, 1.0 / pitch_factor)


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
    groups = [
        (1_000_000_000, "bilhao", "bilhoes"),
        (1_000_000, "milhao", "milhoes"),
        (1_000, "mil", "mil"),
        (1, "", ""),
    ]
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
            parts.append("mil" if amount == 1 else f"{split_hundreds(amount)} mil")
        else:
            label = singular if amount == 1 else plural
            parts.append(f"um {label}" if amount == 1 else f"{number_to_words(amount)} {label}")
    result = []
    for idx, part in enumerate(parts):
        if idx > 0:
            result.append("e" if idx == len(parts) - 1 else "")
        result.append(part)
    return " ".join(chunk for chunk in result if chunk).strip()


def digits_to_words(text):
    return " ".join(UNITS[int(ch)] for ch in text if ch.isdigit())


def expand_numeric_token(token):
    token = token.strip()
    if re.fullmatch(r"\d+", token):
        return number_to_words(int(token))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        integer, _, fraction = token.partition(",")
        integer = integer.replace(".", "")
        return f"{number_to_words(int(integer))} virgula {digits_to_words(fraction)}" if fraction else number_to_words(int(integer))
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
        integer, _, fraction = token.partition(".")
        integer = integer.replace(",", "")
        return f"{number_to_words(int(integer))} ponto {digits_to_words(fraction)}" if fraction else number_to_words(int(integer))
    if re.fullmatch(r"\d+[.,]\d+", token):
        integer, sep, fraction = re.split(r"([.,])", token, maxsplit=1)
        word = "virgula" if sep == "," else "ponto"
        return f"{number_to_words(int(integer))} {word} {digits_to_words(fraction)}"
    for sep, word in (("/", "barra"), ("-", "hifen"), (":", "dois pontos")):
        if sep in token and re.fullmatch(r"\d+(?:\%s\d+)+" % re.escape(sep), token):
            return f" {word} ".join(expand_numeric_token(part) for part in token.split(sep))
    return digits_to_words(token)


def preprocess_text(text, symbol_level=300):
    text = normalize_text(text)
    text = re.sub(r"\s+", " ", text)
    tokens = re.findall(r"[Ff]\d{1,2}|\d[\d.,:/-]*%?|[A-Za-zÀ-ÖØ-öø-ÿ]+|[^\s]", text, re.UNICODE)
    output = []
    for token in tokens:
        if re.fullmatch(r"[Ff]\d{1,2}", token):
            output.append(("character", "F"))
            output.extend(("character", digit) for digit in token[1:])
            continue
        if WORD_RE.fullmatch(token):
            lowered = token.lower()
            if len(lowered) > 1 and len(set(lowered)) == 1:
                output.extend(("character", ch) for ch in token)
                continue
            output.append(("word", token))
        elif re.fullmatch(r"\d[\d.,:/-]*%?", token):
            expanded = f"{expand_numeric_token(token[:-1])} por cento" if token.endswith("%") else expand_numeric_token(token)
            # Preserve the numeric origin. Dedicated number recordings must
            # not leak into written words such as "uma", "ponto" or "menos".
            output.extend(("numberWord", word) for word in expanded.split())
        elif token in PAUSE_CHARS:
            if symbol_level >= SYMBOL_SPEAK_LEVELS.get(token, 300):
                output.append(("symbol", token))
            else:
                output.append(("pause", token))
        else:
            mapped = SYMBOL_WORDS.get(token)
            if mapped and symbol_level >= SYMBOL_SPEAK_LEVELS.get(token, 300):
                output.append(("symbol", token))
            else:
                output.append(("pause", token))

    return output


class DifonesEngine:
    def __init__(self, ind_path, dif_path):
        self.ind_path = ind_path
        self.dif_path = dif_path
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

    def get_unit_audio(self, name, perc=1.0):
        name = name.upper()
        if name not in self.units:
            return None
        if perc >= 1.0:
            cached = self._unit_cache.get(name)
            if cached is not None:
                return cached
        offset, length = self.units[name]
        data = self._unit_cache.get(name)
        if data is None:
            data = self._dif_data[offset : offset + length]
            self._unit_cache[name] = data
        if perc >= 1.0:
            return data
        cache_key = (name, round(float(perc), 4))
        cached = self._clipped_unit_cache.get(cache_key)
        if cached is not None:
            return cached
        clipped_length = max(1, int(len(data) * max(0.0, perc)))
        clipped = data[:clipped_length]
        if len(self._clipped_unit_cache) > 512:
            self._clipped_unit_cache.clear()
        self._clipped_unit_cache[cache_key] = clipped
        return clipped

    def synthesize(self, unit_names):
        audio_data = bytearray()
        for item in unit_names:
            if isinstance(item, tuple):
                name, perc = item
            else:
                name, perc = item, 1.0
            if name == "__PCM__":
                audio_data.extend(perc)
                continue
            if name == "__SIL__":
                silence_len = max(1, int(11025 * max(0.0, perc)))
                audio_data.extend(b"\x80" * silence_len)
                continue
            data = self.get_unit_audio(name, perc)
            if data:
                audio_data.extend(data)
        return bytes(audio_data)


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
                line = line.strip()
                if not line or line.startswith("*") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                self.exceptions[key.lower()] = value

    def _load_rules(self, path):
        with open(path, "r", encoding="latin-1") as file_obj:
            lines = file_obj.readlines()
        for raw in lines:
            raw = raw.strip()
            if not raw or raw.startswith(";"):
                continue
            if "|" in raw:
                raw = raw[: raw.rfind("|")].strip()
            match = re.match(r"^(.*?)\((.*?)\)(.*?)=(.*)$", raw)
            if not match:
                continue
            prefix, target, suffix, result = match.groups()
            rule = {
                "prefix": prefix,
                "target": target,
                "suffix": suffix,
                "result": result,
                "priority": len(target) * 100 + len(prefix) + len(suffix),
            }
            first_char = target[0].lower() if target else ""
            self.rules_by_first[first_char].append(rule)
        for first in self.rules_by_first:
            self.rules_by_first[first].sort(key=lambda item: item["priority"], reverse=True)

    def separa_acentos(self, text):
        mapping = {
            "À": "a`", "Á": "a'", "Â": "a^", "Ã": "a~", "Ä": 'a"',
            "Ç": "ss", "È": "e`", "É": "e'", "Ê": "e^", "Ë": 'e"',
            "Ì": "i`", "Í": "i'", "Î": "i^", "Ï": 'i"', "Ñ": "nh",
            "Ò": "o`", "Ó": "o'", "Ô": "o^", "Õ": "o~", "Ö": "o`",
            "Ù": "u`", "Ú": "u'", "Û": "u^", "Ü": "u", "Ý": "y",
            "ß": "ss", "à": "a`", "á": "a'", "â": "a^", "ã": "a~",
            "ä": 'a"', "ç": "ss", "è": "e`", "é": "e'", "ê": "e^",
            "ë": 'e"', "ì": "i`", "í": "i'", "î": "i^", "ï": 'i"',
            "ñ": "nh", "ò": "o`", "ó": "o'", "ô": "o^", "õ": "o~",
            "ö": "o`", "ù": "u`", "ú": "u'", "û": "u^", "ü": "u",
            "ý": "y", "ÿ": "y",
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
                elif (i == 0 or prev_char == " ") and (i == len(chars) - 1 or next_char == " "):
                    ch = "i"
            out.append(mapping.get(ch, ch))
        return "".join(out)

    def _build_word_array(self, word):
        arr = [" "] * (len(word) + 4)
        for i, ch in enumerate(word, start=1):
            arr[i] = ch
        return arr

    def marca_tonica(self, word):
        tem_acento = any(c in self.acentos for c in word)
        pos_letra = len(word)
        num_vogais = sum(1 for c in word if c in self.vogal)
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
            if (pos_i + j) > pos_letra or ch.upper() != palavra[pos_i + j].upper():
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
                ok = idx < pos_letra + 1 and ch.upper() == palavra[idx].upper()
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
                ok = idx != 0 and ch.upper() == palavra[idx].upper()
                if ok:
                    idx -= 1
            if not ok:
                return False
        return True

    def phonetize_word(self, word):
        word = normalize_text(word)
        word = self.separa_acentos(word).lower()
        word = self.trata_excessoes(word)
        word = self.marca_tonica(word)
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
                chars = list(seq_fonemas)
                for j, ch in enumerate(chars):
                    if ch in self.vog_minuscula:
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
    def __init__(self, module_dir, voice_id):
        data_dir = os.path.join(module_dir, VOICE_DIR_NAME)
        ind_path = os.path.join(data_dir, f"{voice_id}.ind")
        dif_path = os.path.join(data_dir, f"{voice_id}.dif")
        rules_path = os.path.join(data_dir, "Regras.rgr")
        exc_path = os.path.join(data_dir, "portug.exc")
        self.letters_dir = os.path.join(module_dir, LETTERS_DIR_NAME)
        self._letter_sound_map = self._build_letter_sound_map()
        self._ascii_sound_map = self._build_ascii_sound_map()
        self._wav_cache = {}
        self._phoneme_cache = {}
        self._text_pcm_cache = {}
        self._character_pcm_cache = {}
        self.engine = DifonesEngine(ind_path, dif_path)
        self.g2p = RegrasParser(rules_path, exc_path)

    def _build_letter_sound_map(self):
        mapping = {}
        if not os.path.isdir(self.letters_dir):
            return mapping
        for name in os.listdir(self.letters_dir):
            lower_name = name.lower()
            if lower_name.endswith(".wav"):
                mapping[os.path.splitext(lower_name)[0]] = os.path.join(self.letters_dir, name)
        return mapping

    def _build_ascii_sound_map(self):
        mapping = {}
        for code in range(256):
            for key in (
                f"_{code}",
                f"_{code:03d}",
                f"_fon{code}",
                f"_vo{code}",
            ):
                path = self._letter_sound_map.get(key.lower())
                if path:
                    mapping[code] = path
                    break
        return mapping

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
        if character[0] in SPOKEN_NAME_SYMBOLS:
            return None
        direct_keys = DIRECT_CHARACTER_SOUND_KEYS.get(character[0])
        if direct_keys:
            pcm = self._get_direct_sound_by_keys(direct_keys, allow_truncated=True)
            if pcm:
                return pcm
        code = ord(character[0])
        path = self._ascii_sound_map.get(code)
        if path:
            pcm = self._read_letter_wav(path)
            if pcm:
                return pcm
        return None

    def _coerce_character_token(self, character):
        if not isinstance(character, str):
            return character
        stripped = character.strip()
        if len(stripped) == 1:
            return stripped
        resolved = resolve_named_key(stripped)
        if resolved is None:
            return character
        kind, value = resolved
        if kind == "character":
            return value
        return character

    def _get_direct_symbol_name_sound(self, word):
        resolved = resolve_named_key(word)
        if resolved is None:
            return None
        kind, value = resolved
        if kind != "character" or len(value) != 1:
            return None
        if value.isalnum() and value not in ("\u00aa", "\u00ba"):
            return None
        return self._get_direct_character_sound(value)

    def _get_direct_word_sound(self, word):
        if not word:
            return None
        normalized = normalize_sound_key(word)
        if normalized not in DIRECT_WORD_SOUND_KEYS:
            return None
        key = "_" + normalized
        path = self._letter_sound_map.get(key.lower())
        if not path:
            return None
        return self._read_letter_wav(path)

    def _normalize_unit_name(self, raw_name):
        return raw_name.upper().replace("^", "CIRC").replace("~", "TIL")

    def _append_exact_or_fallback_unit(self, units, raw_name, perc=1.0):
        unit_name = self._normalize_unit_name(raw_name)
        if unit_name in self.engine.units:
            units.append((unit_name, perc))
            return True
        for w_rep in ["O", "U"]:
            for y_rep in ["I"]:
                fallback_name = unit_name.replace("W", w_rep).replace("Y", y_rep)
                if fallback_name in self.engine.units:
                    units.append((fallback_name, perc))
                    return True
        return False

    def _append_buffer_units(self, raw_name, units, perc=1.0):
        if self._append_exact_or_fallback_unit(units, raw_name, perc):
            return
        if len(raw_name) <= 2:
            return
        last_char = raw_name[-1]
        if last_char.upper() in VOGAIS_DOSVOX:
            self._append_buffer_units(raw_name[:-1], units, perc * 0.9)
            self._append_buffer_units("$" + last_char, units, perc)
            return
        if raw_name.endswith("CIRC") and len(raw_name) > 6:
            self._append_buffer_units(raw_name[:-5], units, perc * 0.9)
            self._append_buffer_units("$" + raw_name[-5:], units, perc)
            return
        if raw_name.endswith("TIL"):
            base_name = raw_name[:-3]
            if not base_name:
                return
            vogal = base_name[-1].upper()
            if vogal in ("I", "U"):
                self._append_buffer_units(base_name, units, perc * 0.9)
            else:
                self._append_buffer_units(base_name + "CIRC", units, perc * 0.9)
            self._append_buffer_units("$NN", units, 0.9)

    def _append_carrega_fala_units(self, syllable, units, perc=1.0):
        if not syllable:
            return
        nomearq = "$"
        for ch in syllable:
            if ch == "^":
                self._append_buffer_units(nomearq + "CIRC", units, perc)
                nomearq = "$"
            elif ch == "~":
                self._append_buffer_units(nomearq + "TIL", units, perc)
                nomearq = "$"
            else:
                nomearq += ch.lower()
        if nomearq != "$":
            self._append_buffer_units(nomearq, units, perc)

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
            if len(syllable) > 2 and syllable[-2].upper() in VOGAIS_DOSVOX:
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
        return units

    def units_from_text(self, text, pause_scale=1.0, symbol_level=300):
        units = []
        word_pause = 0.035 * pause_scale
        punctuation_pause = 0.08 * pause_scale
        for kind, token in preprocess_text(text, symbol_level=symbol_level):
            if kind == "pause":
                units.append(("__SIL__", punctuation_pause))
                continue
            if kind == "character":
                units.extend(self.units_from_character(token))
                continue
            if kind == "symbol":
                direct_pcm = self._get_direct_character_sound(token)
                if direct_pcm:
                    units.append(("__PCM__", direct_pcm))
                else:
                    mapped = TYPED_SYMBOL_NAMES.get(token) or SYMBOL_WORDS.get(token, token)
                    units.extend(self.units_from_text(mapped, pause_scale=1.0, symbol_level=0))
                units.append(("__SIL__", punctuation_pause))
                continue
            token = PRONUNCIATION_OVERRIDES.get(token.lower(), token)
            if kind == "numberWord":
                direct_pcm = self._get_direct_word_sound(token)
                if direct_pcm:
                    units.append(("__PCM__", direct_pcm))
                    units.append(("__SIL__", word_pause))
                    continue
            ph = self._phonetize_word(token)
            units.extend(self.map_phonemes_to_units(ph))
            units.append(("__SIL__", word_pause))
        return units

    def _phonetize_word(self, token):
        key = token.lower()
        cached = self._phoneme_cache.get(key)
        if cached is not None:
            return cached
        ph = self.g2p.phonetize_word(token)
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
        if character.isalpha() and character.upper() == character and character.lower() != character:
            spoken = "maiuscula " + spoken
        return self.units_from_text(spoken, pause_scale=1.0)

    def synthesize_text(self, text, rate=50, pitch=50, volume=100, pause_scale=1.0, symbol_level=300):
        cache_key = (text, float(pause_scale), int(symbol_level))
        pcm = self._get_cached_pcm(self._text_pcm_cache, cache_key)
        if pcm is None:
            units = self.units_from_text(text, pause_scale=pause_scale, symbol_level=symbol_level)
            pcm = self._put_cached_pcm(self._text_pcm_cache, cache_key, self.engine.synthesize(units))
        pcm = apply_pitch_to_pcm(pcm, pitch)
        pcm = apply_speed_to_pcm(pcm, rate_to_speed(rate))
        pcm = apply_volume_to_pcm(pcm, volume)
        return pcm

    def synthesize_character(self, character, rate=50, pitch=50, volume=100):
        cache_key = character
        pcm = self._get_cached_pcm(self._character_pcm_cache, cache_key)
        if pcm is not None:
            pcm = apply_pitch_to_pcm(pcm, pitch)
            pcm = apply_speed_to_pcm(pcm, rate_to_speed(rate))
            pcm = apply_volume_to_pcm(pcm, volume)
            return pcm
        direct_pcm = self._get_direct_character_sound(character)
        if direct_pcm:
            return apply_volume_to_pcm(direct_pcm, volume)
        units = self.units_from_character(character)
        pcm = self._put_cached_pcm(self._character_pcm_cache, cache_key, self.engine.synthesize(units))
        pcm = apply_pitch_to_pcm(pcm, pitch)
        pcm = apply_speed_to_pcm(pcm, rate_to_speed(rate))
        pcm = apply_volume_to_pcm(pcm, volume)
        return pcm


def get_available_voice_variants(module_dir):
    data_dir = os.path.join(module_dir, VOICE_DIR_NAME)
    if not os.path.isdir(data_dir):
        return {}
    variants = {}
    labels = {
        "novodifo": "Novo difo",
        "Difones": "Difones",
        "Difones2": "Difones 2",
        "Difones3": "Difones 3",
        "difones5": "Difones 5",
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
