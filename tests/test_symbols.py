import sys
from pathlib import Path


DRIVER_DIR = Path(__file__).resolve().parents[1] / "synthDrivers"
sys.path.insert(0, str(DRIVER_DIR))

from dosvox_native_core import (  # noqa: E402
    DosvoxNativeSynth,
    preprocess_text,
    resolve_named_key,
    split_source_symbols,
)


def _build_fake_synth():
    synth = DosvoxNativeSynth.__new__(DosvoxNativeSynth)
    synth._get_direct_word_sound = lambda word: b"number recording"
    synth._get_direct_character_sound = lambda char: b"symbol recording"
    synth._phonetize_word = lambda word: word
    synth.map_phonemes_to_units = lambda word: [("VOICE:" + word, 1.0)]
    return synth


def test_written_symbol_names_remain_words():
    assert preprocess_text("ponto uma hora") == [
        ("word", "ponto"),
        ("word", "uma"),
        ("word", "hora"),
    ]

    units = _build_fake_synth().units_from_text("ponto uma hora")

    assert ("VOICE:ponto", 1.0) in units
    assert ("VOICE:uma", 1.0) in units
    assert ("VOICE:hora", 1.0) in units
    assert not any(kind == "__PCM__" for kind, _ in units)


def test_real_numbers_and_symbols_can_still_use_recordings():
    number_units = _build_fake_synth().units_from_text("1")
    symbol_units = _build_fake_synth().units_from_text(".")

    assert ("__PCM__", b"number recording") in number_units
    assert ("__PCM__", b"symbol recording") in symbol_units


def test_source_symbols_are_marked_without_confusing_written_names():
    assert split_source_symbols("palavra ponto e .", symbol_level=100) == [
        ("text", "palavra ponto e "),
        ("symbol", "."),
    ]
    assert split_source_symbols("ponto", symbol_level=100) == [("text", "ponto")]
    assert split_source_symbols(".", symbol_level=0) == [("text", ".")]


def test_nvda_pt_br_spelling_names_resolve_to_real_symbols():
    names = {
        "ponto": ".",
        "vírgula": ",",
        "número": "#",
        "abre chave": "{",
        "fecha chave": "}",
        "abre colchete": "[",
        "fecha colchete": "]",
        "til": "~",
        "barra invertida": "\\",
        "barra vertical": "|",
        "exclamação": "!",
        "arroba": "@",
        "cifrão": "$",
        "porcento": "%",
        "trema": "¨",
        "eh comercial": "&",
        "asterisco": "*",
        "abre parêntesis": "(",
        "fecha parêntesis": ")",
        "hífen": "-",
        "sublinha": "_",
        "mais": "+",
        "igual": "=",
        "apóstrofo": "'",
        "dois pontos": ":",
        "ponto e vírgula": ";",
        "interrogação": "?",
        "circunflexo": "^",
        "maior que": ">",
        "menor que": "<",
    }
    for name, character in names.items():
        assert resolve_named_key(name) == ("character", character)


def test_all_reported_symbols_have_dedicated_recordings():
    synth = DosvoxNativeSynth(str(DRIVER_DIR), "Difones2")
    symbols = ".,#{ }[]~\\|!@$%\u00a8&*()-_+=\'`:;?^></".replace(" ", "")
    missing = [symbol for symbol in symbols if not synth._get_direct_character_sound(symbol)]
    assert missing == []
