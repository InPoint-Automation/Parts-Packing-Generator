## Building from Source

Developed and tested on Ubuntu 26.04. Includes packaging script for Windows machine to generate executable.

1. Clone the repository
```
git clone https://github.com/InPoint/PartsPackingGenerator.git
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

On Linux, bundle the sources:

```
packaging/make_windows_bundle.sh
```

Copy the resulting ZIP to a Windows box with Python 3.12, unzip, and run:

```
packaging\build_windows.bat
```

This produces a one-folder PyInstaller bundle at `dist\PartsPack\PartsPack.exe`.