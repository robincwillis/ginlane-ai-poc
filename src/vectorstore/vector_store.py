import os
import logging
import numpy as np

from dotenv import load_dotenv
from typing import List, Dict, Tuple, Optional, Any
import asyncio
import json
from dataclasses import dataclass, asdict

from documents.document_utils import DocumentUtils

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
    debug_output_file: str = None,
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY"),
    voyage_api_key: str = os.getenv("VOYAGE_API_KEY"),
    dimension: int = 1024,  # Voyage AI's default dimension
    weight_factor: float = 2.0,
    relationship_boost=1.5,
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
    self.debug_output_file = debug_output_file

    self.embeddings = LangchainVoyageEmbeddings(
      voyage_api_key=voyage_api_key,
      model="voyage-2"
    )

    self.voyage_client = voyageai.Client(api_key=voyage_api_key)

  def calculate_relationships(
    self,
    metadata,
    chunks: List[Dict]
  ):
    """Calculate relationship strength between a chunk and related chunks"""
    # print("calculate relationships")
    chunk_id = metadata['id']
    related_chunks = metadata.get('related_chunks', [])
    relationship_strength = 1.0  # Base strength

    if related_chunks:
      # print('Related chunks:', related_chunks)
      relationship_strength = 0.2 * len(related_chunks)
    else:
      for chunk in chunks:
        if chunk_id in chunk.get('related_chunks', []):
          # print("chunk_id is related_chunks")
          # print(chunk)
          related_chunks.append(chunk['id'])
          # Boost strength based on number of related questions
          relationship_strength += 0.2
        # if client or service, then boost strength

    if related_chunks:
      # print('Related chunks:', related_chunks)
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
    content_type = chunk.get('content_type')

    content = chunk['content']

    # Weighted text construction strategy
    enhanced_text = f"""
      {'Headings: ' + headings if headings else ''}
      {'Subjects: ' + subjects if subjects else ''}
      {'Services: ' + services if services else ''}
      {'Client: ' + client_name if client_name else ''}
      {'Content Type: ' + content_type if content_type else ''}
      Content: {content}
    """.strip()

    enhanced_text = "\n".join(
      line for line in enhanced_text.split("\n") if line.strip())
    return enhanced_text

  def flatten_metadata(self, metadata):
    """
    Flattens nested metadata structure to be compatible with Pinecone.
    Preserves references by converting them to lists of strings.

    Args:
        metadata (dict): The original metadata structure

    Returns:
        dict: Flattened metadata with only Pinecone-compatible values
    """
    flattened = {}

    # First, preserve all top-level fields that aren't nested dicts
    for key, value in metadata.items():
      if key not in ["document_metadata", "chunk_metadata"]:
        # Only copy if the value is Pinecone-compatible
        if isinstance(value, (str, int, float, bool)) or (
            isinstance(value, list) and all(isinstance(x, str) for x in value)
        ):
          flattened[key] = value

    # Handle document metadata
    if "document_metadata" in metadata:
      doc_meta = metadata["document_metadata"]

      # Convert references to list of URLs
      if "references" in doc_meta:
        flattened["reference_urls"] = [
            ref["url"] for ref in doc_meta["references"] if "url" in ref
        ]
        # Optionally preserve descriptions as separate list
        flattened["reference_descriptions"] = [
            ref["description"] for ref in doc_meta["references"] if "description" in ref
        ]

    # Handle media elements
    if "media_elements" in metadata:
      media_elements = metadata["media_elements"]
      flattened["media_urls"] = [
          media["url"] for media in media_elements if "url" in media
      ]
      flattened["media_types"] = [
          media["type"] for media in media_elements if "type" in media
      ]

      flattened["media_texts"] = [
          media["text"] for media in media_elements if "text" in media
      ]
    # Handle chunk metadata - these are already simple types
    if "chunk_metadata" in metadata:
      chunk_meta = metadata["chunk_metadata"]
      flattened["position"] = chunk_meta.get("position", 0)
      flattened["total_media_elements"] = chunk_meta.get(
        "total_media_elements", 0)

    return flattened

  def load_documents(self, data) -> Tuple[List[str], List[Dict]]:

    # TODO Improve documents chunking, formatting etc.
    texts = []
    metadatas = []
    for chunk in data:
      metadata = self.flatten_metadata(chunk['metadata'])
      text = self.prepare_text(chunk)
      metadata['text'] = text
      metadata['id'] = chunk['chunk_id']

      # Add other metadata fields conditionally
      question = chunk.get('question')
      if question is not None:
        metadata['question'] = question
      services = chunk.get('services')
      if services is not None:
        metadata['services'] = services
      subjects = chunk.get('subjects')
      if subjects is not None:
        metadata['subjects'] = subjects

      categories = chunk.get('categories')
      if categories is not None:
        metadata['categories'] = categories

      texts.append(text)
      metadatas.append(metadata)

    return texts, metadatas

  def enhance_metadata(
    self,
    metadata: Dict,
    chunk_relationships: Optional[ChunkRelation] = None,
    max_relationship_strength: float = 5.0
  ):
    enhanced = metadata.copy()

    if chunk_relationships:
      enhanced.update({
        'related_chunks': chunk_relationships.relationship_ids,
        'relationship_strength': chunk_relationships.relationship_strength,
      })

      # Adjust priority based on relationships
      raw_priority = enhanced['priority'] * \
          chunk_relationships.relationship_strength
      # Normalize by dividing by maximum possible value
      # Maximum possible value would be 1.0 * max_relationship_strength
      normalized_priority = raw_priority / max_relationship_strength

      # Ensure we don't exceed 1.0 due to floating point arithmetic
      if 'priority' in enhanced:
        enhanced['priority'] = min(normalized_priority, 1.0)

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

  async def upsert_documents(self, data, segment_size: int = 100, delay: float = 0.1, debug=False) -> List[str]:
    """
      Add documents to Pinecone index
      documents: List of dicts with 'text' and optional metadata
    """
    print(f"upsert_documents debug: {debug}")
    texts, metadatas = self.load_documents(data)

    chunk_relationships = None

    if metadatas:
      chunk_relationships = [
        self.calculate_relationships(
          metadata,
          data
        )
        for metadata in metadatas
      ]

    max_relationship_strength = max(
      relationship.relationship_strength
      for relationship in chunk_relationships
      if relationship is not None
    )

    ids = [
        metadata.get('id') or  # Use existing ID if provided
        metadata.get('chunk_id') or  # Fallback to document_id
        f"chunk_{i}"  # Default to incremental ID
        for i, metadata in enumerate(metadatas)
    ]

    weighted_embeddings = self.embed_documents(
      texts, metadatas, chunk_relationships)

    # Prepare vectors for upsert
    vectors = [
        {
            "id": id,
            "values": embedding,
            "metadata": self.enhance_metadata(
                metadata,
                relationship if chunk_relationships else None,
                max_relationship_strength
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

    if (debug):
      debug = [
        {
          "id": vector['id'],
          "metadata": vector['metadata']
        }
        for vector in vectors
      ]
      # save vectors sans values
      if self.debug_output_file:
        DocumentUtils.save_to_json(debug, self.debug_output_file)
      else:
        print("Warn: No debug output file")
      return debug
    else:
      def segment_list(lst: List[Any], segment_size: int):
        for i in range(0, len(lst), segment_size):
          yield lst[i:i + segment_size]

      # Upsert vectors in smaller segments
      upsert_responses = []
      for vector_segment in segment_list(vectors, segment_size):
        try:
          print("Inserting vector segement...")
          response = self.index.upsert(vector_segment)
          upsert_responses.append(response)
          await asyncio.sleep(delay)  # Add delay to avoid rate limiting

        except Exception as e:
          print(f"Error upserting segment: {str(e)}")

      return upsert_responses
      # upsert_response = self.index.upsert(vectors)
      # return upsert_response

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
