"""Planet Zoo 2 Türkçe Yama — tek tıklık kurulum programı.

Oyuncunun kendi Loc.ovl dosyasını yedekler, Türkçe metinleri İngilizce dil yuvalarına (US ve UK) yazar.
Oyun dosyası bu programın içinde yoktur; yama her kurulumda oyuncunun kendi dosyasından üretilir.
"""
from __future__ import annotations

import glob
import gzip
import hashlib
import json
import os
import shutil
import sys
import threading
import traceback
import winreg
from pathlib import Path

# Pencereli .exe'de konsol yoktur; çıktılar yok sayılır
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE.parent / "tools"))  # kaynak koddan çalıştırırken

APP_NAME = "Planet Zoo 2 Türkçe Yama"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PZ2TurkceYama"
BACKUP_DIR = APP_DIR / "yedek"
STATE_FILE = APP_DIR / "durum.json"
SLOTS = ("English/UnitedStates", "English/UnitedKingdom")


def data_file() -> Path:
    for p in (BASE / "tr_data.json.gz", BASE.parent / "release" / "tr_data.json.gz"):
        if p.exists():
            return p
    raise FileNotFoundError("tr_data.json.gz bulunamadı")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def already_patched(strings: dict[str, str], entries: dict) -> bool:
    """Dosyadaki metinlerin çoğu zaten Türkçe mi (ör. geliştirici aracıyla ya da başka bir sürümle yamalanmış)?"""
    hits = sum(1 for sid, (_, tr) in entries.items() if strings.get(sid) == tr)
    return hits > len(entries) // 2


# --------------------------------------------------------------------------- oyun klasörünü bulma

def is_game_dir(p: Path) -> bool:
    return (p / "Win64" / "ovldata").is_dir() and any(p.glob("oo2core_*_win64.dll"))


