
from typing import Dict, List, Any, Optional
import uuid
import logging
import asyncio
import streamlit as st
from agent.chatbot import ChatBot
from config import MODEL, IDENTITY, INDEX, TOPICS, STATIC_GREETINGS_AND_GENERAL, SEARCH_K

logging.basicConfig(level=logging.INFO)


def initialize_contexts() -> Dict[str, str]:
  """Initialize default context values if they don't exist in session state"""
  if 'identity' not in st.session_state:
    st.session_state.identity = IDENTITY
  if 'contexts' not in st.session_state:
    st.session_state.contexts = {
        'greeting_and_general': STATIC_GREETINGS_AND_GENERAL,
    }
  if 'topics' not in st.session_state:
    st.session_state.topics = TOPICS
    st.session_state.topic_filter = "All"

  if 'priority_filter' not in st.session_state:
    st.session_state.priority_filter = 0.3

  if 'filter' not in st.session_state:
    st.session_state.filter = {
      "subjects": None,
      "priority": {"$gte": 0.3}
    }

  return st.session_state.contexts


def initialize_session_state():
  if "display_messages" not in st.session_state:
    st.session_state.display_messages = []
  if "api_messages" not in st.session_state:
    st.session_state.api_messages = []
  if "token_usage" not in st.session_state:
    st.session_state.token_usage = 0
  if "message_tokens" not in st.session_state:
    st.session_state.message_tokens = []
  if "initialized" not in st.session_state:
    st.session_state.initialized = False


async def initialize_chatbot():
  initialize_session_state()
  # initialize chatbot with new identity
  chatbot = ChatBot(st.session_state.identity, INDEX, st.session_state)

  if not st.session_state.initialized:
    await chatbot.initialize_conversation(combine_contexts())
    st.session_state.initialized = True

  st.toast("I'm up!", icon="🏄🏽‍♀️")
  return chatbot


def combine_contexts() -> str:
  """Combine all contexts into a single message"""
  contexts = st.session_state.contexts
  context_texts = [v for k, v in contexts.items()]
  return "\n\n".join(context_texts)


def delete_context(key: str):
  """Delete a context and trigger a rerun"""
  del st.session_state.contexts[key]

  # Reset initialization flag to rebuild conversation
  st.session_state.initialized = False
  if 'chatbot' in st.session_state:
    del st.session_state.chatbot

  st.toast("Context deleted and chat state reset!", icon="✅")
  st.rerun()


def update_priority_filter(value):
  if value != st.session_state.priority_filter:
    st.session_state["priority_filter"] = value
    st.session_state["filter"]["priority"] = {"$gte": value}


def update_topic_filter(value):
  if value != st.session_state.priority_filter:
    st.session_state["topic_filter"] = value
    if value != "All":
      st.session_state["filter"]["subjects"] = value
    else:
      st.session_state["filter"]["subjects"] = None


