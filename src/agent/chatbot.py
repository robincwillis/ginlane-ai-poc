import sys
import os

from dotenv import load_dotenv
from anthropic import Anthropic
import logging
import asyncio
import streamlit as st
import json
import pandas as pd

from config import MODEL, SEARCH_K, MAX_TOKENS, STATIC_GREETINGS_AND_GENERAL, MAX_INPUT_TOKENS_PER_MINUTE, TOKEN_BUFFER, TOPICS
from agent.tools import get_quote

from vectorstore.vector_store import VectorStore
from agent.session_manager import SessionManager

# Load environment variables from .env file
load_dotenv()


class ChatBot:
  def __init__(self, identity, identity_on_topic, identity_off_topic, index, session_state):
    self.anthropic = Anthropic()
    self.session_state = session_state
    self.identity = identity
    self.identity_on_topic = identity_on_topic
    self.identity_off_topic = identity_off_topic
    self.topics = TOPICS
    self.max_tokens = MAX_TOKENS
    self.index = index
    self.vector_store = VectorStore(index_name=index)
    # self.vector_db.load_db() # For local dev
    self.session_manager = SessionManager(
      anthropic_client=self.anthropic,
      model=MODEL,
      # Adjust this based on your API plan limits
      max_tokens=MAX_INPUT_TOKENS_PER_MINUTE,
      token_buffer=TOKEN_BUFFER,  # Buffer before trimming history
      system_prompt=self.identity,
      session_state=session_state
    )

  async def initialize_conversation(self, greeting):
    """Initialize the conversation with system greeting and assistant acknowledgment."""
    if not hasattr(self.session_state, 'initialized') or not self.session_state.initialized:
      await self.session_manager.add_message("user", greeting, add_to_api=True, add_to_display=False)
      await self.session_manager.add_message("assistant", "Understood", add_to_api=True, add_to_display=False)
      self.session_state.initialized = True
    return self

  def stream_message(self, identity):
    try:

      messages = self.session_manager.get_api_messages()

      response = self.anthropic.messages.stream(
        model=MODEL,
        system=identity or self.identity,
        max_tokens=self.max_tokens,
        messages=messages,
        # tools=TOOLS
      )
      return response
    except Exception as e:
      return {"error": str(e)}

  def create_message(self, identity):
    try:
      messages = self.session_manager.get_api_messages()
      response = self.anthropic.messages.create(
        model=MODEL,
        system=identity or self.identity,
        max_tokens=self.max_tokens,
        messages=messages,
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
    images = []
    links = []
    references = []

    clean_filter = {k: v for k, v in filter.items() if v is not None}

    search_results = await self.vector_store.search_similar(search_input, SEARCH_K, filter=clean_filter)
    if search_results:
      images, links, references = self.get_media(search_results)

      with st.expander("📕 Relevant Documents"):
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

    else:
      context = "No relevant documents found."

    return context, images, links, references

  def get_system_prompt(self, input):
    input_lower = input.lower()
    for topic in self.topics:
      if topic.lower() in input_lower:
        logging.info('Using on Topic Identity...')
        return self.identity_on_topic

    # If no topics match, classify as off-topic
    logging.info('Using Off Topic Identity...')

    return self.identity_off_topic

  async def process_eval_input(self, input, filter):
    identity = self.get_system_prompt(input)

    context_text, images, links, references = await self.get_context(input, filter)

    context_message = {"role": "user", "content": (
        f"Answer the following question as clearly and naturally as possible, using the relevant details below.\n\n"
        f"{context_text}\n\n"
        f"Question: {input}"
    )}

    messages = [
        {'role': "user", "content": STATIC_GREETINGS_AND_GENERAL},
        {'role': "assistant", "content": "Understood"}
    ]

    messages.append(context_message)

    response = self.create_message(identity)

    return response

  async def process_user_input(self, user_input, filter):
    await self.session_manager.add_message("user", user_input, add_to_api=False, add_to_display=True)
    message = {"role": "user", "content": user_input}
    images = []
    links = []
    references = []

    identity = self.get_system_prompt(user_input)

    with st.expander("🧠 Identity"):
      st.write(identity)

    if identity == self.identity_on_topic:
      context_text, images, links, references = await self.get_context(user_input, filter)

      # Include the response from the vector database as context for the LLM
      context_message = {"role": "user", "content": (
          f"Answer the following question as clearly and naturally as possible, using the relevant details below.\n\n"
          f"{context_text}\n\n"
          f"Question: {user_input}"
        )}

      message["content"] = context_message["content"]
      with st.expander("🧩 Prompt with Context"):
        st.write(context_message['content'])

    # self.session_state.api_messages.append(context_message)
    await self.session_manager.add_message(
        role=message["role"],
        content=message["content"],
        add_to_api=True,
        add_to_display=False,
        is_context=True
    )

    stream_response = self.stream_message(identity)

    if isinstance(stream_response, dict) and "error" in stream_response:
      st.error(f"Error: {stream_response['error']}")
      return f"process_user_input: Error: {stream_response['error']}"

    return stream_response, images, links, references

  def handle_tool_use(self, func_name, func_params):
    if func_name == "get_quote":
      premium = get_quote(**func_params)
      return f"Quote generated: ${premium: .2f} per month"

    raise Exception(f"An unexpected tool was used: {func_name}")

  async def reset_conversation(self, greeting):
    """Reset the conversation history."""
    await self.session_manager.reset()
    await self.initialize_conversation(greeting)

  def get_token_stats(self):
    """Get current token usage statistics."""
    return self.session_manager.get_stats()
