"""
manifest.py - read eSim's pinned dependency list from GitHub.

eSim publishes windows/deps-manifest.json in its repository. It pins every
third-party artifact (version, download URL, sha256). This module:

  1. fetches that file (with a timeout),
  2. validates it,
  3. renames its entries to the tool names used in tools.json,
  4. downloads an artifact and verifies its sha256.

Standard library only, so there is nothing extra to install.
"""

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

# tools.json sits next to this file (same folder as detector.py).
TOOLS_FILE = Path(__file__).parent / "tools.json"

# Which eSim release to read the manifest from. Use a tag, not "master",
# because master moves and would change your baseline without warning.
DEFAULT_REF = "v2.6"

MANIFEST_URL = (
    "https://raw.githubusercontent.com/FOSSEE/eSim/{ref}/windows/deps-manifest.json"
)

# manifest key -> tool name used in tools.json.
# Anything not listed here (msys2, iverilog, innosetup, ...) is ignored.
NAME_MAP = {
    "python": "esim-python",
    "ngspice": "ngspice",
    "kicad_installer": "kicad-cli",
}

# Every mapped entry must have these fields.
REQUIRED_FIELDS = ("version", "url", "filename", "sha256")

SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
USER_AGENT = "eSim-tool-manager"
CHUNK_SIZE = 1024 * 1024  # 1 MB


class ManifestError(Exception):
    """Raised when the manifest cannot be fetched, parsed or trusted."""


# ----------------------------------------------------------------------------
# 1. Fetching
# ----------------------------------------------------------------------------

def fetch_manifest(ref=DEFAULT_REF, timeout=10):
    """Download the manifest for the given git ref and return it as a dict."""
    url = MANIFEST_URL.format(ref=ref)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise ManifestError(f"GitHub returned HTTP {error.code} for {url}") from error
    except urllib.error.URLError as error:
        raise ManifestError(f"Could not reach GitHub ({error.reason})") from error
    except TimeoutError as error:
        raise ManifestError(f"Timed out after {timeout}s fetching {url}") from error

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"The manifest at {url} is not valid JSON ({error})") from error

    if not isinstance(data, dict):
        raise ManifestError("The manifest should be a JSON object at the top level.")
    return data


# ----------------------------------------------------------------------------
# 2. Validating
# ----------------------------------------------------------------------------

def validate_manifest(raw):
    """Return a list of problems found (an empty list means the manifest is fine)."""
    problems = []

    for manifest_key in NAME_MAP:
        entry = raw.get(manifest_key)
        if not isinstance(entry, dict):
            problems.append(f"'{manifest_key}' is missing or is not an object.")
            continue

        for field in REQUIRED_FIELDS:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"'{manifest_key}.{field}' is missing or empty.")

        url = entry.get("url")
        if isinstance(url, str) and url.strip() and not url.startswith("https://"):
            problems.append(f"'{manifest_key}.url' must start with https://")

        sha = entry.get("sha256")
        if isinstance(sha, str) and sha.strip() and not SHA256_PATTERN.match(sha):
            problems.append(f"'{manifest_key}.sha256' is not a 64-character hex string.")

    return problems


# ----------------------------------------------------------------------------
# 3. Mapping to tools.json names
# ----------------------------------------------------------------------------

def map_manifest(raw):
    """
    Validate, then return {tool_name: {version, url, filename, sha256}}.
    Raises ManifestError if validation fails.
    """
    problems = validate_manifest(raw)
    if problems:
        raise ManifestError("Manifest failed validation:\n  - " + "\n  - ".join(problems))

    mapped = {}
    for manifest_key, tool_name in NAME_MAP.items():
        entry = raw[manifest_key]
        mapped[tool_name] = {
            "version": entry["version"].strip(),
            "url": entry["url"].strip(),
            "filename": entry["filename"].strip(),
            "sha256": entry["sha256"].strip().lower(),
        }
    return mapped


