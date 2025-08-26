import os
import docraptor

def _get_api_key():
    return (
        os.getenv("DOC_RAPTOR_API_KEY")
    )

def render_pdf_from_html(html_content: str, filename: str, *, test: bool = True, javascript: bool = False) -> bytes:
    """
    Send HTML to DocRaptor and return PDF bytes.
    - html_content: fully rendered HTML string
    - filename: a friendly name recorded by DocRaptor
    - test: True => free test PDFs with watermark 
    - javascript: True if your HTML uses Chart.js (or any JS)
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("DocRaptor API key not set (DOC_RAPTOR_API_KEY).")

    client = docraptor.DocApi()
    client.api_client.configuration.username = api_key

    doc = {
        "test": bool(test),
        "document_type": "pdf",
        "document_content": html_content,
        "name": filename,
        "javascript": bool(javascript),
        # examples if you need later:
        # "prince_options": {"media": "print"},
        # "ignore_resource_errors": False,
    }
    return client.create_doc(doc)