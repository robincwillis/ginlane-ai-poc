import json
from typing import List, Dict, Any
from langchain_core.documents import Document
# from sklearn.feature_extraction.text import TfidfVectorizer

from document_utils import DocumentUtils


class JsonProcessor:
  def __init__(self, json_path, priority_boost: float = 0.8):

    self.priority_boost = priority_boost
    # self.vectorizer = TfidfVectorizer()

    with open(json_path, 'r') as f:
      self.data = json.load(f)

  def process_document(self):
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
            'answer': test.get('correct_answer', '')
        })

    for qa in qa_data:
      question = qa.get('question', '')
      answer = qa.get('answer', '')
      content = f"Question: {question}\nAnswer: {answer}"
      # Calculate TF-IDF based relevance score
      # tfidf_score = max(self.vectorizer.transform([question]).toarray()[0])
      tfidf_score = 0

      chunk = Document(
        page_content=content,
        metadata={
            'id': DocumentUtils.generate_stable_id(content),
            'source': 'qa_dataset',
            'question_id': qa.get('question_id', ''),
            'subject': qa.get('subject', 'Unknown'),
            'subject_id': qa.get('subject_id', ''),
            'question': question,
            'priority_score': tfidf_score + self.priority_boost,
            'is_qa_chunk': True
        }
      )
      chunks.append(chunk)
    return chunks


if __name__ == "__main__":

  json_path = "../../data/json/evaluation_dataset_v1.json"
  json_processor = JsonProcessor(json_path)

  docs = json_processor.process_document()
  DocumentUtils.save_documents_to_json(docs, "test.json")
