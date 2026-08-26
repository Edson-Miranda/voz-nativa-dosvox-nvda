# Native DOSVOX voice for NVDA

[Documentação em português](README.md).

This is a Portuguese synthesizer for NVDA based on the native voice from the
DOSVOX system, developed at UFRJ beginning in 1993.

This is an independent NVDA adaptation. It is not an official product of the
DOSVOX Project or NV Access.

## Features

- Difones, Difones 2, Difones 3, and Difones 5 voice banks;
- playback of the original recordings for letters, numbers, and symbols;
- an alternative set of fast letter recordings;
- Cortafala, Rapidinho, and volume reduction options;
- configurable pauses and diphone parameters in `dosvox.ini`;
- responsive cancellation and streaming synthesis for long texts;
- handling of numbers, times, Brazilian real amounts, punctuation, and
  symbols;
- integration with spelling and NVDA Input Help.

## Structure

- `manifest.ini`: add-on identification and compatibility metadata;
- `synthDrivers/vozNativaDoDosvox.py`: NVDA integration;
- `synthDrivers/dosvox_data/dosvox_native_core.py`: synthesis core;
- `synthDrivers/dosvox_data/`: voice banks, rules, configuration, and
  recordings;
- `doc/pt_BR/readme.html`: user help displayed by NVDA;
- `tests/`: automated checks;
- `build_nvda_addon.py`: generation of the installable package.

## Testing and building the package

Python 3 is required.

```powershell
python .\tests\run_tests.py
python .\build_nvda_addon.py
```

The package is created in `dist/`. This directory is ignored by Git; published
packages must be attached to a repository release.

## Installation

Open the `.nvda-addon` file while NVDA is running, confirm the installation,
and restart NVDA. Then select “Voz nativa do DOSVOX” under Preferences,
Settings, Speech, Synthesizer.

## Authorship and origin

- NVDA adaptation: Edson Miranda
  (`edson.demiranda.melo@gmail.com`);
- improvements integrated into version 2.1.1: Lucas Antônio, including
  restoration of the space recording, audio streaming adjustments involving
  Letras and LetrasRapidas, text chunking corrections, and removal of
  unsuitable numeric controls from the voice settings panel;
- original system and voice: DOSVOX Project, developed at NCE/UFRJ beginning
  in 1993.

See [NOTICE.md](NOTICE.md) and [LICENSE.md](LICENSE.md). Antônio Borges
authorized the use and redistribution of the DOSVOX audio and data in this
add-on, as confirmed by maintainer Edson Miranda.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.
