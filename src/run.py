import argparse
import asyncio
from datetime import datetime, timezone

from documents.document_chunker import DocumentChunker
from documents.project_chunker import ProjectChunker
from documents.document_preparation import DocumentPreparation

from documents.document_utils import DocumentUtils
from vectorstore.vector_store import VectorStore

from config import INDEX, DOCS_FILE_NAME, PROJECTS_FILE_NAME


class WorkflowRunner:

  def __init__(self,
               document_prep: DocumentPreparation,
               document_chunker: DocumentChunker,
               project_chunker: ProjectChunker,
               vector_store: VectorStore,
               debug: bool = False
               ):

    self.document_prep = document_prep
    self.document_chunker = document_chunker
    self.project_chunker = project_chunker
    self.vector_store = vector_store
    self.debug = debug

  def prepare_services(self, file_name: str):
    """ Find and add relationship ids to services """
    print("Preparing services...")
    updated_services = self.document_prep.update_services_with_chunks()
    DocumentUtils.save_to_json(updated_services, file_name)

  def prepare_questions(self, file_name: str):
    """ Find and add relationship ids to questions """
    print("Preparing questions...")
    update_questions = self.document_prep.update_questions_with_chunks()
    DocumentUtils.save_to_json(update_questions, file_name)

  def chunk_documents(self, directory_path: str, file_name: str, print_summary: bool = True):
    """Chunk all documents"""
    print("Chunking projects...")
    dataset = self.document_chunker.process_directory(directory_path)
    DocumentUtils.save_to_json(dataset, file_name)

    if print_summary:
      print("\nProcessing Summary:")
      print(f"Total Documents: {dataset['metadata']['total_documents']}")
      print(f"Total Chunks: {dataset['metadata']['total_chunks']}")
      print("\nSubjects found:")
      for subject in dataset['metadata']['subjects']:
        print(f"- {subject}")

  def chunk_projects(self, directory_path: str, file_name: str, print_summary: bool = True):
    """Chunk all projects"""
    print("Chunking projects...")
    dataset = self.project_chunker.process_directory(directory_path)
    DocumentUtils.save_to_json(dataset, file_name)

    # Print summary
    if print_summary:
      print("\nProcessing Summary:")
      print(f"Total Documents: {dataset['metadata']['total_documents']}")
      print(f"Total Chunks: {dataset['metadata']['total_chunks']}")
      print("\nClients found:")
      for client in dataset['metadata']['clients']:
        print(f"- {client}")

  async def generate_embeddings(self):
    """Embed Upsert all documents"""
    print("Generating embeddings... TODO Break out into seperate workflow")

  async def upsert_documents(self):
    """Embed Upsert all documents"""
    print("Inserting documents into the vector store...")
    chunks = self.document_prep.get_all_chunks()
    result = await self.vector_store.upsert_documents(chunks, debug=self.debug)

  def debug(self):
    print("Debugging workflow...")
    # with open("./evaluation/chunk_evaluation.json", "w") as f:
    #     json.dump(evaluation, f, indent=2)

  def evaluate(self):
    print("Evaluating workflow...")


async def main():
  parser = argparse.ArgumentParser(description="Run different workflows")
  parser.add_argument("workflow", choices=[
                      "prepare", "chunk", "embed", "debug"], help="Select a workflow to run")

  timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

  questions_file = "../data/documents/Questions and Answers.json"
  services_file = "../data/documents/Services.json"

  documents_debug_file = f"../data/json/gin_lane_docs_debug_{timestamp}.json"
  projects_debug_file = f"../data/json/gin_lane_projects_debug_{timestamp}.json"

  projects_path = "../data/projects"
  documents_path = "../data/documents"

  projects_file = f"../data/json/{PROJECTS_FILE_NAME}"
  documents_file = f"../data/json/{DOCS_FILE_NAME}"
  index = INDEX  # 'gin-lane-docs-v2'

  document_config_file = '../data/document_config.json'
  project_config_file = '../data/project_config.json'
  client_config_file = '../data/client_config.json'

  debug_output_file = "../scrap/debug.json"

  args = parser.parse_args()

  # Classes

  document_prep = DocumentPreparation(
    questions_file=questions_file,
    services_file=services_file,
    documents_file=documents_file,
    projects_file=projects_file
  )
  project_chunker = ProjectChunker(
    project_config_file=project_config_file,
    client_config_file=client_config_file
  )

  document_chunker = DocumentChunker(
    document_config_file=document_config_file,
    chunk_size=500,
    chunk_overlap=50
  )

  vector_store = VectorStore(INDEX, debug_output_file=debug_output_file)

  runner = WorkflowRunner(
      document_prep=document_prep,
      document_chunker=document_chunker,
      project_chunker=project_chunker,
      vector_store=vector_store,
      debug=False
  )

  if args.workflow == "chunk":
    # Chunk all documents from the projects  / documents files
    runner.chunk_documents(documents_path, documents_file)
    runner.chunk_projects(projects_path, projects_file)

  elif args.workflow == "prepare":
    # Find and add relationship ids to questions and services
    runner.prepare_questions(questions_file)
    runner.prepare_services(services_file)

  elif args.workflow == "embed":
    embeddings = await runner.generate_embeddings()
    results = await runner.upsert_documents()
    print(results)
  elif args.workflow == "debug":
    runner.debug()
  elif args.workflow == "evaluate":
    runner.evaluate()

if __name__ == "__main__":
  asyncio.run(main())