def find_game_dirs() -> list[Path]:
    found: list[Path] = []
    # Epic Games
    manifests = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    for item in manifests.glob("*.item"):
        m = load_json(item, {})
        if "planet zoo 2" in str(m.get("DisplayName", "")).lower() or "planetzoo2" in str(m.get("InstallLocation", "")).lower().replace(" ", ""):
            found.append(Path(m.get("InstallLocation", "")))
    # Steam
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam = Path(winreg.QueryValueEx(k, "SteamPath")[0])
        libs = [steam]
        vdf = steam / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            import re
            libs += [Path(x.replace("\\\\", "\\")) for x in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore"))]
        for lib in libs:
            found += [Path(p) for p in glob.glob(str(lib / "steamapps" / "common" / "Planet Zoo 2*"))]
    except OSError:
        pass
    # Bilinen varsayılan konumlar
    for drive in "CDEFG":
        found += [Path(f"{drive}:/Program Files/Epic Games/PlanetZoo2"), Path(f"{drive}:/Epic Games/PlanetZoo2")]
    found.append(Path.home() / "Epic Games" / "PlanetZoo2")
    out = []
    for p in found:
        if p not in out and is_game_dir(p):
            out.append(p)
    return out


def loc_files(game: Path) -> list[tuple[str, str]]:
    """[(paket_adı, ovldata'ya göre yol)] — yalnızca İngilizce dil yuvaları."""
    base = game / "Win64" / "ovldata"
    out = []
    for slot in SLOTS:
        for p in sorted(base.rglob(f"Localised/{slot}/Loc.ovl")):
            rel = p.relative_to(base).as_posix()
            out.append((rel.split("/Localised/")[0].replace("/", "_"), rel))
    return out


# --------------------------------------------------------------------------- kurulum / kaldırma

class GameRunning(Exception):
    pass


def install(game: Path, log) -> None:
    import logging
    import fastloc
    logging.disable(logging.WARNING)  # cobra-tools'un ayrıntılı kayıtları
    dlls = sorted(game.glob("oo2core_*_win64.dll"))
    fastloc.use_oodle(str(dlls[-1]))
    with gzip.open(data_file(), "rt", encoding="utf-8") as f:
        data = json.load(f)
    log(f"Çeviri verisi: {data['count']} metin (sürüm {data['version']})")
    state = load_json(STATE_FILE, {})
    base = game / "Win64" / "ovldata"
    targets = loc_files(game)
    if not targets:
        raise RuntimeError("Oyunda İngilizce dil dosyası (Loc.ovl) bulunamadı.")
    done = 0
    verified: dict[str, dict[str, str]] = {}  # paket → ABD dosyasında doğrulanan çeviriler
    for pack, rel in targets:
        entries = data["packs"].get(pack)
        if not entries:
            continue
        game_file = base / rel
        backup = BACKUP_DIR / rel
        entry = state.get(rel, {})
        cur = sha256(game_file)
        log(f"{rel}: okunuyor...")
        if cur == entry.get("patched_sha") and backup.exists():
            original = backup
            strings = fastloc.read_strings(original)
        else:
            strings = fastloc.read_strings(game_file)
            if already_patched(strings, entries):
                # Dosya zaten Türkçe: orijinal değildir, yedeğin üzerine yazılmaz. Mevcut yedek yalnızca
                # aynı oyun sürümüne aitse (metin kimlikleri aynıysa) ve kendisi yamalı değilse tutulur.
                keep = False
                if backup.exists():
                    old = fastloc.read_strings(backup)
                    keep = old.keys() == strings.keys() and not already_patched(old, entries)
                if not keep:
                    backup.unlink(missing_ok=True)
                    entry = {}
                    log(f"{rel}: dosya zaten Türkçe yamalı ama orijinal yedeği yok. Yamayı kaldırmak için "
                        "Epic Games / Steam'de oyun dosyalarını doğrulaman gerekir.")
                original = game_file
            else:
                # Oyunun kendi dosyası (ilk kurulum ya da oyun güncellemesi): yedekle
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(game_file, backup)
                if entry.get("orig_sha") and entry["orig_sha"] != cur:
                    log(f"{rel}: oyun güncellenmiş, yeni dosya yedeklendi.")
                entry = {"orig_sha": cur}
                original = backup
        texts, stale, present = {}, 0, 0
        if pack in verified:
            # İngiliz İngilizcesi yuvası: yazım farkları (colour/color) parmak izini bozar, bu yüzden
            # ABD dosyasında doğrulanan çeviriler kullanılır.
            texts = {sid: tr for sid, tr in verified[pack].items() if sid in strings}
        else:
            for sid, (fp, tr) in entries.items():
                en = strings.get(sid)
                if en is None:
                    continue
                if en == tr:
                    present += 1
                    texts[sid] = tr
                elif fingerprint(en) == fp:
                    texts[sid] = tr
                else:
                    stale += 1
            verified[pack] = texts
        tmp = APP_DIR / "gecici" / rel
        n = fastloc.inject(original, tmp, texts)
        try:
            shutil.copyfile(tmp, game_file)
        except PermissionError as e:
            raise GameRunning() from e
        finally:
            pass
        entry["patched_sha"] = sha256(game_file)
        state[rel] = entry
        save_json(STATE_FILE, state)
        shutil.rmtree(APP_DIR / "gecici", ignore_errors=True)
        msg = f"{rel}: {n} metin Türkçe"
        if present:
            msg += f" ({present} metin zaten Türkçeydi)"
        if stale:
            msg += f" ({stale} metin oyun güncellemesiyle değiştiği için İngilizce kaldı)"
        log(msg)
        done += 1
    if not done:
        raise RuntimeError("Hiçbir dil dosyasına yama uygulanamadı.")


def uninstall(game: Path, log) -> None:
    state = load_json(STATE_FILE, {})
    base = game / "Win64" / "ovldata"
    restored = 0
    for rel, entry in state.items():
        game_file = base / rel
        backup = BACKUP_DIR / rel
        if not game_file.exists():
            continue
        if entry.get("patched_sha") and not backup.exists():
            log(f"{rel}: orijinal yedek yok. Epic Games / Steam'de oyun dosyalarını doğrulayarak geri alabilirsin.")
        elif entry.get("patched_sha") and sha256(game_file) == entry["patched_sha"] and backup.exists():
            try:
                shutil.copyfile(backup, game_file)
            except PermissionError as e:
                raise GameRunning() from e
            log(f"{rel}: orijinal dosya geri yüklendi")
            restored += 1
        else:
            log(f"{rel}: zaten orijinal (ya da oyun güncellenmiş)")
        entry.pop("patched_sha", None)
    save_json(STATE_FILE, state)
    if not restored:
        log("Geri yüklenecek yamalı dosya bulunamadı.")


# --------------------------------------------------------------------------- arayüz

def main() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("640x460")
    root.minsize(560, 400)
    try:
        root.iconbitmap(str(BASE / "simge.ico"))
    except tk.TclError:
        pass

    settings = load_json(APP_DIR / "ayarlar.json", {})
    game_var = tk.StringVar(value=settings.get("game_dir", ""))
    if not game_var.get() or not is_game_dir(Path(game_var.get())):
        dirs = find_game_dirs()
        game_var.set(str(dirs[0]) if dirs else "")

    frm = ttk.Frame(root, padding=14)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=APP_NAME, font=("Segoe UI", 15, "bold")).pack(anchor="w")
    ttk.Label(frm, text="Resmî olmayan, gönüllü hazırlanmış Türkçe çeviri. Oyunda dil olarak English seçili olmalı.",
              wraplength=600).pack(anchor="w", pady=(2, 10))

    row = ttk.Frame(frm)
    row.pack(fill="x")
    ttk.Label(row, text="Oyun klasörü:").pack(side="left")
    entry = ttk.Entry(row, textvariable=game_var)
    entry.pack(side="left", fill="x", expand=True, padx=6)

    def browse():
        d = filedialog.askdirectory(title="Planet Zoo 2 klasörünü seç (PlanetZoo2.exe'nin olduğu klasör)")
        if d:
            game_var.set(d)

    ttk.Button(row, text="Değiştir...", command=browse).pack(side="left")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=12)
    btn_install = ttk.Button(btns, text="Türkçe Yamayı Kur")
    btn_install.pack(side="left", ipadx=10, ipady=4)
    btn_remove = ttk.Button(btns, text="Yamayı Kaldır")
    btn_remove.pack(side="left", padx=8, ipadx=10, ipady=4)

    ttk.Label(frm, text="Çeviri: lukosovian  •  github.com/lukosovian  •  Ücretsizdir, satılamaz.",
              foreground="#666").pack(side="bottom", anchor="w", pady=(8, 0))
    log_box = tk.Text(frm, height=12, wrap="word", state="disabled", font=("Segoe UI", 9))
    log_box.pack(fill="both", expand=True)

    def log(msg: str) -> None:
        def add():
            log_box.configure(state="normal")
            log_box.insert("end", msg + "\n")
            log_box.see("end")
            log_box.configure(state="disabled")
        root.after(0, add)

    def run(action, title_ok: str):
        game = Path(game_var.get().strip().strip('"'))
        if not is_game_dir(game):
            messagebox.showerror(APP_NAME, "Seçilen klasör Planet Zoo 2 klasörü değil.\n"
                                           "PlanetZoo2.exe dosyasının bulunduğu klasörü seç.")
            return
        save_json(APP_DIR / "ayarlar.json", {"game_dir": str(game)})
        btn_install.state(["disabled"])
        btn_remove.state(["disabled"])

        def work():
            try:
                action(game, log)
                root.after(0, lambda: messagebox.showinfo(APP_NAME, title_ok))
            except GameRunning:
                log("HATA: Dil dosyasına yazılamadı. Oyun açık olabilir.")
                root.after(0, lambda: messagebox.showerror(APP_NAME, "Oyun açıkken yama kurulamaz.\nOyunu kapatıp tekrar dene."))
            except Exception as e:  # noqa: BLE001
                log("HATA: " + "".join(traceback.format_exception_only(type(e), e)).strip())
                (APP_DIR / "hata.log").parent.mkdir(parents=True, exist_ok=True)
                (APP_DIR / "hata.log").write_text(traceback.format_exc(), encoding="utf-8")
                root.after(0, lambda: messagebox.showerror(APP_NAME, f"Bir hata oluştu:\n{e}\n\nAyrıntılar: {APP_DIR / 'hata.log'}"))
            finally:
                root.after(0, lambda: (btn_install.state(["!disabled"]), btn_remove.state(["!disabled"])))

        threading.Thread(target=work, daemon=True).start()

    btn_install.configure(command=lambda: run(install, "Türkçe yama kuruldu!\n\nOyunda dil olarak English seçili olduğundan emin ol.\n"
                                                       "Oyun güncellendiğinde bu programı tekrar çalıştırman yeterli."))
    btn_remove.configure(command=lambda: run(uninstall, "Yama kaldırıldı, oyunun orijinal dil dosyası geri yüklendi."))

    if game_var.get():
        log(f"Oyun bulundu: {game_var.get()}")
    else:
        log("Oyun klasörü otomatik bulunamadı. 'Değiştir...' ile PlanetZoo2.exe'nin olduğu klasörü seç.")
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] in ("--kur", "--kaldir"):
        (install if sys.argv[1] == "--kur" else uninstall)(Path(sys.argv[2]), print)
    else:
        main()
