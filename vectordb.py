import os
import pickle
import json
import numpy as np
import voyageai
import time

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class VectorDB:

  def __init__(self, name, api_key=None):
    if api_key is None:
      api_key = os.getenv("VOYAGE_API_KEY")

    self.client = voyageai.Client(api_key=api_key)
    self.name = name
    self.embeddings = []
    self.metadata = []
    self.query_cache = {}
    self.db_path = f"./data/db/{name}/vector_db.pkl"

  def load_data(self, data):
    if self.embeddings and self.metadata:
      print("Vector database is already loaded. Skipping data loading.")
      return
    if os.path.exists(self.db_path):
      print("Loading vector database from disk")
      self.load_db()

    # texts = [f"Heading: {item['chunk_heading']}\n\n Chunk Text:{item['text']}" for item in data]
    # texts = [f"Subject:{item['metadata']['subject']} Text": {item['content']}]
    texts = []

    # Loop through each document and chunk
    for document in data['documents']:
      for chunk in document['chunks']:
        subject = chunk['metadata']['subject']
        content = chunk['content']
        text = f"Subject:{subject} Text: {content}"
        texts.append(text)

    self._embed_and_store(texts, data)
    self.save_db()
    print("Vector database loaded and saved.")

  def _embed_and_store(self, texts, data):
    batch_size = 128
    result = []
    for i in range(0, len(texts), batch_size):
      result.append(
        self.client.embed(
          texts[i: i + batch_size],
          model="voyage-2"
        ).embeddings
      )
      # Add a delay of 1 second between each call to avoid rate limits
      time.sleep(1)
    self.embeddings = [embedding for batch in result for embedding in batch]
    self.metadata = data

  def search(self, query, k=5, similarity_threshold=0.75):
    if query in self.query_cache:
      query_embedding = self.query_cache[query]
    else:
      query_embedding = self.client.embed(
        [query], model="voyage-2").embeddings[0]
      self.query_cache[query] = query_embedding

    if not self.embeddings:
      raise ValueError("No data loaded in the vector database.")

    simliarities = np.dot(self.embeddings, query_embedding)
    top_indices = np.argsort(simliarities)[::-1]
    top_examples = []

    for idx in top_indices:
      if simliarities[idx] >= similarity_threshold:
        if idx >= len(self.metadata):
          print(f"Index {idx} is out of bounds for metadata with length {
                len(self.metadata)}")
          continue
        example = {
          "metadata": self.metadata[idx],
          "similarity": simliarities[idx],
        }
        top_examples.append(example)

        if len(top_examples) >= k:
          break

    self.save_db()
    return top_examples

  def save_db(self):
    data = {
      "embeddings": self.embeddings,
      "metadata": self.metadata,
      "query_cache": json.dumps(self.query_cache),
    }

    os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    with open(self.db_path, "wb") as file:
      pickle.dump(data, file)

  def load_db(self):
    if not os.path.exists(self.db_path):
      raise ValueError(
        "Vector database file not found. use load_data to create a new database.")
    with open(self.db_path, "rb") as file:
      data = pickle.load(file)

    self.embeddings = data["embeddings"]
    self.metadata = data["metadata"]
    self.query_cache = json.loads(data["query_cache"])


if __name__ == "__main__":
  with open('./data/json/gin_lane_docs.json', 'r') as f:
    ginlane_docs = json.load(f)

  # Initialize the VectorDB
  db = VectorDB("ginlane_docs")
  db.load_data(ginlane_docs)
