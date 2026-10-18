# MagnaCarta2-Recompiled

[简体中文](README.md) · [日本語](README.ja.md)

## Overview

A Simplified Chinese localization and reusable localization-tooling project for the original Xbox 360 game MagnaCarta 2. The repository was previously named `Magna-Carta-2-CN`; the current repository name and research history remain unchanged.

## Current status

**Windows x64 native recompilation development is suspended indefinitely as of 2026-10-18.** This is a planned technical archive, not a rejection of existing research. Native recompilation is no longer a near-term deliverable.

Future development focuses on localizing original Xbox 360 game resources, with Xenia as the primary environment for game verification. The first milestone is a minimal proof of Simplified Chinese glyph coverage, text reinsertion and in-game display. Xenia validation, Chinese typography and production translations have not yet passed in-game acceptance.

No playable native Windows version or Chinese patch is available. Historical title-screen, menu and partial video readbacks do not demonstrate complete gameplay.

The [technical archive](docs/NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md) and [status index](docs/STATUS.md) retain stages 1–36, subsequent evidence, unfinished experiments and restoration instructions. The GitHub repository remains non-Archived.

## Development and validation

Basic tooling requires Python 3.12+ and Git. [BUILDING.md](BUILDING.md) retains resource investigation and historical native-research reproduction steps. Research uses fingerprinted Korean Xbox 360 two-disc inputs. Original images, executables, resources and third-party SDKs are not distributed in this repository.

```powershell
python -m unittest discover -s tests -v
python tools/validators/validate_catalog.py localization/zh-Hans/catalog.json
python -m tools.validators.validate_markdown_style
```

These commands validate tools and data rules, not gameplay in Xenia or the native host.

## Documentation

| Topic | Entry |
|---|---|
| Archive, environment and unresolved issues | [Technical archive](docs/NATIVE_RECOMPILATION_ARCHIVE_2026-10-18.md) |
| Research stages and localization preparation | [Status index](docs/STATUS.md) |
| Build environment and historical reproduction | [BUILDING.md](BUILDING.md) |
| Translation data and terminology | [Translation standard](TRANSLATING.md) · [Glossary](GLOSSARY.md) |
| Technical findings | [TECHNICAL.md](TECHNICAL.md) · [File formats](docs/FILE_FORMATS.md) |
| Contributions | [Contributing](CONTRIBUTING.md) |
| Issue reports | [GitHub Issues](https://github.com/jyh9521/MagnaCarta2-Recompiled/issues) |

## Licensing and credits

Original project tools use the [MIT license](LICENSE); translations use the [translation license](LICENSE-translations.md). Game code, assets, fonts and third-party components have separate licensing terms. See [licensing boundaries](LICENSING.md) and [credits](CREDITS.md).
