# clients/utils_ocr.py
# --------------------------------------------------------------------------
# نفس منطق ocr_folder_automation.py (build_docx و build_html)، لكن بمكتبات
# بايثون القياسية فقط - بدون python-docx وبدون Pillow.
#
# build_docx:
#   ملف .docx هو في حقيقته ملف ZIP فيه شوية ملفات XML بصيغة Word (OOXML).
#   إحنا هنا بنبني نفس الـ ZIP يدويًا بمكتبة zipfile الجاهزة في بايثون،
#   بدل ما نستخدم مكتبة python-docx لتوليده. الناتج ملف .docx حقيقي
#   يفتح عادي في Word.
#
# build_html:
#   نفس الفكرة الأصلية (ملف HTML قائم بذاته، الصور متضمنة base64) لكن
#   بقت تقبل مصدر الصورة إما مسار محلي (زي الأصل) أو رابط https مباشر
#   (حالة Google Drive) - بتستخدم urllib.request المكتبة القياسية لتحميل
#   بايتات الصورة، من غير أي مكتبة خارجية.
# --------------------------------------------------------------------------

import base64
import html as html_lib
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape


# ---------------------------------------------------------------------------
# ملف Word المجمّع (بدون python-docx)
# ---------------------------------------------------------------------------

def _docx_paragraph(text, bold=False, size=None, page_break_before=False):
    """
    يبني عنصر <w:p> واحد (فقرة) بترتيب RTL، مع خيار عريض/حجم خط/فاصل صفحة
    قبل الفقرة. size بوحدة half-points (زي ما بيستخدمها Word: 28 = 14pt).
    """
    rpr_parts = ["<w:rtl/>"]
    if bold:
        rpr_parts.append("<w:b/>")
        rpr_parts.append("<w:bCs/>")
    if size:
        rpr_parts.append(f'<w:sz w:val="{size}"/>')
        rpr_parts.append(f'<w:szCs w:val="{size}"/>')
    rpr = "<w:rPr>" + "".join(rpr_parts) + "</w:rPr>"

    break_run = '<w:r><w:br w:type="page"/></w:r>' if page_break_before else ""
    text_run = f'<w:r>{rpr}<w:t xml:space="preserve">{_xml_escape(text or "")}</w:t></w:r>'
    p_pr = '<w:pPr><w:bidi/><w:jc w:val="right"/></w:pPr>'
    return f"<w:p>{p_pr}{break_run}{text_run}</w:p>"


def build_docx(entries, out_path, title):
    """
    نفس توقيع الدالة الأصلية بالضبط (entries, out_path, title) والمخرج
    النهائي واحد لواحد: عنوان رئيسي، ثم لكل عنصر عنوان فرعي برقمه واسم
    صورته، ثم النص سطرًا سطرًا، مع فاصل صفحة بين كل عنصرين - كله RTL.
    """
    body_parts = [_docx_paragraph(title, bold=True, size="36")]

    for i, entry in enumerate(entries):
        heading = f"{entry['index']}. {entry['image_filename']}"
        body_parts.append(
            _docx_paragraph(heading, bold=True, size="28", page_break_before=(i > 0))
        )
        text = entry.get("text") or "(لم يتم استخراج نص من هذه الصورة)"
        for line in text.split("\n"):
            body_parts.append(_docx_paragraph(line))

    body_xml = "".join(body_parts)

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body_xml}"
        '<w:sectPr>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" '
        'w:header="708" w:footer="708" w:gutter="0"/>'
        '</w:sectPr>'
        '</w:body>'
        '</w:document>'
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        '</Relationships>'
    )

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types_xml)
        z.writestr("_rels/.rels", rels_xml)
        z.writestr("word/document.xml", document_xml)


# ---------------------------------------------------------------------------
# ملف HTML التفاعلي (نفس تصميم السكربت الأصلي بالحرف، فقط مصدر الصورة
# بقى يقبل رابط https - زي Google Drive - أو مسار محلي)
# ---------------------------------------------------------------------------

def _load_image_bytes(image_path):
    """يرجّع (bytes, mime) لصورة من مسار محلي - مستخدمة فقط في وضع السكربت المكتبي."""
    with open(image_path, "rb") as img_f:
        raw = img_f.read()
    ext = Path(image_path).suffix.lower().lstrip(".")
    mime = "jpeg" if ext == "jpg" else (ext or "jpeg")
    return raw, mime


