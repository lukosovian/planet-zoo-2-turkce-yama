"""Kurulum programını tek dosyalık .exe olarak paketler: installer/dist/PZ2TurkceYama.exe

Gereken: buildenv (pyinstaller, numpy, pillow, imageio, bitarray kurulu Python 3.11 ortamı) ve
oyunun kurulu olduğu bir bilgisayar (cobra-tools'un hangi modülleri kullandığını tespit etmek için).
Kullanım: buildenv\\Scripts\\python.exe installer\\build_exe.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "installer"
STAGE = HERE / "build" / "stage"
COBRA = ROOT / "cobra-tools"
PY = sys.executable

COLLECT = r'''
import sys, json
sys.path.insert(0, r"{tools}")
from pathlib import Path
import fastloc
fastloc.use_oodle(r"{dll}")
s = fastloc.read_strings(Path(r"{ovl}"))
fastloc.inject(Path(r"{ovl}"), Path(r"{out}"), {{next(iter(s)): "x"}})
print(json.dumps(sorted(sys.modules)))
'''


def copy_cobra() -> None:
    dst = STAGE / "cobra-tools"
    shutil.rmtree(dst, ignore_errors=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.dll", "*.exe", "*.log")
    for d in ("generated", "modules", "utils"):
        shutil.copytree(COBRA / d, dst / d, ignore=ignore)
    (dst / "constants").mkdir(parents=True)
    for f in ("__init__.py", "converter.py"):
        shutil.copy2(COBRA / "constants" / f, dst / "constants" / f)
    shutil.copytree(COBRA / "constants" / "Planet Coaster 2", dst / "constants" / "Planet Coaster 2", ignore=ignore)
    for f in ("__init__.py", "__version__.py", "LICENSE"):
        if (COBRA / f).exists():
            shutil.copy2(COBRA / f, dst / f)


def hidden_imports() -> list[str]:
    cfg_file = ROOT / "config.json"
    game = Path(json.loads(cfg_file.read_text(encoding="utf-8"))["game_dir"]) if cfg_file.exists() else Path(sys.argv[1])
    ovl = game / "Win64" / "ovldata" / "Content0" / "Localised" / "English" / "UnitedStates" / "Loc.ovl"
    dll = sorted(game.glob("oo2core_*_win64.dll"))[-1]
    code = COLLECT.format(tools=ROOT / "tools", dll=dll, ovl=ovl, out=HERE / "build" / "probe.ovl")
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise SystemExit(r.stderr[-2000:])
    mods = json.loads(r.stdout.strip().splitlines()[-1])
    skip = ("generated", "modules", "utils", "constants", "fastloc", "__main__", "__mp_main__", "cython_runtime")
    return [m for m in mods if not m.startswith(skip) and not m.startswith("_frozen")]


def main() -> int:
    if (ROOT / "tools" / "release.py").exists():  # çeviri deposunda yayın verisini yeniden üret
        subprocess.run([PY, str(ROOT / "tools" / "release.py")], check=True, cwd=ROOT)
    shutil.rmtree(STAGE, ignore_errors=True)
    STAGE.mkdir(parents=True)
    copy_cobra()
    shutil.copy2(ROOT / "release" / "tr_data.json.gz", STAGE / "tr_data.json.gz")
    mods = hidden_imports()
    print(f"{len(mods)} gizli içe aktarma")
    args = [PY, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--name", "PZ2TurkceYama",
            "--distpath", str(HERE / "dist"), "--workpath", str(HERE / "build" / "work"),
            "--specpath", str(HERE / "build"), "--paths", str(ROOT / "tools"),
            "--add-data", f"{STAGE / 'cobra-tools'};cobra-tools",
            "--add-data", f"{STAGE / 'tr_data.json.gz'};.",
            "--add-data", f"{HERE / 'LISANSLAR.txt'};.",
            "--hidden-import", "fastloc", "--copy-metadata", "imageio", "--copy-metadata", "numpy", "--copy-metadata", "pillow"]
    if (HERE / "simge.ico").exists():
        args += ["--icon", str(HERE / "simge.ico"), "--add-data", f"{HERE / 'simge.ico'};."]
    for m in mods:
        args += ["--hidden-import", m]
    args.append(str(HERE / "kurulum.py"))
    subprocess.run(args, check=True, cwd=ROOT)
    exe = HERE / "dist" / "PZ2TurkceYama.exe"
    print(f"{exe}: {exe.stat().st_size // (1024 * 1024)} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
