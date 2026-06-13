import io
import re
import base64


IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"}
TEXT_EXTS = {"txt", "eml", "html", "htm", "csv", "json", "md", "log"}


def _get_ext(filename: str) -> str:
    return filename.lower().rsplit(".", 1)[-1] if "." in filename else ""


def _strip_data_url(content: str) -> str:
    """
    Acepta base64 puro o Data URL:
    data:image/png;base64,AAAA...
    """
    if not isinstance(content, str):
        return ""
    if "," in content and content.strip().lower().startswith("data:"):
        return content.split(",", 1)[1]
    return content


def _decode_bytes(content: str) -> bytes:
    """
    Decodifica base64 puro o data URL. Si no es base64, retorna bytes UTF-8.
    """
    raw = _strip_data_url(content).strip()
    raw = re.sub(r"\s+", "", raw)

    try:
        return base64.b64decode(raw, validate=True)
    except Exception:
        return content.encode("utf-8", errors="ignore")


def _extract_pdf(content: str, filename: str) -> str:
    try:
        import PyPDF2

        pdf_bytes = _decode_bytes(content)
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))

        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")

        text = "\n".join(text_parts).strip()

        if not text:
            return f"[PDF sin texto extraíble: {filename}]"

        return f"[Archivo PDF: {filename}]\n\nTexto extraído:\n{text[:3000]}"

    except Exception as e:
        return f"[Error al leer PDF: {filename}. Detalle: {str(e)}]"


def _extract_docx(content: str, filename: str) -> str:
    try:
        from docx import Document

        docx_bytes = _decode_bytes(content)
        doc = Document(io.BytesIO(docx_bytes))

        text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()]).strip()

        if not text:
            return f"[DOCX sin texto extraíble: {filename}]"

        return f"[Archivo Word DOCX: {filename}]\n\nTexto extraído:\n{text[:3000]}"

    except Exception as e:
        return f"[Error al leer DOCX: {filename}. Detalle: {str(e)}]"


def _extract_image_ocr(content: str, filename: str) -> str:
    """
    OCR local para capturas de pantalla o imágenes.
    No ejecuta el archivo, no visita enlaces y no interpreta código.
    Solo extrae texto visible.
    """
    try:
        from PIL import Image, ImageOps, ImageFilter
        import pytesseract

        img_bytes = _decode_bytes(content)
        img = Image.open(io.BytesIO(img_bytes))

        # Convertir y mejorar legibilidad para OCR
        img = img.convert("RGB")

        # Aumentar tamaño si la captura es chica
        max_side = max(img.size)
        if max_side < 1600:
            scale = min(2.5, 1600 / max_side)
            new_size = (int(img.width * scale), int(img.height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        gray = ImageOps.grayscale(img)
        gray = ImageOps.autocontrast(gray)
        gray = gray.filter(ImageFilter.SHARPEN)

        text = pytesseract.image_to_string(
            gray,
            lang="spa+eng",
            config="--oem 3 --psm 6"
        ).strip()

        if not text:
            return (
                f"[Imagen/Captura sin texto legible por OCR: {filename}]\n"
                "No se pudo extraer texto visible. Si la captura está borrosa o el texto es muy pequeño, "
                "pedile al usuario que suba una imagen más clara o copie el texto manualmente."
            )

        return f"[Imagen/Captura analizada por OCR: {filename}]\n\nTexto extraído:\n{text[:3000]}"

    except Exception as e:
        return f"[Error al aplicar OCR sobre imagen: {filename}. Detalle: {str(e)}]"


def extract_text_from_file(content: str, filename: str = "") -> str:
    """
    Extrae texto legible de diferentes tipos de archivo.
    content: texto plano, base64 puro o data URL base64.
    filename: nombre del archivo para detectar tipo.
    """
    ext = _get_ext(filename)

    if ext == "pdf":
        return _extract_pdf(content, filename)

    if ext == "docx":
        return _extract_docx(content, filename)

    if ext in IMAGE_EXTS:
        return _extract_image_ocr(content, filename)

    if ext in TEXT_EXTS:
        return content[:3000]

    # Fallback seguro: no ejecutar, solo analizar como texto truncado
    return content[:3000]


def is_base64(s: str) -> bool:
    try:
        raw = _strip_data_url(s)
        base64.b64decode(raw, validate=True)
        return True
    except Exception:
        return False
