import sys
import os

from dotenv import load_dotenv
from anthropic import Anthropic
import logging
import streamlit as st
import json
import pandas as pd

from config import MODEL, TOOLS
from agent.tools import get_quote

from vectorstore.vector_store import VectorStore

# Load environment variables from .env file
load_dotenv()


class ChatBot:
  def __init__(self, identity, index, session_state):
    self.anthropic = Anthropic()
    self.session_state = session_state
    self.identity = identity
    self.vector_store = VectorStore(index_name=index)
    # self.vector_db.load_db() # For local dev

  def generate_message(
    self,
    messages,
    max_tokens
  ):
    try:
      response = self.anthropic.messages.stream(
        model=MODEL,
        system=self.identity,
        max_tokens=max_tokens,
        messages=messages,
        # tools=TOOLS
      )
      return response
    except Exception as e:
      return {"error": str(e)}

  async def get_context(self, search_input, filter):
    clean_filter = {k: v for k, v in filter.items() if v is not None}
    search_results = await self.vector_store.search_similar(search_input, filter=clean_filter)
    if search_results:
      with st.expander("📕 Relevant Documents"):
        logging.info(search_results)
        st.json(search_results, expanded=False)
        extracted_results = [
            {
                # "subject": result['metadata']['subject'],
                "text": text,
                "topics": metadata.get("subjects", []),
                "services": metadata.get("services", []),
                "tags": metadata.get("tags", []),
                "priority": metadata["priority"],
                "score": score,
            }
            for text, score, metadata in search_results
        ]
        df = pd.DataFrame(extracted_results)
        st.dataframe(df, use_container_width=True)

      with st.expander("📖 Media"):
        images = [
          {
            "count": total_media_elements
          }
          for metedata in search_results
        ]
      with st.expander("📖 References"):

      context = "\n".join(
        [f"{text}\n\n" for text, score, metadata in search_results])

      # content = embedded_text.split("Text:", 1)[1].strip(
      # ) if "Text:" in embedded_text else embedded_text

      # response_text = content

    else:
      context = "No relevant documents found."

    return context

  async def process_user_input(self, user_input, filter):
    self.session_state.display_messages.append(
      {"role": "user", "content": user_input})

    context_text = await self.get_context(user_input, filter)

    # Include the response from the vector database as context for the LLM
    context_message = {"role": "user", "content": (
        f"Based on the following context, please provide a response to the user's question. "
        f"Context: <context>{context_text}<context>\n\n"
        f"User's question: <question>{user_input}</question>"
    )}

    with st.expander("🧩 Prompt with Context"):
      st.write(context_message['content'])

    self.session_state.api_messages.append(context_message)

    stream_response = self.generate_message(
      messages=self.session_state.api_messages,
      max_tokens=2048
    )

    if isinstance(stream_response, dict) and "error" in stream_response:
      st.error(f"Error: {stream_response['error']}")
      return f"process_user_input: Error: {stream_response['error']}"

    return stream_response

  def handle_tool_use(self, func_name, func_params):
    if func_name == "get_quote":
      premium = get_quote(**func_params)
      return f"Quote generated: ${premium: .2f} per month"

    raise Exception(f"An unexpected tool was used: {func_name}")
