import json
from typing import List, Dict, Tuple
import re
import asyncio

from documents.document_utils import DocumentUtils

# from documents.document_chunker import DocumentChunker
# from documents.project_chunker import ProjectChunker

from vectorstore.vector_store import VectorStore


class ChunkPreparationService:

  def __init__(self,
               questions_file: str,
               services_file: str,
               documents_file: str,
               projects_file: str,
               ):
    """ Go through and build relationships then embeddings """

    self.questions = DocumentUtils.load_from_json(questions_file)
    self.services = DocumentUtils.load_from_json(services_file)
    self.documents = DocumentUtils.load_from_json(documents_file)
    self.projects = DocumentUtils.load_from_json(projects_file)

    self.chunks = []
    for document in self.documents['documents']:
      for chunk in document['chunks']:
        self.chunks.append(chunk)

    for document in self.projects['documents']:
      for chunk in document['chunks']:
        self.chunks.append(chunk)

  def find_relevant_chunks(self, text: str, overlap: float = 0.3) -> List[str]:
    """Find relevant chunks for a peice of text"""

    relevant_chunk_ids = []
    for chunk in self.chunks:
      should_include = False
      chunk_content = chunk.get('content', '').lower()
      chunk_client = chunk.get('client_name', '').lower()

      if chunk_client and chunk_client in text:
        should_include = True

      content_words = set(re.findall(r'\b\w+\b', chunk_content))
      test_words = set(re.findall(r'\b\w+\b', text))

      # Calculate word overlap ratio
      if len(content_words) > 0 and len(test_words) > 0:
        overlap = len(content_words.intersection(test_words))
        content_ratio = overlap / len(content_words)

        # If there's significant word overlap (adjust threshold as needed)
        if content_ratio > overlap:  # 30% overlap threshold
          should_include = True

      if should_include:
        relevant_chunk_ids.append(chunk['chunk_id'])

    return relevant_chunk_ids

  def update_questions_with_chunks(self) -> List[Dict]:
    """Update questions with relevant chunks"""
    for entry in self.questions:
      for question in entry['tests']:
        answer = question.get('correct_answer', '').lower()
        chunk_ids = self.find_relevant_chunks(answer)
        question['correct_chunks'] = chunk_ids

    return self.questions

  def find_relevant_projects(self, text: str) -> List[str]:
    correct_chunks = []
    project_ids = []
    client_ids = []
    for chunk in self.chunks:
      if text in chunk['services']:
        correct_chunks.append(chunk['chunk_id'])
        project_ids.append(chunk['project_id'])
        client_ids.append(chunk['client_id'])

    return correct_chunks, project_ids, client_ids

  def update_services_with_chunks(self) -> List[Dict]:
    """Update services with relevant chunks"""

    for service in self.services:
      correct_chunks, project_ids, client_ids = self.find_relevant_projects(
        service['title'])

      service['correct_chunks'] = correct_chunks
      service['project_ids'] = list(set(project_ids))
      service['client_ids'] = list(set(client_ids))
    return self.services

  def chunk_documents(self):
    """Chunk all documents into smaller pieces"""

    for document in self.documents['documents']:
      for chunk in document['chunks']:
        chunk_content = chunk['content']
        chunk['chunks'] = self.chunk_text(chunk_content)

    return self.documents

  async def embed_and_upsert(self):
    """Embed Upsert all documents"""

    vector_store = VectorStore('gin-lane-docs-v2')
    result = await vector_store.upsert_documents(self.chunks)


async def main():
  questions_file = "../../data/documents/Questions and Answers.json"
  services_file = "../../data/documents/Services.json"
  projects_file = "../../data/json/gin_lane_projects_v1.json"
  documents_file = "../../data/json/gin_lane_docs_v3.json"

  embedding_prep_service = ChunkPreparationService(
    questions_file=questions_file,
    services_file=services_file,
    documents_file=documents_file,
    projects_file=projects_file
  )
  results = await embedding_prep_service.embed_and_upsert()

if __name__ == "__main__":
  asyncio.run(main())
  # documents_path = '../../data/json/gin_lane_docs_v2.json'
  # with open(documents_path, 'r') as f:
  #   data = json.load(f)

  # updated_services = embedding_prep_service.update_services_with_chunks()
  # update_questions = embedding_prep_service.update_questions_with_chunks()

  # DocumentUtils.save_to_json(update_questions, questions_file)
  # DocumentUtils.save_to_json(updated_services, services_file)

  output_file = "../../scrap/updated_questions.json"
