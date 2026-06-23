## Building from Source

Developed and tested on Ubuntu 26.04. Includes packaging script for Windows machine to generate executable.

1. Clone the repository
```
git clone https://github.com/InPoint-Automation/Parts-Packing-Generator.git
cd PartsPackingGenerator
```

2. Create a Python 3.12 virtual environment and install dependencies

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Run the app

```
python PartsPack.py
```

## Build the Windows exe

### Dependencies
- python.org Python 3.12 with the `py` launcher (so `py -3.12` works).
- Visual Studio Build Tools with the "Desktop development with C++" selected

### Build

```
packaging\build_windows.bat
```

The script creates a `.build-venv` installs the dependencies, then builds the bundle.

This produces the PyInstaller executable `PartsPack.exe`.
