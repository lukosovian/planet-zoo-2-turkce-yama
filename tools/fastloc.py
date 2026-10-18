"""Loc.ovl dosyalarını cobra-tools API'siyle süreç içinde, geçici dosya kullanmadan okur ve yazar.

ovl_tool_cmd üzerinden enjeksiyon her metin için tüm yükleyicileri tarayan bir çakışma kontrolü
yaptığı için 30 bin metinde dakikalar sürer. TXT yükleyicilerinin alt akışı olmadığından bu kontrol
burada atlanır; okuma ve yazma birkaç saniyeye iner.
"""
from __future__ import annotations

import logging
import os
import struct
import sys
from pathlib import Path

COBRA_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "cobra-tools"
if str(COBRA_DIR) not in sys.path:
    sys.path.insert(0, str(COBRA_DIR))

if not hasattr(logging, "success"):
    logging.success = lambda *a, **k: None  # type: ignore[attr-defined]
logging.getLogger().setLevel(logging.WARNING)

_GAME = "Planet Coaster 2"
SENTIMENT = " [sentiment="


_OODLE_DLL: str | None = None


def use_oodle(dll_path: str) -> None:
    """cobra-tools'un kendi Oodle DLL'si yerine verilen DLL'yi kullan (ör. oyunun oo2core_9_win64.dll'si).
    generated.formats.ovl içe aktarılmadan önce çağrılmalıdır."""
    global _OODLE_DLL
    _OODLE_DLL = dll_path


def _prepare_oodle() -> None:
    name = "modules.formats.utils.oodle.oodle"
    if not _OODLE_DLL or name in sys.modules:
        return
    import types
    src_path = COBRA_DIR / "modules" / "formats" / "utils" / "oodle" / "oodle.py"
    src = src_path.read_text(encoding="utf-8").replace(
        'oodle_dll = os.path.join(os.path.dirname(__file__), "oo2core_8_win64.dll")', f"oodle_dll = {_OODLE_DLL!r}")
    mod = types.ModuleType(name)
    mod.__file__ = str(src_path)
    exec(compile(src, str(src_path), "exec"), mod.__dict__)
    sys.modules[name] = mod


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _open(path: Path):
    path = Path(path).resolve()
    cwd = os.getcwd()
    os.chdir(COBRA_DIR)
    try:
        _prepare_oodle()
        from generated.formats.ovl import OvlFile
        ovl = OvlFile()
        ovl.game = _GAME
        ovl.load_hash_table()
        ovl.load(str(path), {})
        return ovl
    finally:
        os.chdir(cwd)


def _decode(loader) -> str:
    pool, offset = loader.root_ptr
    b = pool.get_data_at(offset)
    v = loader.mime_version
    if v == 4:
        n, sn = struct.unpack("<II", b[:8])
        text = b[8:8 + n].decode("utf-8")
        if sn:
            text += f"{SENTIMENT}{b[9 + n:9 + n + sn].decode('utf-8')}]"
        return text
    if v in (2, 3):
        n = struct.unpack("<I", b[:4])[0]
        return b[4:4 + n].decode("utf-8")
    raise ValueError(f"Desteklenmeyen TXT sürümü: {v}")


def _encode(text: str, version: int) -> bytes:
    from generated.formats.base.structs.PadAlign import get_padding
    sentiment = ""
    if version == 4 and SENTIMENT in text:
        text, sentiment = text.split(SENTIMENT)
        sentiment = sentiment[:-1]
    tb, sb = text.encode("utf-8"), sentiment.encode("utf-8")
    if version == 4:
        prefix = struct.pack("<II", len(tb), len(sb))
    elif version in (2, 3):
        prefix = struct.pack("<I", len(tb))
    else:
        raise ValueError(f"Desteklenmeyen TXT sürümü: {version}")
    entry = prefix + tb + b"\x00"
    if sb:
        entry += sb + b"\x00"
    return entry + get_padding(len(entry), alignment=8)


def read_strings(path: Path) -> dict[str, str]:
    """{metin_kimliği: metin}"""
    ovl = _open(path)
    return {Path(name).stem: _norm(_decode(ld)) for name, ld in ovl.loaders.items() if ld.ext == ".txt"}


def inject(path: Path, out_path: Path, texts: dict[str, str]) -> int:
    """Orijinal ovl'deki metinleri değiştirip out_path'e yazar. Değiştirilen metin sayısını döndürür."""
    out_path = Path(out_path).resolve()
    ovl = _open(path)
    names = {Path(name).stem: name for name, ld in ovl.loaders.items() if ld.ext == ".txt"}
    cwd = os.getcwd()
    os.chdir(COBRA_DIR)
    try:
        version = ovl.get_mime(".txt", "version")
        n = 0
        for sid, text in texts.items():
            name = names.get(sid)
            if not name:
                continue
            loader = ovl.init_loader(name, ".txt", version)
            loader.get_constants_entry()
            loader.set_ovs("STATIC")
            loader.write_root_bytes(_encode(text, version))
            loader.root_ptr[0].num_files += 1
            ovl.register_loader(loader)
            n += 1
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ovl.save(str(out_path), {"update_aux": False})
        return n
    finally:
        os.chdir(cwd)
