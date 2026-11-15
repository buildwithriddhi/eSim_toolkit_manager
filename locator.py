import os
import sys
import json
from pathlib import Path

if sys.platform == "win32":
    import winreg

UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
UNINSTALL_KEY_32BIT = r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"


def read_value(key, name):
    try:
        value, _value_type = winreg.QueryValueEx(key, name)
        return value
    except OSError:
        return None


def read_uninstall_entries():
    if sys.platform != "win32":
        return []

    places = [
        (winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY),
        (winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY_32BIT),
        (winreg.HKEY_CURRENT_USER, UNINSTALL_KEY),
    ]

    entries = []
    for hive, path in places:
        try:
            parent = winreg.OpenKey(hive, path)
        except OSError:
            continue

        with parent:
            number_of_subkeys = winreg.QueryInfoKey(parent)[0]
            for index in range(number_of_subkeys):
                try:
                    child_name = winreg.EnumKey(parent, index)
                    with winreg.OpenKey(parent, child_name) as child:
                        name = read_value(child, "DisplayName")
                        if not name:
                            continue
                        location = read_value(child, "InstallLocation")
                        entries.append({
                            "name": str(name),
                            "version": read_value(child, "DisplayVersion"),
                            "location": str(location) if location else None,
                        })
                except OSError:
                    continue
    return entries


def find_in_registry():
    found = []
    for entry in read_uninstall_entries():
        if entry["name"].lower().startswith("esim") and entry["location"]:
            found.append(entry)
    return found

def looks_like_esim(folder):
    folder = Path(folder)
    return (folder / "eSim.exe").is_file() and (folder / "tools").is_dir()


def find_esim_root(config, user_path=None):
    attempts = []

    if user_path:
        attempts.append(("user setting", user_path))

    from_env = os.environ.get("ESIM_ROOT")
    if from_env:
        attempts.append(("ESIM_ROOT variable", from_env))

    for entry in find_in_registry():
        attempts.append(("Windows registry", entry["location"]))

    for candidate in config["esim_root_candidates"]:
        attempts.append(("default location", candidate))
    
    if __name__=="__main__":
        print("This is the list of possible paths :")
        for source, folder in attempts:
            print(source,folder)

    for source, folder in attempts:
        if looks_like_esim(folder):
            return Path(folder), source

    return None, None


if __name__ == "__main__":
    TOOLS_FILE = Path(__file__).parent / "tools.json"
    with open(TOOLS_FILE, encoding="utf-8") as f:
        tools= json.load(f)
        for entry in find_in_registry():
            print(entry)


    print("\nSearching for eSim root...")

    root, source = find_esim_root(tools)

    if root:
        print("eSim found at:", root)
        print("Found using:", source)
    else:
        print("eSim installation not found.")