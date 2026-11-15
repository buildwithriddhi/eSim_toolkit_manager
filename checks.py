import os
from dataclasses import dataclass

from locator import read_uninstall_entries

OK = "OK"
WARNING = "WARNING"
PROBLEM = "PROBLEM"


@dataclass
class Check:
    name: str
    status: str
    message: str
    fix: str = ""


def check_install_path(root):
    text = str(root)
    if "program files" in text.lower():
        return Check(
            "Install path", PROBLEM,
            f"eSim is installed under Program Files: {text}",
            "Reinstall eSim into a folder such as C:\\FOSSEE\\eSim.",
        )
    if " " in text:
        return Check(
            "Install path", PROBLEM,
            f"The eSim folder path contains spaces: {text}",
            "Reinstall eSim into a folder whose path has no spaces.",
        )
    return Check("Install path", OK, f"{text} has no spaces and is not under Program Files.")


def check_path_for_conflicts(keywords):
    hits = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        lowered = entry.lower()
        if any(word in lowered for word in keywords):
            hits.append(entry)

    if hits:
        return Check(
            "PATH conflicts", WARNING,
            "These PATH entries look like MinGW or MSYS: " + "; ".join(hits),
            "If eSim misbehaves, remove these folders from your PATH setting.",
        )
    return Check("PATH conflicts", OK, "No MinGW or MSYS folders found on PATH.")


def check_conflicting_software(keywords):
    names = [entry["name"] for entry in read_uninstall_entries()]
    hits = sorted({n for n in names if any(word in n.lower() for word in keywords)})

    if hits:
        return Check(
            "Conflicting software", WARNING,
            "Installed programs that may conflict with eSim: " + ", ".join(hits),
            "If eSim misbehaves, uninstall these and reinstall eSim.",
        )
    return Check("Conflicting software", OK, "No known conflicting programs found.")