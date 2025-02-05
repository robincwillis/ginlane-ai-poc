import json
import matplotlib.pyplot as plt
import xml.etree.ElementTree as ET
from tqdm import tqdm
import logging
from typing import Callable, List, Dict, Any, Tuple, Set

evaluation_dataset = 'data/json/evaluation_dataset_v1.json'
docs_dataset = 'data/json/gin_lane_docs_v2.json'
# Load the evaluation dataset
with open(evaluation_dataset, 'r') as f:
  eval_data = json.load(f)


# Load the Anthropic documentation
with open(docs_dataset, 'r') as f:
  gl_docs = json.load(f)


def get_vector_db():
  """get the latest database from pinecone"""


def search_db(query, db):
  results = db.search(query, k=3)
  context = ""
  for result in results:
    chunk = result['metadata']
    context += f"\n{chunk['text']}\n"

  # Todo piece back together from dataset
  return results, context


def answer_query_base(query, db):
  documents, context = search_db(query, db)
  prompt = f"""
  You have been tasked with helping us to answer the following query:
  <query>
  {query}
  </query>
  You have access to the following documents which are meant to provide context as you answer the query:
  <documents>
  {context}
  </documents>
  Please remain faithful to the underlying context, and only deviate from it if you are 100% sure that you know the answer already.
  Answer the question now, and avoid providing preamble such as 'Here is the answer', etc
  """
  response = client.messages.create(
      model="claude-3-haiku-20240307",
      max_tokens=2500,
      messages=[
          {"role": "user", "content": prompt}
      ],
      temperature=0
  )
  return response.content[0].text


def calculate_mrr(retrieved_links: List[str], correct_links: Set[str]) -> float:
  for i, link in enumerate(retrieved_links, 1):
    if link in correct_links:
      return 1 / i
  return 0


def evaluate_retrieval(retrieval_function: Callable, evaluation_data: List[Dict[str, Any]], db: Any) -> Tuple[float, float, float, float, List[float], List[float], List[float]]:
  precisions = []
  recalls = []
  mrrs = []

  for i, item in enumerate(tqdm(evaluation_data, desc="Evaluating Retrieval")):
    try:
      retrieved_chunks, _ = retrieval_function(item['question'], db)
      retrieved_links = [chunk['metadata'].get(
        'chunk_link', chunk['metadata'].get('url', '')) for chunk in retrieved_chunks]
    except Exception as e:
      logging.error(f"Error in retrieval function: {e}")
      continue

    correct_links = set(item['correct_chunks'])

    true_positives = len(set(retrieved_links) & correct_links)
    precision = true_positives / len(retrieved_links) if retrieved_links else 0
    recall = true_positives / len(correct_links) if correct_links else 0
    mrr = calculate_mrr(retrieved_links, correct_links)

    precisions.append(precision)
    recalls.append(recall)
    mrrs.append(mrr)

    if (i + 1) % 10 == 0:
      print(f"Processed {i + 1}/{len(evaluation_data)} items. Current Avg Precision: {sum(precisions) / len(
        precisions):.4f}, Avg Recall: {sum(recalls) / len(recalls):.4f}, Avg MRR: {sum(mrrs) / len(mrrs):.4f}")

  avg_precision = sum(precisions) / len(precisions) if precisions else 0
  avg_recall = sum(recalls) / len(recalls) if recalls else 0
  avg_mrr = sum(mrrs) / len(mrrs) if mrrs else 0
  f1 = 2 * (avg_precision * avg_recall) / (avg_precision +
                                           avg_recall) if (avg_precision + avg_recall) > 0 else 0

  return avg_precision, avg_recall, avg_mrr, f1, precisions, recalls, mrrs


def evaluate_end_to_end(answer_query_function, db, eval_data):
  correct_answers = 0
  results = []
  total_questions = len(eval_data)

  for i, item in enumerate(tqdm(eval_data, desc="Evaluating End-to-End")):
    query = item['question']
    correct_answer = item['correct_answer']
    generated_answer = answer_query_function(query, db)

    prompt = f"""
    You are an AI assistant tasked with evaluating the correctness of answers to questions about Anthropic's documentation.

    Question: {query}

    Correct Answer: {correct_answer}

    Generated Answer: {generated_answer}

    Is the Generated Answer correct based on the Correct Answer? You should pay attention to the substance of the answer, and ignore minute details that may differ.

    Small differences or changes in wording don't matter. If the generated answer and correct answer are saying essentially the same thing then that generated answer should be marked correct.

    However, if there is any critical piece of information which is missing from the generated answer in comparison to the correct answer, then we should mark this as incorrect.

    Finally, if there are any direct contradictions between the correect answer and generated answer, we should deem the generated answer to be incorrect.

    Respond in the following XML format:
    <evaluation>
    <content>
    <explanation>Your explanation here</explanation>
    <is_correct>true/false</is_correct>
    </content>
    </evaluation>
    """

    try:
      response = client.messages.create(
          model="claude-3-5-sonnet-20241022",
          max_tokens=1500,
          messages=[
              {"role": "user", "content": prompt},
              {"role": "assistant", "content": "<evaluation>"}
          ],
          temperature=0,
          stop_sequences=["</evaluation>"]
      )

      response_text = response.content[0].text
      print(response_text)
      evaluation = ET.fromstring(response_text)
      is_correct = evaluation.find('is_correct').text.lower() == 'true'

      if is_correct:
        correct_answers += 1
      results.append(is_correct)

      logging.info(f"Question {i + 1}/{total_questions}: {query}")
      logging.info(f"Correct: {is_correct}")
      logging.info("---")

    except ET.ParseError as e:
      logging.error(f"XML parsing error: {e}")
      is_correct = 'true' in response_text.lower()
      results.append(is_correct)
    except Exception as e:
      logging.error(f"Unexpected error: {e}")
      results.append(False)

    if (i + 1) % 10 == 0:
      current_accuracy = correct_answers / (i + 1)
      print(f"Processed {
            i + 1}/{total_questions} questions. Current Accuracy: {current_accuracy:.4f}")
    # time.sleep(2)
  accuracy = correct_answers / total_questions
  return accuracy, results

# A question
# Chunks from our docs which are relevant to that question. This is what we expect our retrieval system to retrieve when the question is asked
# A correct answer to the question.

# We'll evaluate our system based on 5 key metrics:
# Precision
# Recall
# F1 Score
# Mean Reciprocal Rank (MRR)
# End-to-End Accuracy.
