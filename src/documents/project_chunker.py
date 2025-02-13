import os
from typing import List, Dict, Any
import json
from enum import Enum
import hashlib
from datetime import datetime, timezone

from langchain.text_splitter import RecursiveCharacterTextSplitter
from dataclasses import dataclass, field

from documents.markdown_processor import MarkdownProcessor
from documents.json_processor import JsonProcessor

from documents.document_utils import DocumentUtils


DEF_CHUNK_SIZE = 1000
DEF_CHUNK_OVERLAP = 200


class ProjectType(Enum):
  CASE_STUDY = "case_study"
  PROJECT_DELIVERABLE = "project_deliverable"
  CLIENT_BRIEF = "client_brief"
  PROPOSAL = "proposal"
  RESEARCH = "research"


@dataclass
class ClientMetadata:
  client_id: str
  client_name: str
  categories: List[str] = field(default_factory=list)


@dataclass
class ProjectMetadata:
  project_id: str
  client_id: str
  project_name: str
  project_type: ProjectType
  services: List[str] = field(default_factory=list)
  technologies: List[str] = field(default_factory=list)
  categories: List[str] = field(default_factory=list)


@dataclass
class ServiceMetadata:
  service_id: str
  service_name: str


class ProjectChunker:
  def __init__(
    self,
    project_config_file,
    client_config_file,
    chunk_size: int = DEF_CHUNK_SIZE,
    chunk_overlap: int = DEF_CHUNK_OVERLAP,
    supported_file_types: List[str] = ['.md', '.json']
  ):

    self.chunk_size = chunk_size
    self.chunk_overlap = chunk_overlap
    self.supported_file_types = supported_file_types

    self.text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap,
      separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""],
      length_function=len
    )

    self.project_config = DocumentUtils.load_from_json(project_config_file)
    self.client_config = DocumentUtils.load_from_json(client_config_file)

  def process_directory(
    self,
    directory_path: str
  ) -> Dict[str, Any]:
    """Process all files in a directory and its subdirectories"""

    processed_docs = []
    services = set()
    clients = set()
    total_chunks = 0

    base_dir = os.path.abspath(directory_path)

    for root, _, files in os.walk(base_dir):
      for file in files:
        file_path = os.path.join(root, file)
        file_ext = os.path.splitext(file)[1].lower()

        if file_ext not in self.supported_file_types:
          continue

        processed_doc = self.process_document(
          file, file_path, file_ext)

        if not processed_doc:
          print(f"Warn: didn't get a processed doc for {directory_path}")
          continue

        processed_docs.append(processed_doc)
        total_chunks += len(processed_doc["chunks"])

        services.update(processed_doc["metadata"]["services"])
        clients.update(processed_doc["metadata"]["clients"])

    # Create dataset with directory structure information
    dataset = {
        "metadata": {
            "creation_date": datetime.now(timezone.utc).isoformat(),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "total_documents": len(processed_docs),
            "total_chunks": total_chunks,
            "services": sorted(list(services)),
            "clients": sorted(list(clients)),
            "directory_structure": DocumentUtils.get_directory_structure(base_dir)
        },
        "documents": processed_docs
    }

    return dataset

  def get_config(self, file_name):
    """
    Retrieves document and client configuration based on the given file name.

    Args:
        file_name (str): The name of the file to search for in project_config.

    Returns:
        tuple: (doc_config, client_config), where doc_config is the matching project config
                and client_config is the associated client config.
    """
    # Find the document config
    doc_config = next(
        (entry for entry in self.project_config if entry.get('document') == file_name),
        None
    )

    if not doc_config:
      print(f"Warn: No project config found for {file_name}")
      print(self.project_config)
      return None, None  # Return explicit None values to indicate failure

    # Find the client config that includes the project's ID
    client_config = next(
        (entry for entry in self.client_config if entry.get('client_id')
         == doc_config['client_id']),
        None
    )

    if not client_config:
      print(
          f"Warn: No client config found for project ID {doc_config['project_id']}")

    return doc_config, client_config

  def process_document(
    self,
    file_name: str,
    file_path: str,
    file_ext: str
  ) -> Dict[str, Any]:
    """Process a single project document into chunks with metadata"""
    chunks = []
    doc_config, client_config = self.get_config(file_name)

    # print(doc_config)
    # print(client_config)

    try:
      match file_ext:
        case ".md":
          # print("Processing Markdown File...")
          markdown_processor = MarkdownProcessor(file_path)
          chunks = markdown_processor.process_document()
        case ".json":
          # print("Processing JSON File...")
          json_processor = JsonProcessor(file_path)
          chunks = json_processor.process_document()

        case _:
          print(f"Unsupported file type. {file_path}")
          return
    except Exception as e:
      print(f"Error processing {file_path}: {str(e)}")

    processed_chunks = []
    unique_services = set()
    unique_clients = set()
    priority = doc_config.get("priority", 0)

    for i, doc in enumerate(chunks):
      chunk = doc.page_content
      metadata = doc.metadata
      chunk_id = hashlib.md5(
        f"{file_name}_{i}_{chunk[:50]}".encode()).hexdigest()

      # if services, then add to services
      services = list(set(
          (doc_config.get("services", []) if doc_config else []) +
          (client_config.get("services", []) if client_config else [])
      ))

      # get headings from metadata
      unique_services.update(services)

      # document_metadata

      if client_config:
        unique_clients.update([client_config.get("client_name")], [])

      headings = []
      if 'headings' in metadata:
        headings.extend(metadata['headings'])
      else:
        for i in range(1, 4):
          heading_key = f'header_{i}'
          if heading_key in metadata.get("document_metadata", []):
            headings.append(metadata['document_metadata'][heading_key])

      processed_chunks.append({
        "chunk_id": chunk_id,
        "services": services,
        "headings": headings,
        "content": chunk,
        "technologies": doc_config["technologies"],
        "project_id": doc_config["project_id"],
        "project_name": doc_config["project_name"],
        "client_id": doc_config["client_id"],
        "content_type": doc_config["content_type"],
        "client_name": client_config["client_name"],
        "categories": client_config["categories"],
        "chunk_number": i + 1,
        "metadata": {
          "source": file_name,
          "char_length": len(chunk),
          "word_count": len(chunk.split()),
          "priority": priority + metadata.get('priority_score', 0),
          ** metadata
        }
      })

      processed_doc = {
        "doc_id": hashlib.md5(file_name.encode()).hexdigest(),
        "file_name": file_name,
        "file_type": file_ext,
        "chunks": processed_chunks,
        "metadata": {
            "source_path": file_path,
            "services": list(unique_services),
            "clients": list(unique_clients),
            "creation_date": datetime.now(timezone.utc).isoformat(),
            "total_chunks": len(chunks),
            "original_size": os.path.getsize(file_path) if os.path.exists(file_path) else None
        },
          }

    return processed_doc
