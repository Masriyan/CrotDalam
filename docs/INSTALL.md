# Installation

## Requirements

- **Python 3.11 or newer.** The code uses `typing.NotRequired`,
  `asyncio.timeout` and PEP 604 unions in dataclass fields.
- No database server, no browser, no network access at import time.
- Verified on Python 3.11 through 3.14 on Linux.

## Install from source

```sh
git clone https://github.com/Masriyan/CrotDalam.git
cd CrotDalam
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[pdf]"
```

`-e` (editable) is recommended while the project is at 0.2.x, so a `git pull`
takes effect without reinstalling.

## Dependency sets

| Extra | Command | Adds |
|---|---|---|
| *(none)* | `pip install -e .` | `beautifulsoup4`, `networkx`, `regex`, `cryptography` |
| `pdf` | `pip install -e ".[pdf]"` | `reportlab`, for `report --format pdf` |
| `dev` | `pip install -e ".[dev]"` | `coverage`, `pyflakes` |
| `all` | `pip install -e ".[all]"` | Everything above |

What each core dependency is for:

| Package | Used by |
|---|---|
| `beautifulsoup4` | `crotdalam.collectors.hydration` — parsing page JSON scripts |
| `networkx` | `crotdalam.analyzers.network` — centrality and community detection |
| `regex` | `crotdalam.search.fuzzy` and `.regex` — needs `timeout=` support |
| `cryptography` | `crotdalam.utils.crypto` — AES-256-GCM at rest |

`reportlab` is imported lazily. PDF export is the only feature that fails
without it, and it fails with an explicit message.

## Optional: desktop GUI

The GUI needs Tkinter, which ships separately from Python on most Linux
distributions, plus a graphical display.

```sh
sudo dnf install python3-tkinter      # Fedora / RHEL
sudo apt install python3-tk           # Debian / Ubuntu
```

The GUI also requires the collection engine, which this release does not ship —
see [`SCOPE.md`](SCOPE.md).

## Verify the installation

```sh
crotdalam --help
crotdalam config show
python -m unittest discover -s tests
```

Expected: the help text, a JSON configuration block, and `Ran 79 tests ... OK`.

Confirm the version:

```sh
python -c "import crotdalam; print(crotdalam.__version__)"    # 0.2.0
```

## Running without installing

Every command works from a clone with no install step, provided the four runtime
dependencies are present:

```sh
pip install beautifulsoup4 networkx regex cryptography
python -m crotdalam.ui.cli --help
```

Substitute `python -m crotdalam.ui.cli` for `crotdalam` everywhere in the
documentation.

## Directory layout at runtime

`data/` is created on demand and ignored by Git:

```
data/db/         SQLite evidence databases
data/exports/    Generated reports
data/cache/      Reserved
data/logs/       Reserved
```

Override the defaults with `--database`, `--output`, or the `CROTDALAM_*`
environment variables described in [`CONFIGURATION.md`](CONFIGURATION.md).

## Uninstall

```sh
pip uninstall crotdalam
```

This removes the package only. Evidence databases and exports under `data/`
are yours to delete — see the retention guidance in
[`LEGAL-AND-ETHICS.md`](LEGAL-AND-ETHICS.md).