def load_requirements(ref=DEFAULT_REF, timeout=10):
    """Fetch + validate + map in one call. This is the function other modules use."""
    return map_manifest(fetch_manifest(ref, timeout))


# ----------------------------------------------------------------------------
# 3b. Writing the manifest values into tools.json
# ----------------------------------------------------------------------------

def sync_tools_json(ref=DEFAULT_REF, timeout=10, tools_file=TOOLS_FILE):
    """
    Fetch the manifest and save its values into tools.json.

    For every tool that appears in both files it writes:
        required_version, download_url, filename, sha256, required_version_source
    and removes the old hardcoded minimum_version fields.

    The file is written to a temporary name first and then swapped in, so a
    crash halfway can never leave tools.json half-written.
    If GitHub can't be reached, ManifestError is raised and tools.json is
    left exactly as it was.
    """
    requirements = load_requirements(ref, timeout)
    tools_file = Path(tools_file)
    config = json.loads(tools_file.read_text(encoding="utf-8"))

    for tool_name, info in requirements.items():
        tool = config["tools"].get(tool_name)
        if tool is None:
            continue  # tool is in the manifest but not tracked in tools.json
        tool.pop("minimum_version", None)
        tool.pop("minimum_version_source", None)
        tool["required_version"] = info["version"]
        tool["download_url"] = info["url"]
        tool["filename"] = info["filename"]
        tool["sha256"] = info["sha256"]
        tool["required_version_source"] = f"eSim {ref} windows/deps-manifest.json"

    temp_file = tools_file.with_name(tools_file.name + ".tmp")
    temp_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_file, tools_file)
    return requirements


# ----------------------------------------------------------------------------
# 4. Downloading with sha256 verification
# ----------------------------------------------------------------------------

def sha256_of_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url, destination, expected_sha256, timeout=30):
    """
    Download url to destination and check its sha256.

    The file is first written to '<destination>.part'. It is only renamed to
    the real name if the hash matches, so a bad or partial download can never
    be mistaken for a good one. Returns the final Path.
    """
    if not url.startswith("https://"):
        raise ManifestError(f"Refusing to download over a non-HTTPS URL: {url}")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, \
                open(partial, "wb") as out:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
    except urllib.error.HTTPError as error:
        partial.unlink(missing_ok=True)
        raise ManifestError(f"Download failed: HTTP {error.code} for {url}") from error
    except urllib.error.URLError as error:
        partial.unlink(missing_ok=True)
        raise ManifestError(f"Download failed: {error.reason}") from error
    except (TimeoutError, OSError) as error:
        partial.unlink(missing_ok=True)
        raise ManifestError(f"Download failed: {error}") from error

    actual = digest.hexdigest()
    if actual != expected_sha256.lower():
        partial.unlink(missing_ok=True)
        raise ManifestError(
            f"sha256 mismatch for {destination.name}\n"
            f"  expected: {expected_sha256.lower()}\n"
            f"  got:      {actual}\n"
            "The file was deleted. It may be corrupted or tampered with."
        )

    partial.replace(destination)
    return destination


# ----------------------------------------------------------------------------
# Quick manual test:  python manifest.py [ref]
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # python manifest.py          -> just print what the manifest says
    # python manifest.py sync     -> also save it into tools.json
    args = [a for a in sys.argv[1:] if a != "sync"]
    do_sync = "sync" in sys.argv[1:]
    ref = args[0] if args else DEFAULT_REF

    print(f"Fetching manifest from eSim ref '{ref}' ...")
    try:
        requirements = sync_tools_json(ref) if do_sync else load_requirements(ref)
    except ManifestError as error:
        print("FAILED:", error)
        sys.exit(1)

    for tool_name, info in requirements.items():
        print(f"\n{tool_name}")
        print(f"  version : {info['version']}")
        print(f"  file    : {info['filename']}")
        print(f"  sha256  : {info['sha256']}")
        print(f"  url     : {info['url']}")

    if do_sync:
        print(f"\nSaved into {TOOLS_FILE}")