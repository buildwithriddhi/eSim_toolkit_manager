import json
import re
import subprocess
from pathlib import Path

REGISTRY_FILE = Path(__file__).parent / "registry.json"


def load_registry():
    with open(REGISTRY_FILE, encoding="utf-8") as f:
        return json.load(f)


def find_esim_root(registry):
    for candidate in registry["esim_root_candidates"]:
        if Path(candidate).is_dir():
            return Path(candidate)
    return None


def locate_tool(tool, root):
    if root is None:
        return None
    for relative in tool["relative_paths"]:
        full_path = root / relative
        if full_path.is_file():
            return full_path
    return None


def get_version(path, args, pattern):
    try:
        result = subprocess.run(
            [str(path), *args],
            capture_output=True,
            text=True,
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return "timed out", None
    except OSError as error:
        return f"could not run ({error})", None

    output = result.stdout + result.stderr
    match = re.search(pattern, output)
    if match:
        return "ok", match.group(1)
    return "version not recognised", None


def main():
    registry = load_registry()
    root = find_esim_root(registry)

    if root is None:
        print("eSim installation folder not found.")
        return
    print(f"eSim root: {root}\n")

    for name, tool in registry["tools"].items():
        path = locate_tool(tool, root)
        if path is None:
            print(f"{name:12} NOT INSTALLED")
            continue
        status, version = get_version(path, tool["version_args"], tool["version_pattern"])
        shown = version if version else status
        print(f"{name:12} {shown:10} {path}")


if __name__ == "__main__":
    main()