from langchain_community.document_loaders import TextLoader, UnstructuredMarkdownLoader, JSONLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict, Any
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import hashlib

from markdown_processor import MarkdownProcessor
from pdf_processor import PdfProcessor
from json_processor import JsonProcessor

from document_utils import DocumentUtils


DEF_CHUNK_SIZE = 500
DEF_CHUNK_OVERLAP = 50


class DocumentChunker:
  def __init__(
    self,
    chunk_size: int = DEF_CHUNK_SIZE,
    chunk_overlap: int = DEF_CHUNK_OVERLAP
  ):
    self.chunk_size = chunk_size
    self.chunk_overlap = chunk_overlap

    # Initialize
    self.text_splitter = RecursiveCharacterTextSplitter(
      chunk_size=chunk_size,
      chunk_overlap=chunk_overlap,
      separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""],
      length_function=len
    )

    self.config = DocumentUtils.load_from_json('../../data/config.json')

  def get_subject_from_path(
    self,
    file_path: str,
    base_dir: str
  ) -> str:
    """Extract subject from the directory structure"""
    # Get relative path from base directory
    rel_path = os.path.relpath(os.path.dirname(file_path), base_dir)
    if rel_path == '.':
      return None
    subject = rel_path.replace(os.sep, '/').replace('_', ' ').title()
    return subject

  def get_directory_structure(self, base_dir: str) -> Dict:
    """Create a dictionary representing the directory structure"""
    structure = {}

    for root, dirs, files in os.walk(base_dir):
      # Get relative path
      rel_path = os.path.relpath(root, base_dir)
      current_dict = structure

      # Skip the base directory
      if rel_path != '.':
        # Split path into parts
        path_parts = rel_path.split(os.sep)

        # Build nested dictionary
        for part in path_parts:
          if part not in current_dict:
            current_dict[part] = {}
          current_dict = current_dict[part]

      # Add files
      docs = [f for f in files if f.endswith(('.pdf', '.md'))]
      if docs:
        current_dict['documents'] = docs

    return structure

  def process_directory(
    self,
    directory_path: str
  ) -> Dict[str, Any]:
    """Process all PDFs and Markdown files in a directory and its subdirectories"""

    processed_docs = []
    subjects = set()
    total_chunks = 0

    base_dir = os.path.abspath(directory_path)

    for root, _, files in os.walk(base_dir):
      for file in files:
        file_path = os.path.join(root, file)
        file_ext = os.path.splitext(file)[1].lower()

        if file_ext not in ['.pdf', '.md', '.json', '.txt']:
          continue

        subject = self.get_subject_from_path(file_path, base_dir)

        processed_doc = self.process_document(file_path, file_ext, subject)

        if not processed_doc:
          print(f"Warn: didn't get a processed doc for {directory_path}")
          continue

        processed_docs.append(processed_doc)
        total_chunks += len(processed_doc["chunks"])

        subjects.update(processed_doc["metadata"]["subjects"])

    print(subjects)
    # Create dataset with directory structure information
    dataset = {
        "metadata": {
            "creation_date": datetime.now(timezone.utc).isoformat(),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "total_documents": len(processed_docs),
            "total_chunks": total_chunks,
            "subjects": sorted(list(subjects)),
            "directory_structure": self.get_directory_structure(base_dir)
        },
        "documents": processed_docs
    }

    return dataset

  def process_document(
    self,
    file_path: str,
    file_ext: str,
    subject: str
  ) -> Dict[str, Any]:
    """Process a single document into chunks with metadata"""
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
          # loader = JSONLoader(file_path)
          # doc = loader.load()
          json_processor = JsonProcessor(file_path)
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

    # Extract basic metadata
    # source_path = doc.metadata.get("source", "")
    file_name = os.path.basename(file_path)
    file_type = os.path.splitext(file_name)[1].lower()

    # Process chunks with metadata
    processed_chunks = []
    unique_subjects = set()

    for i, doc in enumerate(chunks):
      chunk = doc.page_content
      metadata = doc.metadata
      # Generate unique chunk ID
      chunk_id = hashlib.md5(
        f"{file_name}_{i}_{chunk[:50]}".encode()).hexdigest()

      # Calculate chunk metrics
      # chunk_metrics = self.calculate_chunk_metrics(chunk)

      # Extra Metadata from config
      priority = 0
      for entry in self.config:
        if entry['document'] == file_name:
          priority = entry.get('priority')
          break

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
          heading_key = f'heading_{i}'
          if heading_key in metadata:
            headings.append(metadata[heading_key])
      # question

      processed_chunks.append({
          "chunk_id": chunk_id,
          "subjects": subjects,
          "headings": headings,
          "question": metadata.get('question'),
          "content": chunk,
          "metadata": {
              "chunk_number": i + 1,
              "char_length": len(chunk),
              "word_count": len(chunk.split()),
              "priority": priority + metadata.get('priority_score', 0)
              # "metrics": chunk_metrics
          }
      })

    # Create document entry
    processed_doc = {
        "doc_id": hashlib.md5(file_name.encode()).hexdigest(),
        "file_name": file_name,
        "file_type": file_type,
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

  # def evaluate_chunks():


if __name__ == "__main__":

  chunker = DocumentChunker(
      chunk_size=500,
      chunk_overlap=50
  )

  dataset = chunker.process_directory("../../data/documents")

  timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
  file_name = f"gin_lane_docs_v2_{timestamp}.json"

  DocumentUtils.save_to_json(dataset, f"../../data/json/{file_name}")

  # Print summary
  print("\nProcessing Summary:")
  print(f"Total Documents: {dataset['metadata']['total_documents']}")
  print(f"Total Chunks: {dataset['metadata']['total_chunks']}")
  print("\nSubjects found:")
  for subject in dataset['metadata']['subjects']:
    print(f"- {subject}")

  # evaluation = chunker.evaluate_chunks(dataset)

  # with open("./evaluation/chunk_evaluation.json", "w") as f:
  #     json.dump(evaluation, f, indent=2)
