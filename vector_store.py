import os
import logging
from dotenv import load_dotenv
from typing import List, Dict, Tuple
import asyncio
import json

from langchain_community.vectorstores import Pinecone as LangchainPinecone
from langchain_community.embeddings import VoyageEmbeddings as LangchainVoyageEmbeddings
from pinecone import Pinecone, ServerlessSpec

load_dotenv()


class VectorStore:

  def __init__(
    self,
    index_name: str,
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY"),
    voyage_api_key: str = os.getenv("VOYAGE_API_KEY"),
    dimension: int = 1024  # Voyage AI's default dimension
  ):
    logging.debug("init")

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

    self.langchain_embeddings = LangchainVoyageEmbeddings(
      voyage_api_key=voyage_api_key,
      model="voyage-2"
    )

    self.vector_store = LangchainPinecone(
      self.index,
      self.langchain_embeddings,
      "text"  # text field in metadata
    )

  def load_documents(self, data) -> Tuple[List[str], List[Dict]]:

    # TODO Improve documents chunking, formatting etc.
    texts = []
    metadatas = []
    for document in data['documents']:
      for chunk in document['chunks']:
        subject = chunk['subject']
        content = chunk['content']
        metadata = chunk['metadata']
        text = f"Subject:{subject} Text: {content}"
        metadata['text'] = text
        texts.append(text)
        metadatas.append(metadata)
    return texts, metadatas

  async def upsert_documents(self, data) -> List[str]:
    """
      Add documents to Pinecone index
      documents: List of dicts with 'text' and optional metadata
    """
    texts, metadatas = self.load_documents(data)
    result = self.vector_store.add_texts(
      texts=texts,
      metadatas=metadatas
    )
    print("Documents added to Pinecone index.")
    return result

  # Return 3 most similar documents from the search.
  async def search_similar(self, query: str, k: int = 3) -> List[Dict]:
    results = self.vector_store.similarity_search_with_score(
      query=query,
      k=k
    )

    return [{
      'text': doc.page_content,
      'metadata': doc.metadata,
      'score': score
    } for doc, score in results]


async def main():
  documents_path = './data/json/gin_lane_docs.json'
  with open(documents_path, 'r') as f:
    data = json.load(f)

  vectorStore = VectorStore('gin-lane-docs-v1')
  result = await vectorStore.upsert_documents(data)
  print(result)

# './data/json/gin_lane_docs.json'
if __name__ == "__main__":
  asyncio.run(main())
