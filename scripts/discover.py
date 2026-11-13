import os

ROOT = r"C:\FOSSEE"
TARGETS = ["ngspice.exe", "ngspice_con.exe", "kicad.exe", "kicad-cli.exe", "python.exe"]

for folder, subfolders, files in os.walk(ROOT):
    for name in files:
        if name.lower() in TARGETS:
            print(name, "->", os.path.join(folder, name))