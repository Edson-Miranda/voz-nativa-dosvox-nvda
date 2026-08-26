import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from synthDrivers.dosvox_data.dosvox_native_core import (  # noqa: E402
    DosvoxNativeSynth,
    expand_numeric_token,
    get_available_voice_variants,
)


def _manifest_value(field):
    text = (ROOT / "manifest.ini").read_text(encoding="utf-8")
    match = re.search(rf"(?m)^{re.escape(field)}\s*=\s*[\"']?([^\"'\r\n]+)", text)
    assert match, field
    return match.group(1).strip()


def test_manifest_and_package_metadata():
    assert _manifest_value("name") == "vozNativaDoDosvox"
    assert _manifest_value("version") == "2.1.1"
    manifest = (ROOT / "manifest.ini").read_text(encoding="utf-8")
    assert "1993" in manifest
    assert "edson.demiranda.melo@gmail.com" in manifest


def test_voice_variants_and_data_layout():
    variants = get_available_voice_variants(str(ROOT / "synthDrivers"))
    assert set(variants) == {"Difones", "Difones2", "Difones3", "difones5", "novodifo"}
    assert variants["novodifo"] == "Novo difo"
    assert (ROOT / "synthDrivers" / "dosvox_data" / "dosvox_native_core.py").is_file()
    assert not (ROOT / "synthDrivers" / "dosvox_native_core.py").exists()


def test_number_expansion():
    assert expand_numeric_token("1993") == "mil e novecentos e noventa e tres"
    assert expand_numeric_token("0007") == "zero zero zero sete"


def test_recorded_ascii_symbols_and_space():
    synth = DosvoxNativeSynth(str(ROOT / "synthDrivers"), "Difones2")
    sample = " abcXYZ09.,;:!?@#%&*()[]{}+-=/\\"
    missing = [character for character in sample if not synth._get_direct_character_sound(character)]
    assert missing == []


def test_fast_letters_are_available():
    synth = DosvoxNativeSynth(str(ROOT / "synthDrivers"), "Difones2")
    normal = synth._get_direct_character_sound("a")
    synth.definir_letras_rapidas(True)
    fast = synth._get_direct_character_sound("a")
    assert normal and fast and normal != fast