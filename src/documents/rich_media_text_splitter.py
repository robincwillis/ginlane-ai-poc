
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from typing import List, Dict, Any, Optional
import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class MediaElement:
  type: str
  position: int
  url: str
  # alt: Optional[str] = None
  text: Optional[str] = None
  metadata: Dict[str, Any] = None


@dataclass
class DocumentMetadata:
  header_1: Optional[str] = None
  header_2: Optional[str] = None
  header_3: Optional[str] = None
  source: Optional[str] = None
  project_id: Optional[str] = None
  client_id: Optional[str] = None
  project_name: Optional[str] = None
  content_type: Optional[str] = None
  services: List[str] = None
  references: List[Dict[str, str]] = None

  def to_dict(self) -> Dict[str, Any]:
    return {k: v for k, v in self.__dict__.items() if v is not None}


class RichMediaTextSplitter:
  def __init__(self, chunk_size=1000, chunk_overlap=200):
    self.text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )

  def _is_valid_url(self, url: str) -> bool:
    try:
      result = urlparse(url)
      return all([result.scheme, result.netloc])
    except:
      return False

  def get_metadata(self, metadata) -> DocumentMetadata:
    if isinstance(metadata, DocumentMetadata):
      return metadata
    elif isinstance(metadata, dict):
      return DocumentMetadata(**metadata)
    else:
      return DocumentMetadata()

  def extract_media_and_metadata(self, text: str, doc_metadata: Optional[DocumentMetadata] = None) -> tuple[str, List[MediaElement], DocumentMetadata]:
    """Extract media elements, links, and metadata from text."""
    media_elements = []

    metadata = self.get_metadata(doc_metadata)
    metadata.references = metadata.references or []

    # Extract metadata links with pattern {meta_link: description}[url]
    meta_link_pattern = r'\{meta_link:\s*(.*?)\}\[(.*?)\]'

    def meta_link_replacer(match):
      if self._is_valid_url(match.group(2)):
        metadata.references.append({
            'description': match.group(1),
            'url': match.group(2)
        })
      return ''  # Remove metadata links from main text

    # Process metadata links first
    text = re.sub(meta_link_pattern, meta_link_replacer, text)

    # Extract images with pattern ![alt](url)
    image_pattern = r'!\[(.*?)\]\((.*?)\)'

    def image_replacer(match):
      if self._is_valid_url(match.group(2)):
        media_elements.append(MediaElement(
            type='image',
            position=len(media_elements),
            url=match.group(2),
            text=match.group(1),
            metadata={'content_type': 'image'}
        ))
        index = len(media_elements) - 1
        return f"{{{{MEDIA_{index}}}}}"
      return match.group(0)

    # Extract inline links with pattern [text](url)
    link_pattern = r'\[(.*?)\]\((.*?)\)'

    def link_replacer(match):
      if self._is_valid_url(match.group(2)):
        media_elements.append(MediaElement(
            type='link',
            position=len(media_elements),
            url=match.group(2),
            text=match.group(1),
            metadata={'link_type': 'inline'}
        ))
        index = len(media_elements) - 1
        return f"{{{{MEDIA_{index}}}}}"
      return match.group(0)

    # Process text
    processed_text = re.sub(image_pattern, image_replacer, text)
    processed_text = re.sub(link_pattern, link_replacer, processed_text)

    return processed_text, media_elements, metadata

  def restore_media(self, text: str, media_elements: List[MediaElement]) -> str:
    """Restore media elements from placeholders."""
    for element in media_elements:
      placeholder = f"{{{{MEDIA_{element.position}}}}}"
      if element.type == 'image':
        replacement = f"![{element.text or ''}]({element.url})"
      else:  # link
        replacement = f"[{element.text or element.url}]({element.url})"
      text = text.replace(placeholder, replacement)
    return text

  def split_documents(self, documents: List[Document]) -> List[Document]:
    """Split documents into chunks."""
    chunks = []
    for doc in documents:
      chunks.extend(self.create_chunks(doc.page_content, doc.metadata))
    return chunks

  def create_chunks(self, text: str, doc_metadata: Optional[DocumentMetadata] = None) -> List[Document]:
    """Create chunks while preserving media elements and metadata."""
    # Extract media elements and metadata
    processed_text, media_elements, metadata = self.extract_media_and_metadata(
      text, doc_metadata)

    # Split text
    chunks = self.text_splitter.create_documents([processed_text])

    # Restore media elements in each chunk and enrich metadata
    enriched_chunks = []
    for chunk in chunks:
      restored_text = self.restore_media(chunk.page_content, media_elements)
      chunk_metadata = {
          'media_elements': [vars(m) for m in media_elements],
          'document_metadata': metadata.to_dict(),
          'chunk_metadata': {
              'position': len(enriched_chunks),
              'total_media_elements': len(media_elements)
          }
      }
      enriched_chunks.append(Document(
          page_content=restored_text,
          metadata=chunk_metadata
      ))

    return enriched_chunks


def format_chatbot_response(
    response: str,
    metadata: Optional[Dict[str, Any]] = None,
    include_media: bool = True,
    include_references: bool = True
) -> str:
  """Format the chatbot response with proper HTML for rich media display and metadata."""
  if not include_media and not include_references:
    return response

  formatted_response = response

  # if include_media:
  # Convert markdown images to HTML
  # formatted_response = re.sub(
  #     r'!\[(.*?)\]\((.*?)\)',
  #     r'<img src="\2" alt="\1" class="chatbot-image" loading="lazy">',
  #     formatted_response
  # )

  # Convert markdown links to HTML
  # formatted_response = re.sub(
  #     r'\[(.*?)\]\((.*?)\)',
  #     r'<a href="\2" target="_blank" rel="noopener noreferrer" class="chatbot-link">\1</a>',
  #     formatted_response
  # )

  if include_references and metadata and 'document_metadata' in metadata:
    doc_metadata = metadata['document_metadata']
    if doc_metadata.get('references'):
      formatted_response += "\n\nReferences:\n"
      for ref in doc_metadata['references']:
        formatted_response += f"- {ref['description']}: {ref['url']}\n"

  return formatted_response


if __name__ == "__main__":
  # Initialize splitter
  splitter = RichMediaTextSplitter(chunk_size=500, chunk_overlap=100)

  project_id = 'd678ce23'
  markdown_path = '../../data/projects/camber.md'
  project_config_path = '../../data/project_config.json'

  with open(markdown_path, 'r', encoding='utf-8') as file:
    project_doc = file.read()

  with open(project_config_path, 'r', encoding='utf-8') as file:
    project_config = json.load(file)

  project = next(
    (project for project in project_config if project['project_id'] == project_id), None)

  print(project)
  # Create document metadata
  doc_metadata = DocumentMetadata(
      source=markdown_path,
      project_name=project['project_name'],
      client_id=project['client_id'],
      project_id=project['project_id'],
      services=project['services']
  )

  # Create chunks
  chunks = splitter.create_chunks(project_doc, doc_metadata)

  # Example of processing chunks for embedding and display
  for chunk in chunks:
    # The chunk.page_content contains the text with preserved markdown formatting
    # The chunk.metadata contains the media elements and document metadata
    print(f"Chunk text: --------")
    print(chunk.page_content)
    print(f"Metadata: {json.dumps(chunk.metadata, indent=2)}")

    # # Format for display with references
    # formatted_response = format_chatbot_response(
    #   chunk.page_content,
    #   chunk.metadata,
    #   include_media=True,
    #   include_references=True
    # )
    # print(f"Formatted for display: {formatted_response}")
