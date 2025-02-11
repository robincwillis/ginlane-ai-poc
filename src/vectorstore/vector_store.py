import os
import logging
import numpy as np

from dotenv import load_dotenv
from typing import List, Dict, Tuple, Optional
import asyncio
import json
from dataclasses import dataclass


# from langchain_community.vectorstores import Pinecone as LangchainPinecone
# from langchain.embeddings.base import Embeddings

from langchain_voyageai import VoyageAIEmbeddings as LangchainVoyageEmbeddings

from pinecone import Pinecone, ServerlessSpec
import voyageai

load_dotenv()

logging.getLogger("pinecone").setLevel(logging.WARNING)
logging.getLogger("pinecone_plugin_interface").setLevel(logging.WARNING)
logging.getLogger(
  "pinecone_plugin_interface.logging").setLevel(logging.WARNING)


@dataclass
class ChunkRelation:
  chunk_id: str
  relationship_ids: Optional[List[str]]
  relationship_strength: float
  relation_type: str  # e.g., "next", "previous", "parent", "child", "reference"


@dataclass
class ChunkMetadata:
  chunk_id: str
  project_id: str
  client_id: str
  # source_file: str
  # page_number: Optional[int] = None
  # section: Optional[str] = None
  # related_chunks: List[ChunkRelation] = field(default_factory=list)


