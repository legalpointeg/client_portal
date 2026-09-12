"""
client_portal/clients/image_compress.py
-----------------------------------------
نفس وحدة الضغط الموحّدة المستخدمة في lawfirm_portal الأصلي
(files_manager/image_compress.py) - بنفس القيم بالظبط عشان جودة
الصور تفضل متسقة بين المشروعين.
"""
import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1000
JPEG_QUALITY = 50


def compress_image_bytes(image_bytes, max_dimension=MAX_DIMENSION, quality=JPEG_QUALITY):
    """
    يضغط أي bytes صورة لأقصى درجة ضغط ممكنة بإعداد موحّد.
    يرجع (compressed_bytes, mime_type).
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )
        if has_alpha:
            img = img.convert("RGBA")
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue(), "image/png"
        else:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            return buf.getvalue(), "image/jpeg"
    except Exception as e:
        logger.warning(f"[image_compress] فشل ضغط الصورة، سيتم استخدام الأصلية: {e}")
        return image_bytes, None
