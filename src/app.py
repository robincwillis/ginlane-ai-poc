
from typing import Dict, List, Any, Optional
import uuid
import logging
import asyncio
import threading
import time
import streamlit as st
from agent.chatbot import ChatBot
from config import MODEL, IDENTITY, PERSONALITY, PRIORITY_THRESHOLD, PERSONALITY_LEVEL, ON_TOPIC_IDENTITY, OFF_TOPIC_IDENTITY, INDEX, TOPICS, STATIC_GREETINGS_AND_GENERAL, SEARCH_K

logging.basicConfig(level=logging.INFO)


def initialize_contexts() -> Dict[str, str]:
  """Initialize default context values if they don't exist in session state"""
  if 'identity' not in st.session_state:
    st.session_state.identity = IDENTITY
  if 'personality_level' not in st.session_state:
    st.session_state.personality_level = PERSONALITY_LEVEL
  if 'identity_on_topic' not in st.session_state:
    st.session_state.identity_on_topic = ON_TOPIC_IDENTITY
  if 'identity_off_topic' not in st.session_state:
    st.session_state.identity_off_topic = OFF_TOPIC_IDENTITY
  if 'contexts' not in st.session_state:
    st.session_state.contexts = {
        'greeting_and_general': STATIC_GREETINGS_AND_GENERAL,
    }
  if 'topics' not in st.session_state:
    st.session_state.topics = TOPICS

  if 'priority_filter' not in st.session_state:
    st.session_state.priority_filter = PRIORITY_THRESHOLD

  if 'filter' not in st.session_state:
    st.session_state.filter = {
      "priority": {"$gte": PRIORITY_THRESHOLD}
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
  identity = st.session_state.identity
  personality_level = st.session_state.get("personality_level")
  personality = PERSONALITY[personality_level]
  insert_position = st.session_state.identity.find("\n\n")

  if insert_position == -1:
    # If we can't find a good position, just append it
    identity += personality
  else:
    # Insert the personality text after the first paragraph
    identity = st.session_state.identity[:insert_position] + "\n\n" + \
        personality + st.session_state.identity[insert_position:]

  chatbot = ChatBot(
    identity,
    identity + st.session_state.identity_on_topic,
    identity + st.session_state.identity_off_topic,
    INDEX,
    st.session_state
  )

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
  st.session_state.needs_rerun = True


def update_priority_filter(value):
  if value != st.session_state["priority_filter"]:
    st.session_state["priority_filter"] = value
    st.session_state["filter"]["priority"] = {"$gte": value}


def update_personality():
  # if value - 1 != st.session_state["personality_level"]:
  index = st.session_state.personality_slider - 1
  if index != st.session_state.personality_level:
    st.session_state["personality_level"] = index
    st.session_state.initialized = False
    if 'chatbot' in st.session_state:
      del st.session_state.chatbot
    st.session_state.needs_rerun = True


def context_manager(contexts):
  """Create a management interface for context texts"""

  keys_to_remove = []
  with st.sidebar:
    st.header("Settings")

    personality_labels = {
      1: "🧀",
      2: "🍅",
      3: "🍕",
      4: "🌶️",
      5: "🧨"
    }

    personality_level = st.slider(
        f"Personality: {personality_labels[st.session_state.personality_level + 1]}",
        min_value=1,
        max_value=5,
        value=st.session_state.personality_level + 1,  # Default value
        step=1,
        key="personality_slider",
        on_change=update_personality
    )

    priority_filter = st.slider(
      "Priority Threshold",
      0.0,
      1.0,
      0.3,
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
          st.session_state.needs_rerun = True

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
              st.session_state.needs_rerun = True

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
        st.session_state.needs_rerun = True

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

# Define the emoji spinner function


def emoji_spinner(container, delay=0.3):
  emoji_list = ["🗽", "🤌", "🔥", "🍕", "🧄", "🚕", "🏙️", "🌶️", "🍝", "💪", "🍷"]
  stop_spinner = threading.Event()

  def spin_emojis():
    i = 0
    # Instead of trying to create an empty placeholder inside the container,
    # directly update the container with markdown
    while not stop_spinner.is_set():
      with container.container():
        st.markdown(f"{emoji_list[i]} thinking...")
      i = (i + 1) % len(emoji_list)
      time.sleep(delay)

  spinner_thread = threading.Thread(target=spin_emojis)
  spinner_thread.start()

  return stop_spinner, spinner_thread


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

  if st.session_state.get("needs_rerun", False):
    st.session_state.needs_rerun = False
    st.rerun()

  for message in st.session_state.chatbot.session_manager.get_display_messages():
    # ignore tool use blocks
    if isinstance(message["content"], str):
      with st.chat_message(message["role"]):
        st.markdown(message["content"])

  # Chat input
  if user_msg := st.chat_input("Type your message here..."):
    st.chat_message("User").markdown(user_msg)

    with st.chat_message("assistant"):
      with st.spinner("Thinking..."):
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