class VectorStore:

  def __init__(
    self,
    index_name: str,
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY"),
    voyage_api_key: str = os.getenv("VOYAGE_API_KEY"),
    dimension: int = 1024,  # Voyage AI's default dimension
    weight_factor: float = 2.0,
    relationship_boost=1.5
  ):

    pc = Pinecone(api_key=pinecone_api_key)

    # Create new index if it doesn't exist
    if index_name not in pc.list_indexes().names():
      pc.create_index(
        name=index_name,
        dimension=dimension,
        metric='cosine',
        spec=ServerlessSpec(
          cloud='aws',
          region='us-east-1'
        )
      )

    self.index = pc.Index(index_name)
    self.weight_factor = weight_factor

    self.embeddings = LangchainVoyageEmbeddings(
      voyage_api_key=voyage_api_key,
      model="voyage-2"
    )

    self.voyage_client = voyageai.Client(api_key=voyage_api_key)

  def calculate_relationships(
    self,
    chunk_id,
    # questions: List[Dict],
    chunks: List[Dict]
  ):
    """Calculate relationship strength between a chunk and related questions"""

    related_chunks = []
    relationship_strength = 1.0  # Base strength
    for chunk in chunks:
      if chunk_id in chunk.get('correct_chunks', []):
        related_chunks.append(chunk['id'])
        # Boost strength based on number of related questions
        relationship_strength += 0.2
      # if client or service, then boost strength
    return ChunkRelation(
      chunk_id=chunk_id,
      relationship_ids=related_chunks,
      relationship_strength=relationship_strength,
      relation_type="reference"
    )

  def prepare_text(self, chunk):
    subjects = ", ".join(chunk.get('subjects', []))
    headings = ", ".join(chunk.get('headings', []))
    services = ", ".join(chunk.get('services', []))
    client_name = chunk.get('client_name')

    content = chunk['content']

    # Weighted text construction strategy
    enhanced_text = f"""
      {'Headings: ' + headings if headings else ''}
      {'Subjects: ' + subjects if subjects else ''}
      {'Services: ' + services if services else ''}
      {'Client: ' + client_name if client_name else ''}
      Content: {content}
    """.strip()

    enhanced_text = "\n".join(
      line for line in enhanced_text.split("\n") if line.strip())
    return enhanced_text

  def load_documents(self, data) -> Tuple[List[str], List[Dict]]:

    # TODO Improve documents chunking, formatting etc.
    texts = []
    metadatas = []
    for chunk in data:
      metadata = chunk['metadata']
      text = self.prepare_text(chunk)
      metadata['text'] = text
      metadata['id'] = chunk['chunk_id']
      metadata['question'] = chunk.get('question')
      metadata['services'] = chunk.get('services')
      metadata['subjects'] = chunk.get('subjects')
      metadata['tags'] = chunk.get('tags')
      texts.append(text)
      metadatas.append(metadata)

    return texts, metadatas

  def enhance_metadata(
    self,
    metadata: Dict,
    chunk_relationships: Optional[ChunkRelation] = None
  ):
    enhanced = metadata.copy()

    if chunk_relationships:
      enhanced.update({
        'related_chunks': chunk_relationships.relationship_ids,
        'relationship_strength': chunk_relationships.relationship_strength,
      })

      # Adjust priority based on relationships
      if 'priority' in enhanced:
        enhanced['priority'] = enhanced['priority'] * \
          chunk_relationships.relationship_strength

    print(enhanced)
    return enhanced

  def embed_documents(
    self,
    texts,
    metadatas=None,
    chunk_relationships: Optional[List[ChunkRelation]] = None
  ):
    # Calculate base priorities
    priorities = [
      metadata.get('priority', 0.5)
      for metadata in metadatas
    ]

    # Adjust priorities based on relationships
    if chunk_relationships:
      for i, relationship in enumerate(chunk_relationships):
        if relationship:
          priorities[i] *= relationship.relationship_strength

    base_embeddings = self.embeddings.embed_documents(texts)

    weighted_embeddings = []
    for embedding, priority in zip(base_embeddings, priorities):
      weight = np.exp(priority / self.weight_factor)
      weighted_embedding = np.array(embedding) * weight  # Scale vector
      weighted_embeddings.append(weighted_embedding.tolist())

    return weighted_embeddings

  async def upsert_documents(self, data) -> List[str]:
    """
      Add documents to Pinecone index
      documents: List of dicts with 'text' and optional metadata
    """
    texts, metadatas = self.load_documents(data)

    chunk_relationships = None

    if data:
      chunk_relationships = [
        self.calculate_relationships(
          metadata.get('chunk_id'),
          data
        )
        for metadata in metadatas
      ]

    ids = [
        metadata.get('id') or  # Use existing ID if provided
        metadata.get('chunk_id') or  # Fallback to document_id
        f"chunk_{i}"  # Default to incremental ID
        for i, metadata in enumerate(metadatas)
    ]

    print(chunk_relationships)
    # return
    weighted_embeddings = self.embed_documents(
      texts, metadatas, chunk_relationships)

    # Prepare vectors for upsert
    vectors = [
        {
            "id": id,
            "values": embedding,
            "metadata": self.enhance_metadata(
                metadata,
                relationship if chunk_relationships else None
            )
        }
        for i, (embedding, metadata, id, relationship) in enumerate(
            zip(
              weighted_embeddings,
              metadatas,
              ids,
              (chunk_relationships if chunk_relationships else [
               None] * len(ids))
            )
        )
    ]

    upsert_response = self.index.upsert(vectors)
    return upsert_response

  async def search_similar(
    self,
      query: str,
    k: int = 5,
    filter=None,
    rerank=True,
    rerank_k=None
  ) -> List[Dict]:

    query_embedding = self.embeddings.embed_documents([query])[0]

    # Query Pinecone
    query_response = self.index.query(
      vector=query_embedding,
      top_k=k,
      include_metadata=True,
      filter=filter
    )

    # Process and return results
    results = []
    candidates = []
    texts = []
    metadatas = []
    scores = []

    for match in query_response.matches:
      text = match.metadata.get('text', 'Text not found')
      texts.append(text)
      metadatas.append(match.metadata)
      scores.append(match.score)
      candidates.append((text, match.score, match.metadata))

    # Apply reranking if requested
    if rerank and texts:
      # Get reranking scores
      rerank_reresponse = self.voyage_client.rerank(
        query=query,
        documents=texts,
        model="rerank-2",
        top_k=k
      )

      # Create reranked results
      reranked_results = []

      # Access the results through the results attribute
      for item in rerank_reresponse.results:
        idx = item.index
        reranked_results.append((
            texts[idx],
            item.relevance_score,  # Use reranking score
            metadatas[idx]
        ))

      return reranked_results

    # Return original results if no reranking
    return candidates[:k]

    # results = self.vector_store.similarity_search_with_score(
    #   query=query,
    #   k=k
    # )

    # return [{
    #   'text': doc.page_content,
    #   'metadata': doc.metadata,
    #   'score': score
    # } for doc, score in results]


async def embed_and_upsert(vector_store, data):

  result = await vector_store.upsert_documents(data)
  print(result)


async def search(vector_store):
  query = "What is your process for branding projects?"
  filter = {
    "subjects": "Branding and Positioning",
    "priority": {"$gte": 0.5}
  }

  results = await vector_store.search_similar(
    query=query,
    k=5,
    filter=filter,
    rerank=True,
    rerank_k=5  # Number of candidates to consider for reranking
  )

  # sorted_results = sorted(
  #     search_results,
  #     key=lambda x: float(x['similarity']),
  #     reverse=True
  # )

  # Print results
  print(f"\nSearch results for query: '{query}'")
  for text, score, metadata in results:
    print(f"\nText: {text}")
    print(f"Score: {score:.4f}")
    print(f"Metadata: {metadata}")


async def main():
  vector_store = VectorStore('gin-lane-docs-v2')

  await embed_and_upsert(vector_store)
  # await search(vector_store)


# './data/json/gin_lane_docs.json'
if __name__ == "__main__":
  asyncio.run(main())
