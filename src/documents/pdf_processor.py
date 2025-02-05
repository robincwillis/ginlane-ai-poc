import json
import re
from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from document_utils import DocumentUtils
from dataclasses import dataclass


@dataclass
class PageMetadata:
  page_number: int
  headings: List[str]
  is_title_page: bool
  is_end_matter: bool
  page_type: str


DEF_CHUNK_SIZE = 500
DEF_CHUNK_OVERLAP = 50


class PdfProcessor:
  def __init__(
    self,
    pdf_path,
    skip_title_pages: bool = True,
    skip_end_matter: bool = True,
    priority_boost: float = 0.1,
    chunk_size: int = DEF_CHUNK_SIZE,
    chunk_overlap: int = DEF_CHUNK_OVERLAP,
  ):
    self.priority_boost = priority_boost

    # self.text_splitter = RecursiveCharacterTextSplitter(
    #   chunk_size=chunk_size,
    #   chunk_overlap=chunk_overlap,
    #   separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""],
    #   length_function=len
    # )

    # 138 East Broadway October 24, 2019 New York, NY 10002
    # Presentation
    # BRAND BOOK

    # GIN LANE

    # Brand Development Capabilities Overview

    self.title_page_indicators = [
        r'(?i)^\s*table\s+of\s+contents\s*$',
        r'(?i)copyright\s+page',
        r'(?i)^\s*title\s+page\s*$',
        r'(?i)all\s+rights\s+reserved'
    ]

    self.end_matter_indicators = [
        r'(?i)^\s*references?\s*$',
        r'(?i)^\s*bibliography\s*$',
        r'(?i)^\s*acknowledgements?\s*$',
        r'(?i)^\s*thank\s+you\s*$',
        r'(?i)^\s*appendix\s*$'
      ]

    self.heading_patterns = [
        r'^#{1,6}\s+(.+)$',  # Markdown style
        r'^(?:Chapter|Section)\s+\d+[.:]\s+(.+)$',  # Chapter/Section style
        r'^\d+\.\d*\s+(.+)$',  # Numbered style
        r'^[A-Z][A-Z\s]+\s*$',  # ALL CAPS style
        r'^(?:[A-Z][a-z]+\s){2,}$'  # Title Case style
      ]

    self.pdf_path = pdf_path

    loader = PyPDFLoader(pdf_path)

    self.pages = loader.load()

  def _process_page(self, content: str, page_number: int):
    """Analyze page content and extract metadata."""

    # Is it the first page ?

    is_title_page = any(re.search(pattern, content, re.MULTILINE)
                        for pattern in self.title_page_indicators)

    is_end_matter = any(re.search(pattern, content, re.MULTILINE)
                        for pattern in self.end_matter_indicators)

    # Extract headings
    headings = []
    for line in content.split('\n'):
      for pattern in self.heading_patterns:
        match = re.match(pattern, line.strip())
        if match:
          heading = match.group(1) if match.groups() else line.strip()
          headings.append(heading)
          break

    page_type = self._get_page_type(content, is_title_page, is_end_matter)

    return PageMetadata(
      page_number=page_number + 1,
      headings=headings,
      is_title_page=is_title_page,
      is_end_matter=is_end_matter,
      page_type=page_type
    )

  def _extract_headings(self, content: str) -> List[str]:
    """Extract headings from page content."""
    headings = []
    for line in content.split('\n'):
      for pattern in self.heading_patterns:
        if re.match(pattern, line.strip()):
          headings.append(line.strip())
          break
    return headings

  def _get_page_type(self, content: str, is_title: bool, is_end: bool) -> str:
    """Determine the type of page based on content analysis."""
    if is_title:
      return 'title_matter'
    elif is_end:
      return 'end_matter'
    elif re.search(r'(?i)table\s+of\s+contents', content):
      return 'toc'
    elif len(self._extract_headings(content)) > 0:
      return 'content'
    else:
      return 'body'

  def _clean_page(self, content: str):
    """Clean page content by removing headers, footers, and formatting."""
    # Remove page numbers
    content = re.sub(r'\b\d+\b\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*\b\d+\b', '', content, flags=re.MULTILINE)

    # Remove headers and footers (common patterns)
    content = re.sub(
      r'^\s*(?:\d+\s*)?(?:[A-Za-z\s]+)\s*$', '', content, flags=re.MULTILINE)

    # Clean up whitespace
    content = re.sub(r'\s+', ' ', content)
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip()

  def process_document(self):
    chunks = []

    for page_num, page in enumerate(self.pages):
      metadata = self._process_page(page.page_content, page_num)
      content = self._clean_page(page.page_content)

      if not content:
        continue

      chunk = Document(
        page_content=content,
        metadata={
          'source': self.pdf_path,
          'page': metadata.page_number,
          'headings': metadata.headings,
          'page_type': metadata.page_type,
          # 'title': metadata.title
        }
      )
      chunks.append(chunk)
    return chunks


if __name__ == "__main__":

  pdf_path = "../../data/documents/company/Corporate Values.pdf"
  # pdf_path = "../../data/documents/case_studies/AIGA presentation 2.pdf"

  pdf_processer = PdfProcessor(pdf_path)
  docs = pdf_processer.process_document()
  DocumentUtils.save_documents_to_json(docs, "test.json")
