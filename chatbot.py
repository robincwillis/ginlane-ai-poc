import os
from dotenv import load_dotenv
from anthropic import Anthropic
import logging
import streamlit as st
import json
import pandas as pd

from config import IDENTITY, MODEL, TOOLS
from tools import get_quote
from vectordb import VectorDB

# Load environment variables from .env file
load_dotenv()

# logging.basicConfig(level=logging.DEBUG,
#                     format='%(asctime)s - %(levelname)s - %(message)s')


class ChatBot:
  def __init__(self, session_state):
    self.anthropic = Anthropic()
    self.session_state = session_state
    self.vector_db = VectorDB(name="ginlane_docs")
    self.vector_db.load_db()

  def generate_message(
    self,
    messages,
    max_tokens
  ):
    try:
      response = self.anthropic.messages.stream(
        model=MODEL,
        system=IDENTITY,
        max_tokens=max_tokens,
        messages=messages,
        tools=TOOLS
      )
      return response
    except Exception as e:
      return {"error": str(e)}

  def process_user_input(self, user_input):
    self.session_state.display_messages.append(
      {"role": "user", "content": user_input})
    # self.session_state.messages.append({"role": "user", "content": user_input})

    search_results = self.vector_db.search(user_input)
    if search_results:
      with st.expander("Search Results"):
        st.json(search_results, expanded=False)
        extracted_results = [
            {
                "subject": result['metadata']['subject'],
                "content": result['metadata']['content'],
                "similarity": result['similarity']
            }
            for result in search_results
        ]
        df = pd.DataFrame(extracted_results)
        st.dataframe(df, use_container_width=True)

      sorted_results = sorted(
          search_results,
          key=lambda x: float(x['similarity']),
          reverse=True
      )

      top_chunk = sorted_results[0]['metadata']

      with st.expander("Top Chunk"):
        formatted_chunk = json.dumps(top_chunk, indent=4)
        st.code(formatted_chunk, language="json")

      # embeddeding = self.vector_db.get_embedding_by_chunk_number(top_chunk)
      # logging.debug(f"embedded_text: {embedded_text}")
      # st.write(f"embedded_text: {embedded_text}")
      embedded_text = top_chunk['content']

      content = embedded_text.split("Text:", 1)[1].strip(
      ) if "Text:" in embedded_text else embedded_text

      response_text = content
      # self.session_state.messages.append(
      #   {"role": "assistant", "content": response_text})

    else:
      response_text = "No relevant documents found."
      # self.session_state.messages.append(
      #   {"role": "assistant", "content": response_text})

    # Include the response from the vector database as context for the LLM
    # context_message = {"role": "system",
    #                   "content": f"Context: {response_text}"}

    # Prepare messages for the LLM
    context_message = {"role": "user", "content": (
        f"Based on the following context, please provide a response to the user's question. "
        f"Context: <context>{response_text}<context>\n\n"
        f"User's question: <question>{user_input}</question>"
    )}

    with st.expander("Context Message"):
      st.write(context_message['content'])

    self.session_state.api_messages.append(context_message)

    stream_response = self.generate_message(
      messages=self.session_state.api_messages,
      max_tokens=2048
    )

    if isinstance(stream_response, dict) and "error" in stream_response:
      return f"process_user_input:error: {stream_response['error']}"

    return stream_response

  def handle_tool_use(self, func_name, func_params):
    if func_name == "get_quote":
      premium = get_quote(**func_params)
      return f"Quote generated: ${premium: .2f} per month"

    raise Exception(f"An unexpected tool was used: {func_name}")
