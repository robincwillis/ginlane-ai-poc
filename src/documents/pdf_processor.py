import json
from typing import List, Dict, Any

from langchain_core.documents import Document
from langchain_community.document_loaders import PDFMinerLoader

from langchain.text_splitter import RecursiveCharacterTextSplitter

from document_utils import DocumentUtils

DEF_CHUNK_SIZE = 500
DEF_CHUNK_OVERLAP = 50


class PdfProcessor:
  def __init__(
    self,
    pdf_path,
    chunk_size: int = DEF_CHUNK_SIZE,
    chunk_overlap: int = DEF_CHUNK_OVERLAP,
    priority_boost: float = 0.1
  ):
    print(f"init")
    self.text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap,
      separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""],
      length_function=len
    )

    loader = PDFMinerLoader(pdf_path)

    self.docs = loader.load()

  def process_document(self):
    return self.docs


if __name__ == "__main__":

  pdf_path = "../../data/documents/company/Corporate Values.pdf"
  pdf_processer = PdfProcessor(pdf_path)
  docs = pdf_processer.process_document()
  DocumentUtils.save_documents_to_json(docs, "test.json")
