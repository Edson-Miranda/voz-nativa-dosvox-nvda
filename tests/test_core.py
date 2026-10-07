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
    assert _manifest_value("version") == "2.2.1"
    manifest = (ROOT / "manifest.ini").read_text(encoding="utf-8")
    assert "1993" in manifest
    assert "edson.demiranda.melo@gmail.com" in manifest


def test_voice_variants_and_data_layout():
    variants = get_available_voice_variants(str(ROOT / "synthDrivers"))
    assert set(variants) == {"Difones", "Difones2", "Difones3", "difones5"}
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

def test_ini_fallback_matches_standard_parser():
    import tempfile
    from synthDrivers.dosvox_data import dosvox_native_core as core, _configparser

    (ROOT / "dist").mkdir(exist_ok=True)
    original_parser = core.configparser
    cases = [
        ("[SINTETIZADOR]\nDIFONES=Difones3\nCORTAFALA=SIM\nRAPIDINHO=NAO\nINTERPAL=25\n", "utf-8"),
        ("[DEFAULT]\nCORTEFON=2\n[Outra]\nLETRASRAPIDAS=YES\nREDUZIRVOLUME=1\n", "utf-8-sig"),
        ("[voz]\nCORTAFALA=N\u00c3O\nPAUSAVIRG=80\n", "latin-1"),
        ("[voz]\nINTERPAL=999999\nSOBRAFON=-1\nPAUSAPONTO=abc\n", "utf-8"),
        ("[voz]\nDIFONES=Difones2\nDIFONES=Difones3\n", "utf-8"),
        ("arquivo sem secao", "utf-8"),
        ("", "utf-8"),
    ]
    try:
        with tempfile.TemporaryDirectory(dir=ROOT / "dist") as directory:
            path = str(Path(directory) / "dosvox.ini")
            for text, encoding in cases:
                Path(path).write_bytes(text.encode(encoding))
                before = Path(path).read_bytes()
                core.configparser = original_parser
                expected = core.ler_dosvox_ini(path)
                core.configparser = _configparser
                assert core.ler_dosvox_ini(path) == expected
                assert Path(path).read_bytes() == before
            settings = dict(core.CONFIG_PADRAO, difones="DIFONES3", cortafala=True,
                            rapidinho=True, reduzir_volume=True, interpal=20)
            core.escrever_dosvox_ini(path, settings)
            assert core.ler_dosvox_ini(path) == settings
            before = Path(path).read_bytes()
            assert not core.garantir_dosvox_ini(path)
            assert Path(path).read_bytes() == before
    finally:
        core.configparser = original_parser


def test_core_import_without_host_configparser():
    import subprocess
    script = """
import builtins
original = builtins.__import__
def without_configparser(name, *args, **kwargs):
    if name == 'configparser':
        raise ModuleNotFoundError('No module named configparser', name=name)
    return original(name, *args, **kwargs)
builtins.__import__ = without_configparser
from synthDrivers.dosvox_data import dosvox_native_core as core
assert core.configparser.__name__.endswith('._configparser')
assert set(core.get_available_voice_variants('synthDrivers')) == {'Difones', 'Difones2', 'Difones3', 'difones5'}
"""
    subprocess.run([sys.executable, "-c", script], cwd=ROOT, check=True)
