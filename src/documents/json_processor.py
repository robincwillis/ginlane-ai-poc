import json
from typing import List, Dict, Any
from langchain_core.documents import Document
# from sklearn.feature_extraction.text import TfidfVectorizer

from document_utils import DocumentUtils


class JsonProcessor:
  def __init__(self, json_path, priority_boost: float = 0.8):

    self.priority_boost = priority_boost
    self.json_path = json_path
    # self.vectorizer = TfidfVectorizer()

    with open(json_path, 'r') as f:
      self.data = json.load(f)

  def process_services_document(self):
    chunks = []
    for service in self.data:
      service_id = service.get('id', '')
      service_title = service.get('title', '')
      content = service.get('description', '')
      related_chunks = service.get('correct_chunks', [])
      # Calculate TF-IDF based relevance score
      # tfidf_score = max(self.vectorizer.transform([content]).toarray()[0])
      tfidf_score = 0

      chunk = Document(
        page_content=content,
        metadata={
            'id': DocumentUtils.generate_stable_id(content),
            'source': self.json_path,
            'service_id': service_id,
            'service': service_title,
            'related_chunks': related_chunks,
            'priority_score': tfidf_score + self.priority_boost,
            'is_service_chunk': True
        }
      )
      chunks.append(chunk)
    return chunks

  def process_question_document(self):
    chunks = []
    qa_data = []

    for subject in self.data:
      subject_title = subject.get('title', 'Unknown Subject')
      subject_id = subject.get('id', '')
      for test in subject.get('tests', []):
        qa_data.append({
            'subject': subject_title,
            'subject_id': subject_id,
            'question_id': test.get('id', ''),
            'question': test.get('question', ''),
            'answer': test.get('correct_answer', ''),
            'related_chunks': test.get('correct_chunks', [])
        })

    for qa in qa_data:
      question = qa.get('question', '')
      answer = qa.get('answer', '')
      content = answer  # f"Question: {question}\nAnswer: {answer}"
      # Calculate TF-IDF based relevance score
      # tfidf_score = max(self.vectorizer.transform([question]).toarray()[0])
      tfidf_score = 0

      chunk = Document(
        page_content=content,
        metadata={
            'id': DocumentUtils.generate_stable_id(content),
            'source': self.json_path,
            'question_id': qa.get('question_id', ''),
            'subject': qa.get('subject', 'Unknown'),
            'subject_id': qa.get('subject_id', ''),
            'related_chunks': qa.get('related_chunks', []),
            'question': question,
            'priority_score': tfidf_score + self.priority_boost,
            'is_qa_chunk': True
        }
      )
      chunks.append(chunk)
    return chunks

  def process_document(self):
    print(f"Warning: No generic json processor yet for: {self.json_path}")

    return []


if __name__ == "__main__":

  # json_path = "../../data/documents/Services.json"

  # json_path = "../../data/json/evaluation_dataset_v1.json"

  json_path = "../../data/documents/Questions and Answers.json"

  json_processor = JsonProcessor(json_path)

  docs = json_processor.process_question_document()

  DocumentUtils.save_documents_to_json(docs, "test.json")
