"""
OCR text extraction module.

Primary backend: Windows OCR API via winrt (available on Windows 10+, no install required)
Fallback backend: Tesseract (requires pytesseract + Tesseract binary)
No-op mode: When config.ocr_backend == 'none', returns empty list

The Windows OCR API is the preferred backend because:
- No external dependency (built into Windows)
- Fast (runs on GPU if available)
- Good accuracy for UI text
- No per-call cost
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

from windowsagent.exceptions import OCRError

if TYPE_CHECKING:
    from windowsagent.config import Config
    from windowsagent.observer.screenshot import Screenshot

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """A single text region extracted by OCR.

    All coordinates are in logical pixels matching the source screenshot.
    """

    text: str
    bounding_box: tuple[int, int, int, int]  # (left, top, right, bottom) logical pixels
    confidence: float                         # 0.0-1.0 (Windows OCR always returns 1.0)
    line_index: int                           # Which OCR line this text belongs to


def extract_text(screenshot: "Screenshot", config: "Config") -> list[OCRResult]:
    """Extract all text from a screenshot.

    Args:
        screenshot: The screenshot to analyse.
        config: WindowsAgent configuration (determines OCR backend).

    Returns:
        List of OCRResult with text and bounding boxes. Empty list if OCR is
        disabled or no text found. Never raises on "no text found".

    Raises:
        OCRError: If the configured OCR backend fails to initialise or execute.
    """
    if config.ocr_backend == "none":
        return []

    if config.ocr_backend == "windows":
        try:
            return _extract_windows_ocr(screenshot)
        except OCRError:
            raise
        except Exception as exc:
            if config.ocr_backend == "windows":
                logger.warning(
                    "Windows OCR failed: %s — falling back to Tesseract if available", exc
                )
                try:
                    return _extract_tesseract(screenshot)
                except OCRError:
                    logger.warning("Tesseract fallback also failed; returning empty OCR results")
                    return []

    if config.ocr_backend == "tesseract":
        return _extract_tesseract(screenshot)

    logger.warning("Unknown OCR backend %r, returning empty results", config.ocr_backend)
    return []


def find_text(
    screenshot: "Screenshot",
    target: str,
    config: "Config",
    case_sensitive: bool = False,
) -> list[OCRResult]:
    """Find all occurrences of target text in a screenshot.

    Args:
        screenshot: The screenshot to search.
        target: Text to search for.
        config: WindowsAgent configuration.
        case_sensitive: If False, search is case-insensitive.

    Returns:
        List of OCRResult for each occurrence found. Empty if not found.
    """
    results = extract_text(screenshot, config)
    if not case_sensitive:
        target_cmp = target.lower()
        return [r for r in results if target_cmp in r.text.lower()]
    return [r for r in results if target in r.text]


# ── Private helpers ──────────────────────────────────────────────────────────


def _extract_windows_ocr(screenshot: "Screenshot") -> list[OCRResult]:
    """Use Windows built-in OCR API (WinRT) to extract text.

    The Windows OCR API is async-native, so we run it in a temporary event loop.
    """
    try:
        import winrt.windows.media.ocr as ocr
        import winrt.windows.graphics.imaging as imaging
        import winrt.windows.storage.streams as streams
    except ImportError as exc:
        raise OCRError(
            "winrt not installed. Install with: pip install winrt-Windows.Media.Ocr "
            "winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams"
        ) from exc

    async def _run_ocr() -> list[OCRResult]:
        # Save the PIL image to a temp PNG, then load via WinRT
        try:
            import io
            from PIL import Image

            # Convert PIL image to bytes
            img_bytes = io.BytesIO()
            screenshot.image.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            raw_bytes = img_bytes.read()

            # Create WinRT IBuffer from bytes
            writer = streams.DataWriter()
            writer.write_bytes(list(raw_bytes))
            buffer = writer.detach_buffer()

            # Decode image
            bmp_decoder = await imaging.BitmapDecoder.create_async(
                await streams.InMemoryRandomAccessStream.create_async()
            )
            # Simpler approach: write to temp file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(raw_bytes)
                tmp_path = tmp.name

            storage_file = await winrt.windows.storage.StorageFile.get_file_from_path_async(
                tmp_path
            )
            stream = await storage_file.open_async(winrt.windows.storage.FileAccessMode.READ)
            decoder = await imaging.BitmapDecoder.create_async(stream)
            bitmap = await decoder.get_software_bitmap_async()

            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
            if engine is None:
                raise OCRError("Windows OCR engine could not be created for user languages")

            result = await engine.recognize_async(bitmap)
            ocr_results: list[OCRResult] = []

            for line_idx, line in enumerate(result.lines):
                for word in line.words:
                    box = word.bounding_rect
                    dpi = screenshot.dpi_scale
                    ocr_results.append(
                        OCRResult(
                            text=word.text,
                            bounding_box=(
                                int(box.x / dpi),
                                int(box.y / dpi),
                                int((box.x + box.width) / dpi),
                                int((box.y + box.height) / dpi),
                            ),
                            confidence=1.0,
                            line_index=line_idx,
                        )
                    )

            import os
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            return ocr_results

        except OCRError:
            raise
        except Exception as exc:
            raise OCRError(f"Windows OCR processing failed: {exc}") from exc

    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run_ocr())
        finally:
            loop.close()
    except OCRError:
        raise
    except Exception as exc:
        raise OCRError(f"Windows OCR async execution failed: {exc}") from exc


def _extract_tesseract(screenshot: "Screenshot") -> list[OCRResult]:
    """Use Tesseract to extract text from a screenshot."""
    try:
        import pytesseract
    except ImportError as exc:
        raise OCRError(
            "pytesseract not installed. Install with: pip install windowsagent[ocr]"
        ) from exc

    try:
        from PIL import Image

        data = pytesseract.image_to_data(
            screenshot.image,
            output_type=pytesseract.Output.DICT,
            config="--psm 11",  # sparse text detection
        )

        results: list[OCRResult] = []
        n_boxes = len(data["level"])
        current_line = -1
        line_idx = 0

        for i in range(n_boxes):
            # Skip empty text
            text = data["text"][i].strip()
            if not text:
                continue

            conf = float(data["conf"][i])
            if conf < 0:  # Tesseract returns -1 for non-text regions
                continue

            # Track line changes
            if data["line_num"][i] != current_line:
                current_line = data["line_num"][i]
                line_idx += 1

            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]

            dpi = screenshot.dpi_scale
            results.append(
                OCRResult(
                    text=text,
                    bounding_box=(
                        int(x / dpi),
                        int(y / dpi),
                        int((x + w) / dpi),
                        int((y + h) / dpi),
                    ),
                    confidence=min(1.0, conf / 100.0),
                    line_index=line_idx,
                )
            )

        return results

    except OCRError:
        raise
    except Exception as exc:
        raise OCRError(f"Tesseract OCR failed: {exc}") from exc
