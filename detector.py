import json
import re
import subprocess
from pathlib import Path

from checks import (
    Check, OK, WARNING, PROBLEM,
    check_install_path, check_path_for_conflicts, check_conflicting_software,
)
from locator import find_esim_root
from versions import check_exact_version
from manifest import sync_tools_json, ManifestError

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


def check_tool(name, tool, root):
    path = locate_tool(tool, root)
    if path is None:
        return Check(
            name, PROBLEM, "Not found in the eSim folder.",
            "Repair or reinstall eSim.",
        )

    status, version = get_version(path, tool["version_args"], tool["version_pattern"])
    if version is None:
        return Check(
            name, WARNING, f"Found at {path}, but its version could not be read ({status}).",
            "Run the tool by hand to check that it starts.",
        )

    required = tool.get("required_version")
    if not required:
        return Check(
            name, PROBLEM, "No required version is saved in tools.json.",
            "Run 'python manifest.py sync' while online.",
        )

    verdict = check_exact_version(version, required)
    if verdict == "OK":
        return Check(name, OK, f"Version {version} at {path}")
    if verdict.startswith("WRONG"):
        return Check(
            name, PROBLEM,
            f"Found version {version}, but eSim needs exactly {required}.",
            f"Install {name} {required}, or reinstall eSim.",
        )
    return Check(name, WARNING, f"Version {version}: {verdict}.")


def run_all_checks():
    # Refresh tools.json from GitHub. If we're offline, carry on with the
    # versions already saved in tools.json from the last successful sync.
    results = []
    try:
        sync_tools_json()
    except ManifestError as error:
        results.append(Check(
            "Required versions", WARNING,
            f"Could not update from GitHub ({error}). "
            "Using the versions saved in tools.json.",
        ))

    tools = load_tools()
    root, source = find_esim_root(tools)

    if root is None:
        results.append(Check(
            "eSim installation", PROBLEM, "The eSim folder could not be found.",
            "Install eSim, or tell this program where it is.",
        ))
        return results

    results.append(Check("eSim installation", OK, f"Found at {root} (found via {source})."))
    results.append(check_install_path(root))

    for name, tool in tools["tools"].items():
        results.append(check_tool(name, tool, root))

    rules = tools["environment_rules"]
    results.append(check_path_for_conflicts(rules["conflicting_path_keywords"]))
    results.append(check_conflicting_software(rules["conflicting_software_keywords"]))
    return results


def print_report(results):
    for check in results:
        print(f"[{check.status:<7}] {check.name}: {check.message}")
        if check.fix and check.status != OK:
            print(f"           Fix: {check.fix}")

    problems = sum(1 for c in results if c.status == PROBLEM)
    warnings = sum(1 for c in results if c.status == WARNING)
    print(f"\n{len(results)} checks: {problems} problem(s), {warnings} warning(s).")


def main():
    print_report(run_all_checks())


if __name__ == "__main__":
    main()