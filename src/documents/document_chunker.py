from langchain_community.document_loaders import PDFMinerLoader, UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict, Any
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import hashlib

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

  def get_subject_from_path(
    self,
    file_path: str,
    base_dir: str
  ) -> str:
    """Extract subject from the directory structure"""
    # Get relative path from base directory
    rel_path = os.path.relpath(os.path.dirname(file_path), base_dir)
    if rel_path == '.':
      return 'general'
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

        if file_ext not in ['.pdf', '.md']:
          continue

        subject = self.get_subject_from_path(file_path, base_dir)
        subjects.add(subject)

        try:
          if file_ext == '.pdf':
            loader = PDFMinerLoader(file_path)
          else:
            loader = UnstructuredMarkdownLoader(file_path)

          doc = loader.load()[0]

          processed_doc = self.process_document(doc, subject)
          processed_docs.append(processed_doc)
          total_chunks += len(processed_doc["chunks"])

        except Exception as e:
          print(f"Error processing {file_path}: {str(e)}")

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
    doc,
    subject: str
  ) -> Dict[str, Any]:
    """Process a single document into chunks with metadata"""

    # Extract basic metadata
    source_path = doc.metadata.get("source", "")
    file_name = os.path.basename(source_path)
    file_type = os.path.splitext(file_name)[1].lower()

    # Generate chunks
    chunks = self.text_splitter.split_text(doc.page_content)

    # Process chunks with metadata
    processed_chunks = []
    for i, chunk in enumerate(chunks):
      # Generate unique chunk ID
      chunk_id = hashlib.md5(
        f"{file_name}_{i}_{chunk[:50]}".encode()).hexdigest()

      # Calculate chunk metrics
      # chunk_metrics = self.calculate_chunk_metrics(chunk)

      processed_chunks.append({
          "chunk_id": chunk_id,
          "subject": subject,
          "content": chunk,
          "metadata": {
              "chunk_number": i + 1,
              "char_length": len(chunk),
              "word_count": len(chunk.split()),
              # "metrics": chunk_metrics
          }
      })

    # Create document entry
    processed_doc = {
        "doc_id": hashlib.md5(file_name.encode()).hexdigest(),
        "file_name": file_name,
        "file_type": file_type,
        "metadata": {
            "source_path": source_path,
            "subject": subject,
            "creation_date": datetime.now(timezone.utc).isoformat(),
            "total_chunks": len(chunks),
            "original_size": len(doc.page_content)
        },
        "chunks": processed_chunks
    }

    return processed_doc

  def save_to_json(self, dataset: Dict[str, Any], output_path: str):
    """Save processed dataset to JSON file"""
    with open(output_path, 'w', encoding='utf-8') as f:
      json.dump(dataset, f, indent=2, ensure_ascii=False)

  def load_from_json(self, input_path: str) -> Dict[str, Any]:
    """Load dataset from JSON file"""
    with open(input_path, 'r', encoding='utf-8') as f:
      return json.load(f)

  # def calculate_chunk_metrics():

    # def evaluate_chunks():


if __name__ == "__main__":

  chunker = DocumentChunker(
      chunk_size=500,
      chunk_overlap=50
  )

  dataset = chunker.process_directory("./data/documents")

  chunker.save_to_json(dataset, "./data/json/gin_lane_docs.json")

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
