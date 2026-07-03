"""WinRT OCR wrapper - uses Windows 10/11 built-in OCR API."""

from __future__ import annotations

import asyncio
from typing import Any

try:
    import winrt.windows.media.ocr as ocr
    import winrt.windows.graphics.imaging as imaging
    import winrt.windows.storage.streams as streams
    WINRT_AVAILABLE = True
except ImportError:
    WINRT_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class WinRTOCR:
    """Windows Runtime OCR - fast, built-in, no external dependencies."""
    
    def __init__(self, language: str = "en-US"):
        self.language = language
        self._engine = None
        self._available_langs = None
    
    @property
    def available(self) -> bool:
        return WINRT_AVAILABLE
    
    @property
    def available_languages(self) -> list[str]:
        if self._available_langs is None and WINRT_AVAILABLE:
            try:
                self._available_langs = [str(lang) for lang in ocr.OcrEngine.AvailableRecognizerLanguages]
            except Exception:
                self._available_langs = []
        return self._available_langs or []
    
    def _get_engine(self):
        if self._engine is None and WINRT_AVAILABLE:
            try:
                lang = ocr.Language(self.language)
                if not ocr.OcrEngine.IsLanguageSupported(lang):
                    lang = ocr.Language("en-US")
                self._engine = ocr.OcrEngine.TryCreateFromLanguage(lang)
            except Exception:
                self._engine = ocr.OcrEngine.TryCreateFromUserProfileLanguages()
        return self._engine
    
    async def _ocr_async(self, bitmap: Any) -> list[dict]:
        """Internal async OCR."""
        engine = self._get_engine()
        if not engine:
            return []
        
        result = await engine.RecognizeAsync(bitmap)
        lines = []
        for line in result.Lines:
            lines.append({
                "text": line.Text,
                "bounding_rect": {
                    "left": int(line.BoundingRect.X),
                    "top": int(line.BoundingRect.Y),
                    "right": int(line.BoundingRect.X + line.BoundingRect.Width),
                    "bottom": int(line.BoundingRect.Y + line.BoundingRect.Height),
                },
                "words": [
                    {
                        "text": word.Text,
                        "bounding_rect": {
                            "left": int(word.BoundingRect.X),
                            "top": int(word.BoundingRect.Y),
                            "right": int(word.BoundingRect.X + word.BoundingRect.Width),
                            "bottom": int(word.BoundingRect.Y + word.BoundingRect.Height),
                        }
                    }
                    for word in line.Words
                ]
            })
        return lines
    
    def ocr_image_path(self, image_path: str) -> list[dict]:
        """OCR an image file."""
        if not WINRT_AVAILABLE:
            return []
        
        async def _do_ocr():
            # Load image as SoftwareBitmap
            file = await streams.StorageFile.GetFileFromPathAsync(image_path)
            stream = await file.OpenAsync(streams.FileAccessMode.Read)
            decoder = await imaging.BitmapDecoder.CreateAsync(stream)
            bitmap = await decoder.GetSoftwareBitmapAsync()
            return await self._ocr_async(bitmap)
        
        return asyncio.run(_do_ocr())
    
    def ocr_bitmap(self, bitmap: Any) -> list[dict]:
        """OCR a SoftwareBitmap directly."""
        if not WINRT_AVAILABLE:
            return []
        return asyncio.run(self._ocr_async(bitmap))
    
    def ocr_screen_region(self, left: int, top: int, right: int, bottom: int) -> list[dict]:
        """OCR a screen region by capturing it first."""
        if not WINRT_AVAILABLE:
            return []
        
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        
        width = right - left
        height = bottom - top
        
        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        gdi32.SelectObject(hdc_mem, hbitmap)
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, 0x00CC0020)  # SRCCOPY
        
        # Save to temp file for WinRT
        import tempfile
        import os
        tmp_path = os.path.join(tempfile.gettempdir(), f"ocr_{os.getpid()}_{left}_{top}.bmp")
        
        # BMP header
        import struct
        bmp_header = struct.pack('<2sIHHI', b'BM', 54 + width * height * 4, 0, 0, 54)
        dib_header = struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        
        bits = (ctypes.c_byte * (width * height * 4))()
        gdi32.GetBitmapBits(hbitmap, len(bits), bits)
        
        with open(tmp_path, 'wb') as f:
            f.write(bmp_header + dib_header + bytes(bits))
        
        try:
            result = self.ocr_image_path(tmp_path)
        finally:
            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        
        # Adjust coordinates to screen space
        for line in result:
            rect = line["bounding_rect"]
            rect["left"] += left
            rect["top"] += top
            rect["right"] += left
            rect["bottom"] += top
            for word in line["words"]:
                wrect = word["bounding_rect"]
                wrect["left"] += left
                wrect["top"] += top
                wrect["right"] += left
                wrect["bottom"] += top
        
        return result


# Global instance
_ocr_instance: WinRTOCR | None = None

def get_ocr(language: str = "en-US") -> WinRTOCR:
    """Get global OCR instance."""
    global _ocr_instance
    if _ocr_instance is None or _ocr_instance.language != language:
        _ocr_instance = WinRTOCR(language)
    return _ocr_instance


def ocr_available() -> bool:
    """Check if WinRT OCR is available."""
    return WINRT_AVAILABLE


def ocr_languages() -> list[str]:
    """Get available OCR languages."""
    return get_ocr().available_languages