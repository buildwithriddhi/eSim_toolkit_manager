import re
import subprocess

TOOLS = {
    "ngspice": {
        "path": r"C:\FOSSEE\eSim\tools\ngspice\bin\ngspice_con.exe",
        "pattern": r"ngspice-?\s*(\d+(?:\.\d+)*)",
    },
    "kicad-cli": {
        "path": r"C:\FOSSEE\eSim\tools\kicad\bin\kicad-cli.exe",
        "pattern": r"(\d+\.\d+\.\d+)",
    },
    "esim-python": {
        "path": r"C:\FOSSEE\eSim\python\python.exe",
        "pattern": r"Python (\d+\.\d+\.\d+)",
    },
}


def get_version(path, pattern):
    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return "NOT FOUND"
    except subprocess.TimeoutExpired:
        return "TIMED OUT"

    output = result.stdout + result.stderr
    match = re.search(pattern, output)
    if match:
        return match.group(1)

    print("--- raw output that did not match ---")
    print(output)
    print("-------------------------------------")
    return "VERSION NOT RECOGNISED"


for name, info in TOOLS.items():
    print(f"{name:12} {get_version(info['path'], info['pattern'])}")