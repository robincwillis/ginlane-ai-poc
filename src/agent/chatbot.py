import sys
import os

from dotenv import load_dotenv
from anthropic import Anthropic
import logging
import streamlit as st
import json
import pandas as pd

from config import MODEL, SEARCH_K
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

  def get_media(self, search_results):
    images = []
    links = []
    references = []
    # Process media items if they exist
    for search_result in search_results:
      _, _, metadata = search_result
      # Extract metadata links with pattern {meta_link: description}[url]
      media_urls = metadata.get('media_urls', [])
      media_types = metadata.get('media_types', [])
      media_texts = metadata.get('media_texts', [])

      # Ensure all media lists have the same length by padding with None if necessary
      max_media_length = max(
        len(media_urls), len(media_types), len(media_texts))
      media_urls = media_urls + [None] * (max_media_length - len(media_urls))
      media_types = media_types + [None] * \
          (max_media_length - len(media_types))
      media_texts = media_texts + [None] * \
          (max_media_length - len(media_texts))

      for i, (url, media_type, text) in enumerate(zip(media_urls, media_types, media_texts)):
        if url and media_type == 'image':
          images.append({
            'type': 'image',
            'position': i,
            'url': url,
            'text': text or ''  # Use empty string if text is None
          })
        elif url and media_type == 'link':
          links.append({
            'type': 'link',
            'position': i,
            'url': url,
            'text': text or ''  # Use empty string if text is None
          })

      reference_descriptions = metadata.get('reference_descriptions', [])
      reference_urls = metadata.get('reference_urls', [])

      max_reference_length = max(
        len(reference_urls), len(reference_descriptions))
      reference_urls = reference_urls + \
          [None] * (max_reference_length - len(reference_urls))
      reference_descriptions = reference_descriptions + \
          [None] * (max_reference_length - len(reference_descriptions))

    for i, (url, description) in enumerate(zip(reference_urls, reference_descriptions)):
      if url:  # Only add if URL exists
        references.append({
            'type': 'reference',
            'position': i,
            'url': url,
            'text': description or ''  # Use empty string if text is None
        })

    return (images, links, references)

  async def get_context(self, search_input, filter):
    clean_filter = {k: v for k, v in filter.items() if v is not None}
    search_results = await self.vector_store.search_similar(search_input, SEARCH_K, filter=clean_filter)
    if search_results:
      images, links, references = self.get_media(search_results)

      with st.expander("📕 Relevant Documents"):
        logging.info(search_results)
        st.json(search_results, expanded=False)
        extracted_results = [
            {
                # "subject": result['metadata']['subject'],
                "text": text,
                "topics": metadata.get("subjects", []),
                "services": metadata.get("services", []),
                "categories": metadata.get("categories", []),
                "priority": metadata["priority"],
                "source": metadata["source"],
                "score": score,
            }
            for text, score, metadata in search_results
        ]
        df = pd.DataFrame(extracted_results)
        st.dataframe(df, use_container_width=True)

      if images or links:
        with st.expander("🖌️ Media"):
          image_df = pd.DataFrame(images)
          st.dataframe(image_df, use_container_width=True)
          link_df = pd.DataFrame(links)
          st.dataframe(link_df, use_container_width=True)

      if references:
        with st.expander("📖 References"):
          df = pd.DataFrame(references)
          st.dataframe(references, use_container_width=True)

      context = "\n".join(
        [f"{text}\n\n" for text, score, metadata in search_results])

      # content = embedded_text.split("Text:", 1)[1].strip(
      # ) if "Text:" in embedded_text else embedded_text

      # response_text = content

    else:
      context = "No relevant documents found."

    return context, images, links, references

  async def process_user_input(self, user_input, filter):
    self.session_state.display_messages.append(
      {"role": "user", "content": user_input})

    context_text, images, links, references = await self.get_context(user_input, filter)

    # Include the response from the vector database as context for the LLM
    context_message = {"role": "user", "content": (
        f"Answer the following question as clearly and naturally as possible, using the relevant details below.\n\n"
        f"{context_text}\n\n"
        f"Question: {user_input}"
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

    return stream_response, images, links, references

  def handle_tool_use(self, func_name, func_params):
    if func_name == "get_quote":
      premium = get_quote(**func_params)
      return f"Quote generated: ${premium: .2f} per month"

    raise Exception(f"An unexpected tool was used: {func_name}")
