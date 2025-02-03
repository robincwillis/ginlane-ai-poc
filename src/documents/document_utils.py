import uuid
import hashlib
from typing import Dict, Any
import json

from langchain.schema import Document
from typing import List


class DocumentUtils:
  @staticmethod
  def save_documents_to_json(documents: List[Document], file_path: str):
    data = [
      {
        "metadata": doc.metadata,
        "content": doc.page_content
      }
      for doc in documents
    ]

    DocumentUtils.save_to_json(data, file_path)

  @staticmethod
  def save_to_json(dataset: Dict[str, Any], file_path: str):
    """Save processed dataset to JSON file"""
    with open(file_path, 'w', encoding='utf-8') as f:
      json.dump(dataset, f, indent=2, ensure_ascii=False)

  @staticmethod
  def load_from_json(input_path: str) -> Dict[str, Any]:
    """Load dataset from JSON file"""
    with open(input_path, 'r', encoding='utf-8') as f:
      return json.load(f)

  @staticmethod
  def generate_chunk_id() -> str:
    """Generate a unique chunk identifier."""
    return str(uuid.uuid4())

  @staticmethod
  def generate_stable_id(content: str, salt: str = '') -> str:
    """
    Generate a stable (deterministic) ID based on content hash.

    Args:
        content: Text content to hash
        salt: Optional salt to add variability

    Returns:
        Stable chunk identifier
    """
    hash_input = content + salt
    return hashlib.md5(hash_input.encode()).hexdigest()

  @staticmethod
  def extract_metadata(
      content: str,
      max_summary_length: int = 200
  ) -> Dict[str, Any]:
    """
    Extract basic metadata from content.

    Args:
        content: Text content
        max_summary_length: Maximum summary length

    Returns:
        Metadata dictionary
    """
    return {
        'chunk_id': DocumentUtils.generate_chunk_id(),
        'length': len(content),
        'summary': (content[:max_summary_length] + '...')
        if len(content) > max_summary_length
        else content
    }
