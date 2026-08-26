# Contributing

Thank you for helping maintain the native DOSVOX voice for NVDA. The project
preserves a Portuguese voice with historical data while providing a modern
NVDA synthesizer driver.

## Scope

The maintained voice variants are `Difones`, `Difones2`, `Difones3`, and
`difones5`. Do not restore removed variants or introduce generic rate, pitch,
or voice controls without prior agreement with the maintainer.

The synthesis core belongs in
`synthDrivers/dosvox_data/dosvox_native_core.py`. Python files placed directly
under `synthDrivers` are treated by NVDA as synthesizer driver candidates, so
the core must not be copied there.

## Before changing the project

1. Check `git status` and preserve unrelated work.
2. Read `manifest.ini`, `synthDrivers/vozNativaDoDosvox.py`, and
   `synthDrivers/dosvox_data/dosvox_native_core.py`.
3. Keep changes narrow and document the behavior they are intended to alter.
4. Do not classify, rename, or move recordings based on automated inference.
5. Do not install the add-on in NVDA or run interactive NVDA tests without the
   maintainer's explicit authorization.

For pronunciation fixes, prefer an existing authorized recording first, then
an explicit pronunciation override. Change the general phonetic converter only
when there is evidence of a systemic issue.

## Local validation

Run from the repository root:

```powershell
python .\tests\run_tests.py
python .\build_nvda_addon.py
```

A release validation should distinguish among:

- static Python compilation;
- automated Python tests;
- package generation and ZIP inspection;
- real testing inside NVDA.

Static checks and automated tests do not prove that the synthesizer works
correctly inside NVDA. Interactive verification requires installation,
synthesizer selection, voice switching, letter and symbol echo, number
reading, Input Help, cancellation, and driver option checks.

## Packaging and releases

Generated files belong in `dist/` and must not be committed. Packages must not
contain `__pycache__`, `.pyc`, logs, editor settings, credentials, or temporary
development files.

Never change the bytes of an already published package without assigning a new
version. Publishing commits, tags, releases, and NVDA Add-on Store submissions
requires explicit authorization from the maintainer.

## Credits and licensing

Preserve the origin, attribution, and permission statements in `NOTICE.md` and
`LICENSE.md`. The add-on is an independent project and must not be presented as
an official product of NCE/UFRJ, the DOSVOX Project, or NV Access.

Edson Miranda maintains the NVDA adaptation. Lucas Antônio contributed
improvements integrated into version 2.1.1. The voice and synthesis data come
from the DOSVOX Project, and their redistribution in this add-on was authorized
by Antônio Borges, as recorded in the repository notices.
