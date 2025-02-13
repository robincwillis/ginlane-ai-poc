
from typing import Dict
import uuid
import streamlit as st
from agent.chatbot import ChatBot
from config import IDENTITY, INDEX, TOPICS, STATIC_GREETINGS_AND_GENERAL, TERMS, CONTACT, ADDITIONAL_GUARDRAILS
import logging

logging.basicConfig(level=logging.INFO)


def initialize_contexts() -> Dict[str, str]:
  """Initialize default context values if they don't exist in session state"""
  if 'identity' not in st.session_state:
    st.session_state.identity = IDENTITY
  if 'contexts' not in st.session_state:
    st.session_state.contexts = {
        'greeting_and_general': STATIC_GREETINGS_AND_GENERAL,
        'contact': CONTACT,
        'termonology': TERMS,
        # 'guard_rails': ADDITIONAL_GUARDRAILS,
    }
  if 'topics' not in st.session_state:
    st.session_state.topics = TOPICS
    st.session_state.topic_filter = "All"

  if 'priority_filter' not in st.session_state:
    st.session_state.priority_filter = 0.5

  if 'filter' not in st.session_state:
    st.session_state.filter = {
      "subjects": None,
      "priority": {"$gte": 0.5}
    }

  return st.session_state.contexts


def initialize_chatbot():
  if 'display_messages' not in st.session_state:
    st.session_state.display_messages = []

  if 'api_messages' not in st.session_state:
    st.session_state.api_messages = [
      {'role': "user", "content": combine_contexts()},
      {'role': "assistant", "content": "Understood"},
    ]
  # Reinitialize chatbot with new identity
  chatbot = ChatBot(st.session_state.identity, INDEX, st.session_state)
  # if 'chatbot' in st.session_state:
  #   st.session_state.chatbot =
  return chatbot


def combine_contexts() -> str:
  """Combine all contexts into a single message"""
  contexts = st.session_state.contexts
  context_texts = [v for k, v in contexts.items()]
  return "\n\n".join(context_texts)


def delete_context(key: str):
  """Delete a context and trigger a rerun"""
  del st.session_state.contexts[key]
  initialize_chatbot()
  st.rerun()
  st.toast("Context deleted and chat state reset!", icon="✅")


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
      # on_change=update_topic_filter,
      # args=(st.session_state.topic_filter,)
    )
    update_topic_filter(selected_topic)

    priority_filter = st.slider(
      "Priority Threshold",
      0.0,
      1.0,
      0.5,
      0.1,
      # on_change=update_priority_filter,
      # args=(st.session_state.priority_filter,)
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
          initialize_chatbot()
          st.toast("Identity updated and chat state reset!", icon="✅")

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
              initialize_chatbot()
              st.toast("Context updated and chat state reset!", icon="✅")

        with col3:
          if st.button("🗑️", key=f"delete_{key}", use_container_width=True):
            keys_to_remove.append(key)

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


def handle_stream_response(stream_response):

  # create_markdown_media_summary()
  """Handle the streaming response and UI updates"""
  try:
    # Use write_stream to handle the streaming content
    with stream_response as stream:
      full_response = st.write_stream(
          (chunk.delta.text for chunk in stream if chunk.type == "content_block_delta")
      )

    if full_response is not None:
      st.session_state.display_messages.append({
          "role": "assistant",
          "content": full_response
      })
      st.session_state.api_messages.append({
          "role": "assistant",
          "content": full_response
      })

  except Exception as e:
    st.error(f"handle_stream_response:error: {str(e)}")
    return None

    # For Debugging
    # with stream_response as stream:
    #   full_response = ""
    #   for chunk in stream:
    #     if chunk.type == "content_block_delta":
    #       text_chunk = chunk.delta.text
    #       st.write(text_chunk)
    #       full_response += text_chunk
    #       # Debug statement to print each chunk
    #       st.write(f"Chunk received: {text_chunk}")
    #       print(f"Chunk received: {text_chunk}")
    #   return full_response


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
  chatbot = initialize_chatbot()
  context_manager(contexts)

  for message in st.session_state.display_messages:
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

        stream_response, images, links, references = await chatbot.process_user_input(user_msg, st.session_state.filter)

        if images or links or references:
          main_col, media_col = st.columns([2, 1])

          with media_col:
            media_container = st.empty()
            media_summary = create_markdown_media_summary(
              images, links, references)
            if media_summary.strip():
              media_container.markdown(media_summary)

          with main_col:
            handle_stream_response(stream_response)

        else:
          handle_stream_response(stream_response)


if __name__ == "__main__":
  import asyncio
  asyncio.run(main())
