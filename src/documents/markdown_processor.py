import re

from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain.docstore.document import Document

from document_utils import DocumentUtils

DEF_CHUNK_SIZE = 600
DEF_CHUNK_OVERLAP = 40


class MarkdownProcessor:
  def __init__(
      self,
      markdown_path,
      chunk_size: int = DEF_CHUNK_SIZE,
      chunk_overlap: int = DEF_CHUNK_OVERLAP
    ):
    print(f"init MarkdownProcessor:")

    seperators = [
        ("#", "header_1"),
        ("##", "header_2"),
        ("###", "header_3")
    ]

    self.markdown_splitter = MarkdownHeaderTextSplitter(
      headers_to_split_on=seperators,
      # strip_headers=False
    )

    self.text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=DEF_CHUNK_SIZE,
        chunk_overlap=DEF_CHUNK_OVERLAP
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

    # TODO
    # Get Metadata from document name and filepath
    # Get overall Chunk Metadata
    # Get Chunk Priority

    content = self.clean_markdown(self.text)
    print(content)
    docs = self.markdown_splitter.split_text(content)
    splits = self.text_splitter.split_documents(docs)
    return splits
    # docs = self.markdown_splitter.split_text(self.data)


if __name__ == "__main__":
  markdown_path = "../../data/documents/case_studies/case_studies.md"
  markdown_processor = MarkdownProcessor(markdown_path)
  docs = markdown_processor.process_document()

  # print(docs)
  DocumentUtils.save_documents_to_json(docs, "test.json")
