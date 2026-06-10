import io
import base64

def extract_text_from_file(content: str, filename: str = "") -> str:
    """
    Extrae texto legible de diferentes tipos de archivo.
    content: contenido del archivo (texto plano o base64 para binarios)
    filename: nombre del archivo para detectar tipo
    """
    ext = filename.lower().split(".")[-1] if "." in filename else ""

    # PDF
    if ext == "pdf":
        try:
            import PyPDF2
            pdf_bytes = base64.b64decode(content) if is_base64(content) else content.encode()
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text[:3000] if text.strip() else f"[PDF sin texto extraíble: {filename}]"
        except Exception as e:
            return f"[Error al leer PDF: {str(e)}]"

    # Word (.docx)
    if ext == "docx":
        try:
            from docx import Document
            docx_bytes = base64.b64decode(content) if is_base64(content) else content.encode()
            doc = Document(io.BytesIO(docx_bytes))
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            return text[:3000] if text.strip() else f"[DOCX sin texto extraíble: {filename}]"
        except Exception as e:
            return f"[Error al leer DOCX: {str(e)}]"

    # Texto plano, EML, HTML, CSV — ya viene como texto
    return content[:3000]

def is_base64(s: str) -> bool:
    try:
        return base64.b64encode(base64.b64decode(s)).decode() == s
    except Exception:
        return False
