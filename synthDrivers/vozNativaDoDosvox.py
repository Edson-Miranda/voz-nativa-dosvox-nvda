# -*- coding: UTF-8 -*-
import addonHandler
import config
import logHandler
import os
import queue
import re
import threading
import unicodedata

import nvwave
import synthDriverHandler
from autoSettingsUtils.driverSetting import BooleanDriverSetting, DriverSetting
from speech.commands import BreakCommand, CallbackCommand, CharacterModeCommand, IndexCommand, SynthCommand
from speech.extensions import filter_speechSequence

addonHandler.initTranslation()
log = logHandler.log
# Renova o objeto de audio a cada N trechos falados, so em leituras
# continuas longas (ver _run), como mitigacao para as pausas que crescem
# aos poucos ao longo de muitos minutos de leitura sem parar.
RENOVAR_PLAYER_A_CADA = 40

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

def split_source_symbols(text, symbol_level=300):
    """Split real source symbols from text before NVDA expands their names."""
    parts = []
    text_buffer = []
    source_text = str(text or "")
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
    text = reconstruct_numeric_separators(text)
    text = reconstruct_domain_dots(text)
    text = reconstruct_reais(text)
    combined_re = re.compile(
        "(?:" + _ELLIPSIS_RE.pattern + ")|(?:" + _ELLIPSIS_WORD_RE.pattern + ")",
        re.IGNORECASE | re.UNICODE,
    )
    parts = []
    pos = 0
    for match in combined_re.finditer(text):
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


def _juntar_palavras_divididas_pelo_nvda(speech_sequence):
    resultado = []
    i = 0
    total = len(speech_sequence)
    while i < total:
        item = speech_sequence[i]
        eh_sigla = (
            isinstance(item, str)
            and len(item) >= 2
            and item.isalpha()
            and item.isupper()
        )
        if eh_sigla and i + 1 < total:
            proximo = speech_sequence[i + 1]
            if isinstance(proximo, str) and _SUFIXO_MINUSCULO_CURTO_RE.match(proximo):
                resultado.append(item + proximo)
                i += 2
                continue
        resultado.append(item)
        i += 1
    return resultado


# Segunda camada de protecao para o sinal de menos: se o NVDA entregar o
# hifen (ou a palavra substituta -- traco/hifen/menos) como um ITEM
# SEPARADO da lista, antes mesmo do texto virar uma string so, a
# reconstrucao textual do nucleo (que so olha dentro de uma string) nunca
# chega a ver os dois juntos. Aqui a juncao acontece direto na lista
# bruta: um item que e exatamente "-" (ou uma dessas palavras, sozinha),
# seguido imediatamente por um item que comeca com digito, vira um unico
# item colado, sem espaco, pronto para o reconhecimento de sinal de menos
# que ja existe no nucleo pegar corretamente.
_PALAVRAS_HIFEN = {"-", "traco", "traço", "hifen", "hífen", "menos"}


def _juntar_hifen_com_numero(speech_sequence):
    resultado = []
    i = 0
    total = len(speech_sequence)
    while i < total:
        item = speech_sequence[i]
        eh_hifen = isinstance(item, str) and item.strip().lower() in _PALAVRAS_HIFEN
        if eh_hifen and i + 1 < total:
            proximo = speech_sequence[i + 1]
            if isinstance(proximo, str) and proximo[:1].isdigit():
                resultado.append("-" + proximo)
                i += 2
                continue
        resultado.append(item)
        i += 1
    return resultado


# O motor de fonetica ja reduz qualquer palavra para minusculo antes de
# aplicar as regras (a unica letra que fica maiuscula por dentro e
# calculada pela propria marcacao de tonica, nunca herdada do texto de
# entrada) -- entao normalizar a caixa do texto aqui nao tem como estragar
# nenhuma regra fonetica. Isso e uma rede de seguranca mais ampla que a
# juncao acima: quando o NVDA fragmenta uma palavra por transicao de
# maiuscula para minuscula (pensado para identificadores de codigo, tipo
# "minhaVariavel"), pode sobrar um pedaco de caixa mista esquisito -- por
# exemplo "Fs" dentro de "PDFs" -- que soa errado se processado como se
# fosse uma palavra normal. Palavras totalmente minusculas ou totalmente
# maiusculas ficam como estao; so a mistura genuina (um pedaco com as duas
# caixas juntas) e normalizada para minuscula.
_LETRAS_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")


