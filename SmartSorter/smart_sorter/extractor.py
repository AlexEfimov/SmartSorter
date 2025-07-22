# extractor.py — Извлечение текста из файлов разных форматов

from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional
import pdfplumber
from docx import Document
import pandas as pd
from PIL import Image
import pytesseract
import logging

# Подавляем назойливые предупреждения от pdfminer
logging.getLogger("pdfminer").setLevel(logging.ERROR)

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path) -> Optional[str]:
        pass


class PDFExtractor(BaseExtractor):
    def extract(self, file_path: Path) -> Optional[str]:
        try:
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as e:
            logging.warning(f"Ошибка чтения PDF {file_path.name}: {e}")
            return ""


class DocxExtractor(BaseExtractor):
    def extract(self, file_path: Path) -> Optional[str]:
        try:
            doc = Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            logging.warning(f"Ошибка чтения DOCX {file_path.name}: {e}")
            return ""


class XlsxExtractor(BaseExtractor):
    def extract(self, file_path: Path) -> Optional[str]:
        try:
            xls = pd.ExcelFile(file_path)
            text = ""
            for sheet in xls.sheet_names:
                df = xls.parse(sheet)
                text += df.to_string(index=False)
            return text
        except Exception as e:
            logging.warning(f"Ошибка чтения XLSX {file_path.name}: {e}")
            return ""


class ImageExtractor(BaseExtractor):
    def extract(self, file_path: Path) -> Optional[str]:
        try:
            image = Image.open(file_path)
            return pytesseract.image_to_string(image)
        except Exception as e:
            logging.warning(f"Ошибка OCR изображения {file_path.name}: {e}")
            return ""


class TextExtractor:
    def __init__(self):
        self.extractors = {
            ".pdf": PDFExtractor(),
            ".docx": DocxExtractor(),
            ".xlsx": XlsxExtractor(),
            ".png": ImageExtractor(),
            ".jpg": ImageExtractor(),
            ".jpeg": ImageExtractor()
        }

    def extract(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        extractor = self.extractors.get(ext)
        if extractor:
            return extractor.extract(file_path) or ""
        logging.info(f"Формат {ext} не поддерживается")
        return ""
