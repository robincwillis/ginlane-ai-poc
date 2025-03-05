import os
from typing import List, Dict, Any
import json

from langchain_community.document_loaders import TextLoader, UnstructuredMarkdownLoader, JSONLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from datetime import datetime, timezone
from pathlib import Path
import hashlib

from documents.markdown_processor import MarkdownProcessor
from documents.pdf_processor import PdfProcessor
from documents.json_processor import JsonProcessor

from documents.document_utils import DocumentUtils

from config import DEF_CHUNK_OVERLAP, DEF_CHUNK_SIZE


class DocumentChunker:
  def __init__(
    self,
    document_config_file: str,
    chunk_size: int = DEF_CHUNK_SIZE,
    chunk_overlap: int = DEF_CHUNK_OVERLAP,
    supported_file_types: List[str] = ['.pdf', '.md', '.json', '.txt']
  ):
    self.chunk_size = chunk_size
    self.chunk_overlap = chunk_overlap
    self.supported_file_types = supported_file_types

    # Initialize
    self.text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap,
      separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""],
      length_function=len
    )

    self.config = DocumentUtils.load_from_json(document_config_file)

  def process_directory(
    self,
    directory_path: str
  ) -> Dict[str, Any]:
    """Process all files in a directory and its subdirectories"""

    processed_docs = []
    subjects = set()
    total_chunks = 0

    base_dir = os.path.abspath(directory_path)

    for root, _, files in os.walk(base_dir):
      for file in files:
        file_path = os.path.join(root, file)
        file_ext = os.path.splitext(file)[1].lower()

        if file_ext not in self.supported_file_types:
          continue

        subject = DocumentUtils.get_subject_from_path(file_path, base_dir)

        processed_doc = self.process_document(
          file, file_path, file_ext, subject)

        if not processed_doc:
          print(f"Warn: didn't get a processed doc for {directory_path}")
          continue

        processed_docs.append(processed_doc)
        total_chunks += len(processed_doc["chunks"])

        subjects.update(processed_doc["metadata"]["subjects"])

    # Create dataset with directory structure information
    dataset = {
        "metadata": {
            "creation_date": datetime.now(timezone.utc).isoformat(),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "total_documents": len(processed_docs),
            "total_chunks": total_chunks,
            "subjects": sorted(list(subjects)),
            "directory_structure": DocumentUtils.get_directory_structure(base_dir)
        },
        "documents": processed_docs
    }

    return dataset

  def process_document(
    self,
    file_name: str,
    file_path: str,
    file_ext: str,
    subject: str
  ) -> Dict[str, Any]:
    """Process a single document into chunks with metadata"""

    content_type = None
    priority = 0

    for entry in self.config:
      if entry['document'] == file_name:
        priority = entry.get('priority', 0)
        content_type = entry.get('content_type')
        break

    try:
      match file_ext:
        case ".md":
          print("Processing Markdown file...")
          # loader = UnstructuredMarkdownLoader(file_path)
          # doc = loader.load()
          markdown_processor = MarkdownProcessor(file_path)
          chunks = markdown_processor.process_document()
        case ".pdf":
          print("Processing PDF file...")
          pdf_processor = PdfProcessor(file_path)
          # doc = pdf_processor.pages
          chunks = pdf_processor.process_document()
        case ".json":
          print("Processing JSON file...")
          chunks = []
          json_processor = JsonProcessor(file_path)
          if (content_type == "qa"):
            chunks = json_processor.process_question_document()
          elif (content_type == "services"):
            chunks = json_processor.process_services_document()
          else:
            chunks = json_processor.process_document()

        case ".txt":
          print("Processing Text file...")
          loader = TextLoader(file_path)
          doc = loader.load()
          chunks = self.text_splitter.split_text(doc.page_content)
        case _:
          print(f"Unsupported file type. {file_path}")
          return

    except Exception as e:
      print(f"Error processing {file_path}: {str(e)}")

    processed_chunks = []
    unique_subjects = set()

    if not chunks:
      print(f"No chunks found {file_path}")
    # Process chunks with metadata
    for i, doc in enumerate(chunks):
      chunk = doc.page_content
      metadata = doc.metadata
      # Generate unique chunk ID
      chunk_id = hashlib.md5(
        f"{file_name}_{i}_{chunk[:50]}".encode()).hexdigest()

      # Calculate chunk metrics
      # chunk_metrics = self.calculate_chunk_metrics(chunk)

      # Extra Metadata from config

      # get subjects from metadata
      # if subject, then add to subjects
      subjects = []
      if subject:
        subjects.append(subject)
      if 'subject' in metadata:
        subjects.append(metadata['subject'])
      # title
      unique_subjects.update(subjects)
      # summary

      # get headings from metadata
      headings = []
      if 'headings' in metadata:
        headings.extend(metadata['headings'])
      else:
        for i in range(1, 4):
          heading_key = f'header_{i}'
          if heading_key in metadata:
            headings.append(metadata[heading_key])

      if chunk:
        processed_chunks.append({
          "chunk_id": chunk_id,
          "subjects": subjects,
          "headings": headings,
          "content_type": content_type,
          "question": metadata.get('question'),
          "services": [metadata.get('service')] if metadata.get('service') is not None else [],
          "content": chunk,
          "metadata": {
              "source": file_name,
              "chunk_number": i + 1,
              "char_length": len(chunk),
              "word_count": len(chunk.split()),
              "priority": priority + metadata.get('priority_score', 0),
              "related_chunks": metadata.get('related_chunks', [])
              # "metrics": chunk_metrics
          }
        })
      else:
        print(f"Empty chunk in {file_path}")

        # Create document entry
    processed_doc = {
        "doc_id": hashlib.md5(file_name.encode()).hexdigest(),
        "file_name": file_name,
        "file_type": file_ext,
        "chunks": processed_chunks,
        "metadata": {
            "source_path": file_path,
            "subjects": list(unique_subjects),
            "creation_date": datetime.now(timezone.utc).isoformat(),
            "total_chunks": len(chunks),
            "original_size": os.path.getsize(file_path) if os.path.exists(file_path) else None
        },
    }

    return processed_doc
