import re

# from langchain_community.document_loaders import UnstructuredMarkdownLoader

from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.docstore.document import Document

from documents.rich_media_text_splitter import RichMediaTextSplitter
from documents.document_utils import DocumentUtils

DEF_CHUNK_SIZE = 600
DEF_CHUNK_OVERLAP = 40


class MarkdownProcessor:
  def __init__(
      self,
      markdown_path,
      priority_boost: float = 0.2,
      chunk_size: int = DEF_CHUNK_SIZE,
      chunk_overlap: int = DEF_CHUNK_OVERLAP
    ):
    print(f"init MarkdownProcessor:")

    self.priority_boost = priority_boost

    seperators = [
        ("#", "header_1"),
        ("##", "header_2"),
        ("###", "header_3")
    ]

    self.markdown_splitter = MarkdownHeaderTextSplitter(
      headers_to_split_on=seperators,
      # strip_headers=False
    )

    self.media_splitter = RichMediaTextSplitter(
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap
    )

    with open(markdown_path, 'r', encoding='utf-8') as file:
      self.text = file.read()
    # loader = UnstructuredMarkdownLoader(markdown_path, mode="elements")
    # self.data = loader.load()

  def clean_markdown(self, text: str) -> str:
    """
    Clean markdown
    """
    cleaned_lines = []
    for line in text.splitlines():
      # Remove Google Docs styles separators
      if re.match(r'\*{0,2}\\\\\_+_?\*{0,2}', line):
        continue

      if re.match(r'\*{0,2}\\_+_?\*{0,2}', line):
        continue

      # Remove repeated separator lines (underscores, asterisks, etc.)
      if re.fullmatch(r'[_*\-=]{10,}', line):
        continue

      # Remove empty headers
      if re.fullmatch(r'#+\s*', line):
        continue

      # Remove unnecessary horizontal rules
      if re.fullmatch(r'[-_*]{3,}', line):
        continue

      cleaned_lines.append(line)

    # Reassemble lines and remove excessive whitespace
    return '\n'.join(cleaned_lines).strip()

  def process_document(self):
    content = self.clean_markdown(self.text)
    docs = self.markdown_splitter.split_text(content)
    splits = self.media_splitter.split_documents(docs)
    return splits


if __name__ == "__main__":
  markdown_path = "../../data/projects/hims.md"
  markdown_processor = MarkdownProcessor(markdown_path)
  docs = markdown_processor.process_document()

  DocumentUtils.save_documents_to_json(docs, "test.json")
