import re
import yaml
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
      chunk_overlap: int = DEF_CHUNK_OVERLAP,
      remove_metadata: bool = True 
    ):
    print(f"init MarkdownProcessor:")

    self.priority_boost = priority_boost
    self.remove_metadata = remove_metadata

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

  def clean_metadata(self, content, exclude_fields=None):
    """
      Filter out specific metadata fields or all metadata from the markdown content.
    """
    if self.remove_metadata:
      # Remove the entire YAML frontmatter section
      pattern = r'^---\n.*?\n---\n'
      return re.sub(pattern, '', content, flags=re.DOTALL)
    
    if not exclude_fields:
      # No fields to exclude, return content as is
      return content
    
    # Extract YAML frontmatter
    frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not frontmatter_match:
      # No frontmatter found, return content as is
      return content
    
    # Parse YAML
    yaml_text = frontmatter_match.group(1)
    metadata = yaml.safe_load(yaml_text)
    
    # Remove excluded fields
    for field in exclude_fields:
        if field in metadata:
            del metadata[field]
    
    # Convert back to YAML
    filtered_yaml = yaml.dump(metadata, default_flow_style=False)
    
    # Replace original frontmatter with filtered frontmatter
    filtered_content = f"---\n{filtered_yaml}---\n" + content[frontmatter_match.end():]
    
    return filtered_content
    

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
    text = self.clean_metadata(self.text)
    content = self.clean_markdown(text)
    docs = self.markdown_splitter.split_text(content)
    splits = self.media_splitter.split_documents(docs)
    return splits


if __name__ == "__main__":
  markdown_path = "../../data/projects/cedar.md"
  markdown_processor = MarkdownProcessor(markdown_path)
  docs = markdown_processor.process_document()

  DocumentUtils.save_documents_to_json(docs, "../../scrap/test.json")
