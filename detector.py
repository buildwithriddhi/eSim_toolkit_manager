import json
import re
import subprocess
from pathlib import Path
from locator import find_esim_root
from versions import check_version

TOOLS_FILE = Path(__file__).parent / "tools.json"

#this function is opening the json file and returning that data in it in form of python dictionary so it can be referenced later
def load_tools():
    with open(TOOLS_FILE, encoding="utf-8") as f:
        return json.load(f)


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
    tools = load_tools()
    root, source = find_esim_root(tools)

    if root is None:
        print("eSim installation folder not found.")
        return
    print(f"eSim root: {root}  (found via {source})\n")

    for name, tool in tools["tools"].items():
        path = locate_tool(tool, root)
        if path is None:
            print(f"{name:12} NOT INSTALLED")
            continue
        status, version = get_version(path, tool["version_args"], tool["version_pattern"])
        if version is None:
            print(f"{name:12} {status}")
            continue
        verdict = check_version(version, tool.get("minimum_version"))
        print(f"{name:12} {version:10} {verdict}")


if __name__ == "__main__":
    main()
