from PyPDF2 import PdfReader
from typing import Optional
import pymupdf4llm


class PDFService:
    async def extract_text(self, file_path: str) -> Optional[str]:
        """提取PDF文本内容"""
        try:
            reader = PdfReader(file_path)
            text = "\n".join([page.extract_text() for page in reader.pages])
            return text
        except Exception:
            return None

    def pdf2md(self, file_path: str) -> Optional[str]:
        """提取PDF文本内容"""
        try:
            md_text = pymupdf4llm.to_markdown(file_path)
            return md_text
        except Exception:
            return None

    async def ocr_text(self, file_path: str) -> Optional[str]:
        pass