def context_manager(contexts):
  """Create a management interface for context texts"""

  keys_to_remove = []
  with st.sidebar:
    st.header("Search Settings")

    selected_topic = st.selectbox(
      "Filter by Topic",
      st.session_state.topics,
    )
    update_topic_filter(selected_topic)

    priority_filter = st.slider(
      "Priority Threshold",
      0.0,
      1.0,
      0.5,
      0.1,
    )
    update_priority_filter(priority_filter)

    st.header("Agent Context")
    # Identity input (separate from contexts)
    new_identity = st.text_area(
        "**Identity**",
        value=st.session_state.identity,
        key="identity_input",
        height=250,

    )

    identity_changed = new_identity != st.session_state.identity

    col1, col2 = st.columns([8, 4])

    with col2:
      if st.button("Update", key=f"update_identity", type="primary", use_container_width=True, disabled=identity_changed != True):
        if identity_changed:
          st.session_state.identity = new_identity
          st.session_state.initialized = False
          if 'chatbot' in st.session_state:
            del st.session_state.chatbot
          st.toast("Identity updated and chat state reset!", icon="✅")
          st.rerun()  # Add this to force a rerun

    # Container for context editors
    context_editors = st.container()

    # Add new context button
    if st.button("Add New Context"):
      new_key = f"context_{str(uuid.uuid4())[:8]}"
      contexts[new_key] = ""
      st.session_state.contexts = contexts

    # Create text areas for each context
    with context_editors:
      for key, value in contexts.items():
        new_context = st.text_area(
            f"**{key.replace('_', ' ').title()}**",
            value=value,
            key=f"textarea_{key}",
            height=320,
        )
        context_changed = st.session_state.contexts[key] != new_context

        col1, col2, col3 = st.columns([6, 4, 2])
        with col2:
          if st.button(
            "Update",
            key=f"update_{key}",
            type="primary",
            use_container_width=True,
            disabled=context_changed != True
          ):
            if context_changed:
              st.session_state.contexts[key] = new_context
              st.session_state.initialized = False
              if 'chatbot' in st.session_state:
                del st.session_state.chatbot
              st.toast("Context updated and chat state reset!", icon="✅")
              st.rerun()

        with col3:
          if st.button("🗑️", key=f"delete_{key}", use_container_width=True):
            keys_to_remove.append(key)

    # Token stats section at the bottom of sidebar
    if 'chatbot' in st.session_state:
      st.header("Token Usage")
      token_stats = st.session_state.chatbot.get_token_stats()

      st.metric(
        "Token Usage", f"{token_stats['current_usage']} / {token_stats['max_tokens']}")
      progress_val = min(
        1.0, token_stats['current_usage'] / token_stats['max_tokens'])
      st.progress(progress_val)

      # Display more detailed stats
      col1, col2 = st.columns(2)
      with col1:
        st.write(f"Messages: {token_stats['message_count']}")
        st.write(f"Used: {token_stats['percent_used']}%")
      with col2:
        st.write(f"Remaining: {token_stats['remaining_tokens']}")

      # Reset conversation button
      if st.button("Reset Conversation"):
        # Reset session and reinitialize
        st.session_state.display_messages = []
        st.session_state.api_messages = []
        st.session_state.message_tokens = []
        st.session_state.token_usage = 0
        st.session_state.initialized = False
        if 'chatbot' in st.session_state:
          st.session_state.chatbot.reset_conversation(combine_contexts())
          del st.session_state.chatbot
        st.toast("Conversation has been reset!", icon="🔄")
        st.rerun()

    st.write(f"Model: {MODEL}")
    st.write(f"Index: {INDEX}")
    st.write(f"Search K: {SEARCH_K}")

  for key in keys_to_remove:
    delete_context(key)


def create_markdown_media_summary(images, links, references):
  """
  Create a markdown-formatted summary of all media items.
  """
  summary_parts = []

  # Add double newline before starting media summary
  if any([images, links, references]):
    summary_parts.append("\n\n")

  # Add images section if there are any
  if images:
    summary_parts.append("🖼️ **Images**\n")
    for img in images:
        # Format as markdown image with link
      summary_parts.append(f"[![{img['text']}]({img['url']})]({img['url']})\n")
      summary_parts.append(f"*{img['text']}*\n\n")

  # Add links section if there are any
  if links:
    summary_parts.append("🔗 **Links**\n")
    for link in links:
      # Format as markdown link with description
      summary_parts.append(f"* [{link['text']}]({link['url']})\n")
    summary_parts.append("\n")

  # Add references section if there are any
  if references:
    summary_parts.append("📖 **References**\n")
    for ref in references:
      # Format as markdown link with description
      summary_parts.append(f"* [{ref['text']}]({ref['url']})\n")
    summary_parts.append("\n")

  return "".join(summary_parts)


# def handle_stream_response(stream_response):
#   """Handle the streaming response and UI updates"""

#   input_tokens, output_tokens = 0, 0  # Initialize token counters
#   first_chunk = None  # To store the last chunk for token usage

