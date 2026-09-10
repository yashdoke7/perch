"""On-device OCR through Windows.Media.Ocr (architecture Part VI, `ocr_image`).

Why the Windows engine rather than Tesseract or a neural OCR package:

    * it ships with Windows 10 and 11 -- no binary to install, no model to
      download, nothing added to the install size
    * it runs ON THE DEVICE, so reading a screenshot of something private
      does not send it anywhere. For a tool whose privacy story is "zero
      bytes leave the machine", an OCR step that uploaded pixels would undo
      the whole design at the first screenshot
    * it is fast: ~240 ms for a two-line capture on the development machine

What it is not: a layout engine. It returns lines of text in reading order,
which is exactly what a screenshot of a paragraph, an error dialog or a stack
trace needs, and not enough for a table or a form. That limit is stated in the
panel's provenance line ("read by Windows OCR") so an odd answer about a table
can be traced to its cause.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# Windows OCR accuracy falls off sharply on small glyphs, and a screenshot of
# UI text at 100% scaling is small. Upscaling short captures before
# recognition is the cheapest reliable fix -- measured, a 1x capture of 12px
# UI text drops characters that the 2x version reads cleanly.
UPSCALE_BELOW_HEIGHT = 400


@dataclass
class OcrResult:
    text: str
    engine: str = "windows"          # "windows" | "none"
    language: str = ""
    ms: int = 0
    note: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.text.strip())


def _prepare(path: Path) -> tuple[Path, bool]:
    """Upscale small captures and cap huge ones. Returns (path, is_temp)."""
    from PIL import Image

    with Image.open(path) as img:
        w, h = img.size
        scale = 1.0
        if h < UPSCALE_BELOW_HEIGHT:
            scale = 2.0
        limit = 9000                      # engine max is 10000; keep a margin
        if max(w, h) * scale > limit:
            scale = limit / max(w, h)
        if scale == 1.0 and img.mode in ("RGB", "RGBA", "L"):
            return path, False
        out = img.convert("RGB").resize(
            (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        fd, name = tempfile.mkstemp(prefix="perch-ocr-", suffix=".png")
        os.close(fd)                 # an open fd pins the file on Windows
        tmp = Path(name)
        out.save(tmp)
        return tmp, True


async def _recognise(path: Path) -> tuple[str, str]:
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage import FileAccessMode, StorageFile

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        return "", ""
    file = await StorageFile.get_file_from_path_async(str(path.resolve()))
    stream = await file.open_async(FileAccessMode.READ)
    try:
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
    finally:
        stream.close()               # else the temp file cannot be deleted
    result = await engine.recognize_async(bitmap)
    lines = [line.text for line in result.lines]
    return "\n".join(lines), engine.recognizer_language.language_tag


def available() -> str:
    """The recogniser language if Windows OCR can run here, else ''."""
    try:
        from winrt.windows.media.ocr import OcrEngine
        engine = OcrEngine.try_create_from_user_profile_languages()
        return engine.recognizer_language.language_tag if engine else ""
    except Exception:
        return ""


def read_image(path: str | Path) -> OcrResult:
    """Read the text in an image. Never raises: OCR is a convenience, and a
    screenshot that cannot be read is still a screenshot the user can ask about."""
    started = time.perf_counter()
    source = Path(path)
    if not source.is_file():
        return OcrResult("", "none", note=f"no such image: {source.name}")

    try:
        prepared, is_temp = _prepare(source)
    except Exception as exc:                              # noqa: BLE001
        return OcrResult("", "none", note=f"could not open the image ({exc})")

    try:
        # A fresh event loop per call: this runs on worker threads, and an
        # asyncio loop belongs to the thread that made it.
        text, lang = asyncio.run(_recognise(prepared))
    except ImportError:
        return OcrResult("", "none",
                         note="Windows OCR bindings missing: pip install "
                              "winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging "
                              "winrt-Windows.Storage")
    except Exception as exc:                              # noqa: BLE001
        return OcrResult("", "none", note=f"Windows OCR failed ({exc})")
    finally:
        if is_temp:
            try:
                prepared.unlink(missing_ok=True)
            except OSError:
                pass                 # a stray temp file must not cost the answer

    ms = int((time.perf_counter() - started) * 1000)
    if not text.strip():
        return OcrResult("", "windows", lang, ms,
                         note="no text found in the screenshot")
    return OcrResult(text.strip(), "windows", lang, ms)