def build_html(entries, out_path, title):
    """
    كل entry متوقع فيه: index, image_filename, text، وواحد اختياريًا من:
    image_bytes (bytes جاهزة - الحالة المفضّلة، زي الصور المحمّلة من Drive
    بمصادقة صحيحة) أو image_path (مسار محلي - وضع السكربت المكتبي فقط).
    لو مفيش صورة صالحة (مستند مش صورة، أو فشل التحميل)، زرار "عرض الصورة"
    بيتخفي تلقائيًا لهذا العنصر.
    """
    nav_items = []
    sections = []
    images_js = []

    for entry in entries:
        idx = entry["index"]
        fname = html_lib.escape(entry["image_filename"])
        raw_text = entry.get("text") or "(لم يتم استخراج نص من هذه الصورة)"
        text_html = html_lib.escape(raw_text).replace("\n", "<br>")

        nav_items.append(f'<li><a href="#page-{idx}" onclick="closeIndex()">{idx}. {fname}</a></li>')

        has_image = False
        image_bytes = entry.get("image_bytes")
        try:
            if image_bytes:
                b64 = base64.b64encode(image_bytes).decode("ascii")
                images_js.append(f'"{idx}": "data:image/jpeg;base64,{b64}"')
                has_image = True
            elif entry.get("image_path"):
                raw, mime = _load_image_bytes(entry["image_path"])
                b64 = base64.b64encode(raw).decode("ascii")
                images_js.append(f'"{idx}": "data:image/{mime};base64,{b64}"')
                has_image = True
            else:
                images_js.append(f'"{idx}": ""')
        except Exception:
            images_js.append(f'"{idx}": ""')

        img_btn = (
            f'<button class="img-btn" onclick="openImage({idx})">عرض الصورة</button>'
            if has_image else ""
        )

        sections.append(f"""
        <section id="page-{idx}" class="page">
          <div class="page-header">
            <h2>{idx}. {fname}</h2>
            {img_btn}
          </div>
          <div class="page-text">{text_html}</div>
        </section>
        """)

    nav_html = "\n".join(nav_items)
    sections_html = "\n".join(sections)
    images_js_str = ",\n    ".join(images_js)

    html_doc = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_lib.escape(title)}</title>
<style>
  :root {{
    --bg: #f7f5f2;
    --panel: #ffffff;
    --text: #2a2420;
    --accent: #8b5e34;
    --border: #e3ddd4;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: "Segoe UI", Tahoma, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    direction: rtl;
    line-height: 1.9;
  }}
  header.main-title {{
    padding: 22px 32px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }}
  header.main-title h1 {{ margin: 0; font-size: 21px; }}
  .page {{
    max-width: 880px;
    margin: 22px auto;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px 28px;
  }}
  .page-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }}
  .page-header h2 {{ margin: 0; font-size: 17px; color: var(--accent); }}
  .img-btn {{
    background: var(--accent);
    color: #fff;
    border: none;
    padding: 7px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    white-space: nowrap;
  }}
  .img-btn:hover {{ opacity: 0.9; }}
  .page-text {{ font-size: 15px; }}
  #indexToggle {{
    position: fixed; bottom: 26px; left: 26px;
    width: 54px; height: 54px; border-radius: 50%;
    background: var(--accent); color: #fff; border: none;
    font-size: 22px; cursor: pointer;
    box-shadow: 0 4px 14px rgba(0,0,0,0.25); z-index: 50;
  }}
  #indexPanel {{
    position: fixed; bottom: 92px; left: 26px; width: 300px; max-height: 62vh;
    overflow-y: auto; background: var(--panel); border: 1px solid var(--border);
    border-radius: 10px; box-shadow: 0 8px 22px rgba(0,0,0,0.22); padding: 8px;
    display: none; z-index: 50;
  }}
  #indexPanel.open {{ display: block; }}
  #indexPanel ul {{ list-style: none; margin: 0; padding: 0; }}
  #indexPanel li a {{
    display: block; padding: 9px 10px; color: var(--text); text-decoration: none;
    border-bottom: 1px solid var(--border); font-size: 14px; border-radius: 6px;
  }}
  #indexPanel li a:hover {{ background: var(--bg); }}
  #imgModal {{
    position: fixed; inset: 0; background: rgba(0,0,0,0.78);
    display: none; align-items: center; justify-content: center; z-index: 100;
  }}
  #imgModal.open {{ display: flex; }}
  #imgModal img {{
    max-width: 92vw; max-height: 92vh; border-radius: 6px;
    box-shadow: 0 0 30px rgba(0,0,0,0.5);
  }}
  #imgModal .close-btn {{
    position: absolute; top: 22px; left: 22px; background: #fff; border: none;
    border-radius: 50%; width: 40px; height: 40px; font-size: 20px;
    cursor: pointer; line-height: 1;
  }}
</style>
</head>
<body>

<header class="main-title">
  <h1>{html_lib.escape(title)}</h1>
</header>

{sections_html}

<button id="indexToggle" onclick="toggleIndex()" title="فهرس الصفحات">☰</button>
<div id="indexPanel">
  <ul>
  {nav_html}
  </ul>
</div>

<div id="imgModal" onclick="closeImageOnBackdrop(event)">
  <button class="close-btn" onclick="closeImage()">×</button>
  <img id="modalImg" src="" alt="">
</div>

<script>
  const images = {{
    {images_js_str}
  }};

  function toggleIndex() {{ document.getElementById('indexPanel').classList.toggle('open'); }}
  function closeIndex() {{ document.getElementById('indexPanel').classList.remove('open'); }}
  function openImage(idx) {{
    const src = images[idx];
    if (!src) return;
    document.getElementById('modalImg').src = src;
    document.getElementById('imgModal').classList.add('open');
  }}
  function closeImage() {{
    document.getElementById('imgModal').classList.remove('open');
    document.getElementById('modalImg').src = '';
  }}
  function closeImageOnBackdrop(e) {{ if (e.target.id === 'imgModal') closeImage(); }}
  document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeImage(); }});
</script>

</body>
</html>
"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