#   try:
#     def stream_and_capture():
#       nonlocal first_chunk
#       with stream_response as stream:
#         for chunk in stream:
#           if chunk.type == "content_block_delta":
#             yield chunk.delta.text
#           if first_chunk is None:  # Capture the first chunk for token usage
#             first_chunk = chunk
#         # Stream the response while capturing the last chunk
#     full_response = st.write_stream(stream_and_capture())
#     # TODO Debug mode
#     # st.write(first_chunk)

#     if full_response is not None:
#       st.session_state.display_messages.append({
#           "role": "assistant",
#           "content": full_response
#       })
#       st.session_state.api_messages.append({
#           "role": "assistant",
#           "content": full_response
#       })

#       if first_chunk and hasattr(first_chunk, "usage"):
#         input_tokens = first_chunk.usage.input_tokens
#         output_tokens = first_chunk.usage.output_tokens
#         st.write(f"🔢 **Input Tokens:** {input_tokens}")
#         st.write(f"🔢 **Output Tokens:** {output_tokens}")

#   except Exception as e:
#     st.error(f"handle_stream_response:error: {str(e)}")
#     return None

#     # For Debugging
#     # with stream_response as stream:
#     #   full_response = ""
#     #   for chunk in stream:
#     #     if chunk.type == "content_block_delta":
#     #       text_chunk = chunk.delta.text
#     #       st.write(text_chunk)
#     #       full_response += text_chunk
#     #       # Debug statement to print each chunk
#     #       st.write(f"Chunk received: {text_chunk}")
#     #       print(f"Chunk received: {text_chunk}")
#     #   return full_response


async def handle_stream_response(stream_response, chatbot):
  """Handle the streaming response and UI updates"""
  try:
    def stream_and_capture():
      full_text = ""
      with stream_response as stream:
        for chunk in stream:
          if hasattr(chunk, 'type') and chunk.type == "content_block_delta" and hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text'):
            text_chunk = chunk.delta.text
            full_text += text_chunk
            yield text_chunk
      return full_text

    # Stream the response and capture the full text
    full_response = st.write_stream(stream_and_capture())

    if full_response is not None:
      # Add assistant response to both API and display messages via SessionManager
      await chatbot.session_manager.add_message(
          "assistant", full_response, add_to_api=True, add_to_display=True
      )

      # Display token usage stats
      token_stats = chatbot.get_token_stats()
      st.caption(
        f"Token usage: {token_stats['current_usage']} / {token_stats['max_tokens']} ({token_stats['percent_used']}%)")

  except Exception as e:
    st.error(f"Error handling stream response: {str(e)}")
    return None


async def main():
  st.set_page_config(page_icon=":penguin:",
                     page_title="Gin Lane AI", initial_sidebar_state='collapsed')

  st.title("Welcome to Gin Lane. 🌊")
  st.write(
    "We’re here to help you with any and all requests related to: ",
    "brand, ",
    "interactive, ",
    "positioning.",
  )

  contexts = initialize_contexts()
  if 'chatbot' not in st.session_state:
    st.session_state.chatbot = await initialize_chatbot()

  context_manager(contexts)

  for message in st.session_state.chatbot.session_manager.get_display_messages():
    # ignore tool use blocks
    if isinstance(message["content"], str):
      with st.chat_message(message["role"]):
        st.markdown(message["content"])

  # Chat input
  if user_msg := st.chat_input("Type your message here..."):
    st.chat_message("User").markdown(user_msg)

    with st.chat_message("assistant"):
      with st.spinner("🐧 is thinking..."):
        # response_placeholder = st.empty()
        logging.info('User Message')
        logging.info(user_msg)
        logging.info(st.session_state.filter)

        stream_response, images, links, references = await st.session_state.chatbot.process_user_input(user_msg, st.session_state.filter)

        if images or links or references:
          main_col, media_col = st.columns([2, 1])

          with media_col:
            media_container = st.empty()
            media_summary = create_markdown_media_summary(
              images, links, references)
            if media_summary.strip():
              media_container.markdown(media_summary)

          with main_col:
            await handle_stream_response(stream_response, st.session_state.chatbot)

        else:
          await handle_stream_response(stream_response, st.session_state.chatbot)


if __name__ == "__main__":
  asyncio.run(main())