def _normalizar_fragmentos_de_caixa_mista(texto):
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
    # Quem persiste somos nos, sobrescrevendo saveSettings e loadSettings mais
    # abaixo: tudo vai para o dosvox.ini, que passa a ser a unica memoria do
    # complemento.
    #
    # (useConfig existe desde sempre em DriverSetting, e o NVDA passou a
    # respeita-lo corretamente em sintetizadores a partir do 2023.1.)
    supportedSettings = [
        # ATENCAO: NAO use SynthDriver.VariantSetting() aqui.
        #
        # As fabricas do NVDA (VoiceSetting, VariantSetting, RateSetting...) sao
        # classmethods SEM PARAMETRO NENHUM -- todos os drivers do proprio NVDA
        # as chamam vazias. Passar useConfig=False para elas levanta um
        # TypeError no CORPO DA CLASSE, o modulo inteiro deixa de importar, e o
        # sintomas sao exatamente estes: o sintetizador some da lista e a janela
        # de sintetizadores toca o som de erro.
        #
        # Para ter useConfig=False na variante, monta-se a DriverSetting a mao.
        # E' o mesmo objeto que a fabrica devolveria, com o id "variant", que e'
        # o que liga a caixa de selecao aos metodos _get_variant/_set_variant e
        # a lista availableVariants.
        DriverSetting(
            "variant",
            _("V&ariante (banco de difones)"),
            availableInSettingsRing=True,
            defaultVal=DIFONES_PADRAO,
            displayName=_("Variante"),
            useConfig=False,
        ),
        # Opcoes booleanas cabem naturalmente no painel de voz do NVDA.
        #
        # Os parametros numericos do mecanismo (INTERPAL, CORTEFON, SOBRAFON
        # e pausas) NAO sao declarados como NumericDriverSetting: no NVDA essa
        # classe e representada por um slider, que e inadequado para valores
        # exatos em amostras/milisegundos. Eles continuam sendo lidos do
        # dosvox.ini, mas ficam deliberadamente fora deste painel.
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

    def __init__(self):
        self._voice = "dosvoxNative"
        self._queue = queue.Queue()
        self._cancel_event = threading.Event()
        self._state_lock = threading.RLock()
        self._generation = 0
        self._player_lock = threading.RLock()
        # Contador de trechos falados desde a ultima renovacao do objeto
        # de audio. Em leituras continuas muito longas, o player pode
        # acumular algum estado interno do proprio NVDA que faz as pausas
        # entre trechos crescerem aos poucos -- renovar o player de vez em
        # quando, sempre entre um trecho e outro (nunca cortando uma fala
        # no meio), evita esse acumulo sem risco de engasgo audivel.
        self._trechos_desde_renovacao_player = 0
        # A sessao nasce lendo (ou criando) o dosvox.ini, escolhendo o banco de
        # difones e aplicando os tres ajustes de voz. Depois disto o driver nao
        # sabe mais nada sobre nada disso: so pede PCM e pergunta a taxa.
        self._sample_rate = None
        self._player = None
        self._sessao = SessaoDosvox(MODULE_DIR)
        if self._sessao.criou_o_ini:
            log.info("vozNativaDoDosvox: dosvox.ini criado ou migrado em %s"
                     % self._sessao.caminho_ini)
        self._output_device = self._get_configured_output_device()
        self._player = self._create_player(self._output_device)
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        filter_speechSequence.register(self._preserve_source_symbols)

    def _preserve_source_symbols(self, speech_sequence):
        """Mark real symbols while they still differ from written names."""
        speech_sequence = _juntar_palavras_divididas_pelo_nvda(speech_sequence)
        speech_sequence = _juntar_hifen_com_numero(speech_sequence)
        try:
            symbol_level = int(config.conf["speech"]["symbolLevel"])
        except Exception:
            symbol_level = 300
        marked = []
        character_mode = False
        total = len(speech_sequence)
        for index, item in enumerate(speech_sequence):
            if item.__class__.__name__ == "CharacterModeCommand":
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
            # manda o NOME dele, ja traduzido -- "." vira "ponto", "-" vira
            # "hifen". Este filtro precisa reconhecer esse nome e devolver o
            # caractere, para que a voz toque a GRAVACAO em vez de sintetizar a
            # palavra. O unico sinal que o NVDA da e' que o nome vem seguido de
            # um EndUtteranceCommand.
            #
            # SO QUE ISSO NAO BASTA, e era um bug.
            #
            # A condicao antiga era "e' o ultimo texto antes do fim da
            # elocucao". Mas o NVDA parte uma linha em varios pedacos de texto
            # sempre que a formatacao muda -- negrito, link, italico. Se a
            # palavra que calha de ser o nome de um simbolo cair no FIM da
            # linha, ela era trocada pela gravacao:
            #
            #     ["o ", "hifen"]          -> falava o traco, nao a palavra
            #     ["Isso e um ", "ponto"]  -> falava o ponto, nao a palavra
            #
            # E sao 26 palavras comuns do portugues que estao nessa tabela:
            # ponto, virgula, hifen, barra, aspas, arroba, til, crase, mais,
            # menos, igual, asterisco, cifrao, porcentagem, espaco...
            #
            # A regra certa e' a que o Dosvox precisa e nada alem dela: so
            # troque se a palavra for TODO o texto da elocucao. Uma soletracao
            # de simbolo e' exatamente isso -- a elocucao inteira e' o nome, e
            # mais nada. Uma frase que por acaso termina em "hifen" tem outro
            # texto antes, e agora e' falada como texto.
            e_todo_o_texto_da_elocucao = (
                sum(1 for outro in speech_sequence if isinstance(outro, str)) == 1
            )
            next_is_spelling_end = (
                index + 1 < total
                and speech_sequence[index + 1].__class__.__name__ == "EndUtteranceCommand"
            )
            if (
                e_todo_o_texto_da_elocucao
                and next_is_spelling_end
                and item.strip() == item
                and not _esta_entre_aspas(speech_sequence, index, total)
            ):
                resolved = resolve_named_key(item)
                if resolved is not None and resolved[0] == "character":
                    log.debug("vozNativaDoDosvox: %r -> gravacao de %r (soletracao)"
                              % (item, resolved[1]))
                    marked.append(DosvoxSourceSymbolCommand(resolved[1]))
                    continue
            item = _normalizar_fragmentos_de_caixa_mista(item)
            # A pausa das reticencias vem da sessao, e nao mais de uma global.
            for word_kind, word_value in split_literal_symbols(item, self._sessao.pausas.ponto):
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

    def _get_availableVoices(self):
        return {
            voice_id: synthDriverHandler.VoiceInfo(voice_id, label)
            for voice_id, label in get_available_voices(MODULE_DIR).items()
        }

    def _get_voice(self):
        return self._voice

    def _set_voice(self, value):
        if value in self.availableVoices:
            self._voice = value

    def _get_availableVariants(self):
        return {
            variant_id: synthDriverHandler.VoiceInfo(variant_id, label)
            for variant_id, label in get_available_voice_variants(MODULE_DIR).items()
        }

    def _get_variant(self):
        return self._sessao.difones

    def _set_variant(self, value):
        self._sessao.definir_difones(value)

    def _get_cortafala(self):
        return self._sessao.cortafala

    def _set_cortafala(self, value):
        self._sessao.definir_cortafala(value)

    def _get_rapidinho(self):
        return self._sessao.rapidinho

    def _set_rapidinho(self, value):
        # O rapidinho nao mexe nas amostras: muda a TAXA em que elas sao tocadas
        # (11025 -> 16537 Hz), como o wavePlay do Pascal. A sessao avisa quando
        # a taxa mudou; so entao o dispositivo de audio precisa ser reaberto.
        if self._sessao.definir_rapidinho(value):
            self._renovar_player_por_taxa()

    def _get_acelerarLetras(self):
        return self._sessao.letras_rapidas

    def _set_acelerarLetras(self, value):
        self._sessao.definir_letras_rapidas(value)

    def _get_reduzirVolume(self):
        return self._sessao.reduzir_volume

    def _set_reduzirVolume(self, value):
        self._sessao.definir_reduzir_volume(value)

    def _get_interpal(self):
        return self._sessao.interpal

    def _set_interpal(self, value):
        self._sessao.definir_interpal(value)

    def _get_cortefon(self):
        return self._sessao.cortefon

    def _set_cortefon(self, value):
        self._sessao.definir_cortefon(value)

    def _get_sobrafon(self):
        return self._sessao.sobrafon

    def _set_sobrafon(self, value):
        self._sessao.definir_sobrafon(value)

    def _get_pausaPonto(self):
        return self._sessao.pausa_ponto

    def _set_pausaPonto(self, value):
        self._sessao.definir_pausa_ponto(value)

    def _get_pausaVirgula(self):
        return self._sessao.pausa_virgula

    def _set_pausaVirgula(self, value):
        self._sessao.definir_pausa_virgula(value)

    def _get_pausaDoisPontos(self):
        return self._sessao.pausa_dois_pontos

    def _set_pausaDoisPontos(self, value):
        self._sessao.definir_pausa_dois_pontos(value)

    def loadSettings(self, onlyChanged=False):
        # O NVDA chama isto ao carregar o sintetizador e ao trocar de perfil. A
        # classe base leria do nvda.ini; nos lemos do dosvox.ini. Como as quatro
        # opcoes tem useConfig=False, nao ha nada no nvda.ini para ler, e nao
        # chamamos super() de proposito (em versoes do NVDA anteriores a 2023.1,
        # super() ainda tentaria ler essas opcoes do nvda.ini e falharia).
        if self._sessao.recarregar(forcar=True):
            self._renovar_player_por_taxa()
        # POReM: a loadSettings da classe base nao serve so para ler o nvda.ini.
        # E' de dentro dela que o NVDA chama changeVoice(), e e' changeVoice()
        # que reconstroi o anel de configuracoes para o sintetizador ATUAL (o
        # updateSupportedSettings do synthSettingsRing), alem de carregar o
        # dicionario de voz e disparar a notificacao synthChanged. Ao pular
        # super() sem repor essa chamada, o anel nunca era reconstruido para
        # este driver:
        #   - ao TROCAR de outro sintetizador para este, o anel continuava
        #     mostrando as definicoes do sintetizador anterior (ainda validas na
        #     memoria do anel, por isso nenhum erro -- so as definicoes erradas);
        #   - ao INICIAR o NVDA ja com este sintetizador ativo, nao havia anel
        #     anterior nenhum, entao navegar pelas definicoes lancava um erro no
        #     log e nada acontecia.
        # Repor changeVoice() aqui e' exatamente o que a base faria pela voz, sem
        # tocar no nvda.ini. self.voice e' sempre uma voz valida (definida no
        # __init__ e filtrada por _set_voice), entao isto nao levanta o
        # LookupError que a base trata para vozes invalidas; ainda assim,
        # protegemos a chamada para que uma falha inesperada nunca impeca o
        # sintetizador de carregar.
        try:
            synthDriverHandler.changeVoice(self, self.voice)
        except Exception:
            log.error(
                "vozNativaDoDosvox: erro ao reconstruir o anel de configuracoes",
                exc_info=True,
            )

    def saveSettings(self):
        # O NVDA chama isto ao confirmar o painel e ao salvar a configuracao. A
        # sessao ja grava a cada mudanca, entao aqui nao ha nada a fazer -- mas o
        # metodo precisa existir e nao pode chamar super(), que escreveria no
        # nvda.ini.
        pass

    def _recarregar_dosvox_ini_se_mudou(self):
        # Chamado no comeco de cada fala. Quando nada mudou, e' so um
        # os.path.getmtime. E' isto que faz uma edicao do dosvox.ini no Bloco de
        # Notas valer na fala seguinte, sem reiniciar o NVDA.
        if self._sessao.recarregar():
            self._renovar_player_por_taxa()

    def _get_configured_output_device(self):
        try:
            return config.conf["audio"]["outputDevice"]
        except Exception:
            pass
        try:
            return config.conf["speech"]["outputDevice"]
        except Exception:
            return None

    def _create_player(self, output_device):
        # A taxa vem do motor: 11025 Hz, ou 16537 Hz com o rapidinho ligado.
        # E' assim que o Dosvox acelera a fala -- tocando as mesmas amostras
        # mais depressa, sem tocar no audio.
        self._sample_rate = self._sessao.taxa_saida
        kwargs = {
            "channels": 1,
            "samplesPerSec": self._sample_rate,
            "bitsPerSample": 16,
            "buffered": True,
        }
        if output_device is not None:
            kwargs["outputDevice"] = output_device
        try:
            return nvwave.WavePlayer(**kwargs)
        except TypeError:
            kwargs.pop("buffered", None)
            return nvwave.WavePlayer(**kwargs)

    def _stop_player_instance(self, player):
        try:
            player.stop()
        except Exception:
            pass

    def _stop_player_async(self, player):
        threading.Thread(target=self._stop_player_instance, args=(player,), daemon=True).start()

    def _reset_player_for_interrupt(self):
        # ESTE E' O CAMINHO CRITICO DA DIGITACAO.
        #
        # O NVDA chama cancel() antes de praticamente toda fala nova -- e, ao
        # digitar, isso e' UMA VEZ POR TECLA. Antes, cancel() construia um
        # nvwave.WavePlayer NOVO toda vez, o que significa abrir um dispositivo
        # de audio do sistema (WASAPI) do zero, de forma sincrona, na thread que
        # o NVDA usa para falar. Abrir um dispositivo custa ordens de grandeza
        # mais que sintetizar o caractere, e era isso, e nao a sintese, que
        # fazia o teclado parecer pesado: entre bater a tecla e ouvir o som,
        # esperava-se a abertura de um dispositivo de audio.
        #
        # O jeito normal de interromper e' player.stop(), que e' exatamente para
        # isso: descarta o que estava na fila e deixa o mesmo objeto pronto para
        # receber audio novo. Trocar o objeto so faz sentido quando ele nao
        # serve mais -- ou seja, quando o dispositivo de saida mudou, ou quando
        # a taxa mudou (rapidinho). Fora esses dois casos, reaproveitamos.
        output_device = self._get_configured_output_device()
        precisa_trocar = (
            output_device != self._output_device
            or self._sample_rate != self._sessao.taxa_saida
        )
        if not precisa_trocar:
            self._stop_player()
            return

        try:
            new_player = self._create_player(output_device)
        except Exception:
            with self._player_lock:
                old_player = self._player
            self._stop_player_instance(old_player)
            return
        with self._player_lock:
            old_player = self._player
            self._player = new_player
            self._output_device = output_device
        self._stop_player_async(old_player)

    def _stop_player(self):
        with self._player_lock:
            player = self._player
        self._stop_player_instance(player)

    def _discard_pending_speech(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _interrupt_current_speech(self):
        with self._state_lock:
            self._generation += 1
            self._cancel_event.set()
        self._discard_pending_speech()
        self._reset_player_for_interrupt()

    def _queue_speech(self, segments):
        with self._state_lock:
            self._cancel_event.clear()
            generation = self._generation
        self._queue.put((segments, generation))

    def _is_cancelled(self, generation):
        with self._state_lock:
            return self._cancel_event.is_set() or generation != self._generation

    def _synthesize_pcm_chunks(self, segment_type, value, symbol_level):
        if segment_type == "pause":
            yield self._sessao.silencio(value)
            return
        if segment_type == "character":
            # O NVDA ja classificou este item como caractere/tecla. Tenta primeiro
            # o caminho de caractere RESOLVIDO do Kotlin: ele nao reaplica trim
            # nem sanitizacao e, por isso, preserva o espaco literal (" ") e sua
            # gravacao _32.WAV. Se nao houver gravacao direta, usa o caminho
            # normal de caractere como fallback.
            caractere = resolver_caractere(value)
            pcm = self._sessao.falar_caractere_resolvido(caractere)
            if pcm is None:
                pcm = self._sessao.falar_caractere(caractere)
            if pcm:
                yield pcm
            return

        # Mantem o mesmo fatiamento de SessaoDosvox usado pelo servico Kotlin:
        # nunca corta palavra ao meio e prefere uma pontuacao natural. Cada
        # trecho entra INTEIRO no streaming do motor; dentro dele, as fronteiras
        # do Cortafala sao apenas as do proprio mecanismo (sem flush por palavra).
        for text_chunk in self._sessao.trechos(value):
            yield from self._sessao.falar_em_fluxo(text_chunk, symbol_level=symbol_level)

    def _notify_done(self):
        try:
            synthDriverHandler.synthDoneSpeaking.notify(synth=self)
        except Exception:
            pass

    @staticmethod
    def _converter_pcm_para_saida(pcm, reduzir=False):
        # Mesmo caminho do Android/Kotlin: o DOSVOX produz PCM unsigned de 8 bits,
        # mas a saida recebe PCM signed de 16 bits little-endian. Sem reducao, o
        # deslocamento de 8 bits e sem perda; com REDUZIRVOLUME, a conta e feita
        # em 16 bits e truncada em direcao a zero, exatamente como Kotlin/Java.
        if not pcm:
            return pcm
        out = bytearray(len(pcm) * 2)
        j = 0
        if reduzir:
            for sample in pcm:
                amplitude = int((((sample - 128) << 8) * 2) / 5)
                valor = amplitude & 0xFFFF
                out[j] = valor & 0xFF
                out[j + 1] = (valor >> 8) & 0xFF
                j += 2
        else:
            for sample in pcm:
                amplitude = (sample - 128) << 8
                valor = amplitude & 0xFFFF
                out[j] = valor & 0xFF
                out[j + 1] = (valor >> 8) & 0xFF
                j += 2
        return bytes(out)

    def _feed_pcm(self, pcm, generation, on_done=None):
        if not pcm:
            if on_done:
                on_done()
            return True
        if self._is_cancelled(generation):
            return False
        self._sync_output_device()
        with self._player_lock:
            player = self._player
        if self._is_cancelled(generation):
            return False
        pcm = self._converter_pcm_para_saida(pcm, self._sessao.reduzir_volume)
        try:
            player.feed(pcm, onDone=on_done)
        except TypeError:
            # Versoes antigas do NVDA nao aceitam onDone; sem ele, o NVDA
            # nao tem como saber quando o audio realmente terminou de
            # tocar, entao avisamos na hora, como antes (comportamento
            # antigo, sujeito ao mesmo bug de leitura continua).
            player.feed(pcm)
            if on_done:
                on_done()
        except Exception:
            return False
        return not self._is_cancelled(generation)

    def _renovar_player_por_taxa(self):
        # O tocador e' aberto com uma taxa fixa; ligar ou desligar o rapidinho
        # muda essa taxa (11025 <-> 16537 Hz), entao ele precisa ser reaberto.
        # cancel() ja faz exatamente isso -- _reset_player_for_interrupt cria um
        # tocador novo, e _create_player le a taxa atual do motor --, alem de
        # interromper a fala em curso, que e' o esperado ao mexer numa
        # configuracao de voz.
        if self._player is None or self._sample_rate == self._sessao.taxa_saida:
            # Durante a construcao ainda nao ha tocador; ele ja vai nascer na
            # taxa certa, porque _create_player le a taxa do motor.
            return
        self.cancel()

    def _renovar_player_sem_interromper(self):
        # So e chamado depois que o trecho atual ja terminou de tocar (ver
        # _run), entao trocar o player aqui nao corta nem engasga nada --
        # e so a mesma troca que ja fazemos ao mudar de dispositivo de
        # saida, so que por iniciativa propria, para evitar acumulo de
        # estado interno em leituras continuas muito longas.
        try:
            novo_player = self._create_player(self._output_device)
        except Exception:
            return
        with self._player_lock:
            player_antigo = self._player
            self._player = novo_player
        self._stop_player_async(player_antigo)

    def _sync_output_device(self):
        output_device = self._get_configured_output_device()
        if output_device == self._output_device:
            return
        with self._player_lock:
            if output_device == self._output_device:
                return
            try:
                self._player.stop()
            except Exception:
                pass
            self._player = self._create_player(output_device)
            self._output_device = output_device
            log.debug("vozNativaDoDosvox outputDevice=%r", output_device)

    def speakCharacter(self, character, index=None):
        resolved = resolve_named_key(character.strip()) if isinstance(character, str) else None
        if resolved is not None:
            kind, value = resolved
            if kind == "character":
                segments = [("character", value)]
                if index is not None:
                    segments.append(("index", index))
                self._queue_speech(segments)
                return
            if kind == "fkey":
                segments = [("character", "F")]
                segments.extend(("character", digit) for digit in value)
                if index is not None:
                    segments.append(("index", index))
                self._queue_speech(segments)
                return
        segments = [("character", character)]
        if index is not None:
            segments.append(("index", index))
        self._queue_speech(segments)





    def _rewrite_short_sequences(self, segments):
        # Ordinary speech has no reliable metadata saying whether a written
        # symbol name originated from punctuation, so other text is retained.
        return segments

    def _append_special_segments(self, segments, text, e_todo_o_texto):
        # A ajuda de teclado do NVDA manda o nome da tecla como texto seguido de
        # DOIS ESPACOS (por exemplo "a  "), sem CharacterModeCommand. E' o unico
        # sinal que ela da, e e' por isso que este metodo existe.
        #
        # O PROBLEMA: dois espacos no fim nao sao exclusividade da ajuda de
        # teclado. O NVDA separa com espaco os trechos de um texto formatado
        # (negrito, link, italico), e um trecho pode facilmente chegar aqui como
        # "hifen  ". Quando isso acontecia, a palavra virava a GRAVACAO do traco.
        #
        # A regra e' a mesma do _preserve_source_symbols, e agora vale em TODOS
        # os caminhos: so troque uma palavra pela gravacao se ela for TODO o
        # texto da elocucao. O nome de uma tecla, na ajuda de teclado, e'
        # exatamente isso. Uma palavra no meio de uma frase, nunca.
        if e_todo_o_texto and isinstance(text, str) and text.endswith("  "):
            stripped = text.strip()
            resolved = resolve_named_key(stripped) if stripped else None
            if resolved is not None:
                kind, value = resolved
                if kind == "character":
                    log.debug("vozNativaDoDosvox: %r -> gravacao de %r (ajuda de teclado)"
                              % (text, value))
                    segments.append(("character", value))
                    return
                if kind == "fkey":
                    segments.append(("character", "F"))
                    segments.extend(("character", digit) for digit in value)
                    return
        segments.append(("text", text))

    def speak(self, speechSequence):
        segments = []
        character_mode = False
        # Quantos itens de TEXTO esta elocucao tem. Uma palavra so pode virar a
        # gravacao de um simbolo se for o texto inteiro -- ver
        # _append_special_segments e _preserve_source_symbols.
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

            class_name = item.__class__.__name__
            if class_name == "DosvoxSourceSymbolCommand":
                segments.append(("character", item.character))
            elif class_name == "BreakCommand":
                # Pausa de verdade, inserida exatamente aqui na sequencia,
                # nao acumulada para o final (isso quebrava a posicao de
                # toda pausa, inclusive a dos parenteses).
                time_ms = max(0, int(getattr(item, "time", 0)))
                if time_ms:
                    segments.append(("pause", time_ms / 1000.0))
            elif class_name == "IndexCommand":
                # Fica intercalado na mesma sequencia dos segmentos de fala,
                # para o retorno de chamada do audio disparar o indice no
                # ponto certo, e nao todos de uma vez no comeco da fala.
                segments.append(("index", getattr(item, "index", None)))
            elif isinstance(item, CallbackCommand):
                # A leitura continua do NVDA (NVDA+A) usa isso para saber
                # quando pode buscar e falar o proximo trecho: precisa ser
                # chamado exatamente quando o audio ate aqui de fato
                # terminou de tocar, nunca antes.
                segments.append(("callback", item))
            elif class_name == "CharacterModeCommand":
                character_mode = bool(
                    getattr(item, "state", getattr(item, "enable", getattr(item, "enabled", False)))
                )
        segments = self._rewrite_short_sequences(segments)
        has_real_content = any(value for kind, value in segments if kind not in ("index", "callback"))
        has_sync_markers = any(kind in ("index", "callback") for kind, value in segments)
        if not segments or (not has_real_content and not has_sync_markers):
            self._notify_done()
            return
        self._queue_speech(segments)

    def cancel(self):
        self._interrupt_current_speech()
        self._sessao.comecar_elocucao()
        self._trechos_desde_renovacao_player = 0
        self._notify_done()

    def pause(self, switch):
        with self._player_lock:
            if hasattr(self._player, "pause"):
                self._player.pause(switch)

    def terminate(self):
        try:
            filter_speechSequence.unregister(self._preserve_source_symbols)
        except Exception:
            pass
        with self._state_lock:
            self._generation += 1
            self._cancel_event.set()
        self._queue.put(None)
        self._reset_player_for_interrupt()

    def _fire_events(self, events):
        for kind, value in events:
            if kind == "index":
                if value is not None:
                    try:
                        synthDriverHandler.synthIndexReached.notify(synth=self, index=value)
                    except Exception:
                        pass
            elif kind == "callback":
                # CallbackCommand: e assim que a leitura continua do NVDA
                # (NVDA+A) sabe que pode buscar e falar o proximo trecho.
                try:
                    if hasattr(value, "run"):
                        value.run()
                    elif callable(getattr(value, "callback", None)):
                        value.callback()
                except Exception:
                    log.error("vozNativaDoDosvox: erro executando CallbackCommand", exc_info=True)

    def _make_chunk_callback(self, chunk_events):
        def _callback():
            self._fire_events(chunk_events)
        return _callback

    def _wait_for_playback_completion(self):
        # player.sync() bloqueia ate o audio ja entregue realmente terminar
        # de tocar, e nesse meio tempo garante que os retornos de chamada
        # pendentes (onDone) sejam disparados. Rodar isso aqui, na propria
        # thread de trabalho, e mais confiavel do que depender so do
        # retorno de chamada do ultimo pedaco, que pode nao disparar em
        # certos casos (por exemplo, um pedaco so de silencio).
        with self._player_lock:
            player = self._player
        try:
            if hasattr(player, "sync"):
                player.sync()
        except Exception:
            pass

    def _run(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            segments, generation = item
            if self._is_cancelled(generation):
                continue
            # sintetiza (dvwin.pas) comeca sempre com "ultLetra := ' '" e
            # "nrepUlt := 0": o contador do clique vale por elocucao. Sem este
            # reset, uma linha terminada em virgula somava com a seguinte.
            self._sessao.comecar_elocucao()
            self._recarregar_dosvox_ini_se_mudou()
            try:
                try:
                    symbol_level = int(config.conf["speech"]["symbolLevel"])
                except Exception:
                    symbol_level = 300
                # Sintetiza tudo primeiro, guardando quais indices e
                # retornos de chamada (CallbackCommand, usado pela leitura
                # continua do NVDA+A) caem depois de qual pedaco de audio:
                # assim o retorno de chamada de cada pedaco dispara tudo no
                # ponto certo, nunca antes do audio ate ali realmente tocar.
                pcm_chunks = []
                pending_events = []
                for kind, value in segments:
                    if self._is_cancelled(generation):
                        break
                    if kind in ("index", "callback"):
                        pending_events.append((kind, value))
                        continue
                    for pcm in self._synthesize_pcm_chunks(kind, value, symbol_level):
                        if not pcm:
                            continue
                        pcm_chunks.append([pcm, pending_events])
                        pending_events = []
                if pending_events:
                    if pcm_chunks:
                        pcm_chunks[-1][1] = pcm_chunks[-1][1] + pending_events
                    else:
                        self._fire_events(pending_events)
                if self._is_cancelled(generation) or not pcm_chunks:
                    self._notify_done()
                    continue
                spoke = False
                for pcm, chunk_events in pcm_chunks:
                    if self._is_cancelled(generation):
                        break
                    on_done = self._make_chunk_callback(chunk_events)
                    if self._feed_pcm(pcm, generation, on_done):
                        spoke = True
                    else:
                        break
                if self._is_cancelled(generation):
                    # cancel()/terminate() ja avisam por conta propria.
                    continue
                if spoke:
                    self._wait_for_playback_completion()
                    self._trechos_desde_renovacao_player += 1
                    if self._trechos_desde_renovacao_player >= RENOVAR_PLAYER_A_CADA:
                        self._trechos_desde_renovacao_player = 0
                        self._renovar_player_sem_interromper()
                self._notify_done()
            except Exception:
                log.error("vozNativaDoDosvox: erro ao sintetizar fala", exc_info=True)
                self._notify_done()
