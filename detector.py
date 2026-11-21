import argparse
import json
import re
import subprocess
from pathlib import Path

from checks import (
    Check, OK, WARNING, PROBLEM,
    check_install_path, check_path_for_conflicts, check_conflicting_software,
)
from locator import find_esim_root, looks_like_esim
from versions import check_exact_version
from manifest import sync_tools_json, ManifestError, DEFAULT_REF

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


def normalise_ref(version):
    # Users type "2.6"; the git tag is "v2.6". Accept both.
    version = version.strip()
    return version if version.lower().startswith("v") else "v" + version


def saved_versions_are_for(ref, tools):
    # tools.json remembers which eSim release its versions came from.
    return all(
        f"eSim {ref} " in tool.get("required_version_source", "")
        for tool in tools["tools"].values()
    )


def run_all_checks(esim_version=None, esim_path=None):
    results = []

    # 1. If the user gave a path, it must be a real eSim folder. We stop here
    #    instead of quietly checking some other install.
    if esim_path and not looks_like_esim(esim_path):
        return [Check(
            "eSim installation", PROBLEM,
            f"'{esim_path}' does not look like an eSim folder "
            "(it needs eSim.exe and a tools folder).",
            "Check the path and try again.",
        )]

    # 2. Refresh tools.json from GitHub for the chosen eSim version. If we are
    #    offline, use the saved versions, but only if they are for that version.
    ref = normalise_ref(esim_version) if esim_version else DEFAULT_REF
    try:
        sync_tools_json(ref)
    except ManifestError as error:
        if saved_versions_are_for(ref, load_tools()):
            results.append(Check(
                "Required versions", WARNING,
                f"Could not update from GitHub ({error}). "
                f"Using the versions saved in tools.json (for eSim {ref}).",
            ))
        else:
            return [Check(
                "Required versions", PROBLEM,
                f"Could not get the required versions for eSim {ref} ({error}). "
                "The versions saved in tools.json are for a different eSim "
                "version, so they were not used.",
                "Check your internet connection and the version number "
                "(eSim 2.6 is the earliest release that publishes this list).",
            )]

    tools = load_tools()
    root, source = find_esim_root(tools, esim_path)

    if root is None:
        results.append(Check(
            "eSim installation", PROBLEM, "The eSim folder could not be found.",
            'Run again with the path: python detector.py --esim-path "C:\\path\\to\\eSim"',
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
    parser = argparse.ArgumentParser(description="Check an eSim installation.")
    parser.add_argument(
        "--esim-version",
        help="eSim release to take the required versions from, e.g. 2.6 (default: 2.6)",
    )
    parser.add_argument(
        "--esim-path",
        help='eSim install folder, e.g. "D:\\eSim" (default: search automatically)',
    )
    args = parser.parse_args()
    print_report(run_all_checks(args.esim_version, args.esim_path))


if __name__ == "__main__":
    main()