
from typing import Dict
import uuid
import streamlit as st
from chatbot import ChatBot
from config import TASK_SPECIFIC_INSTRUCTIONS, IDENTITY, STATIC_GREETINGS_AND_GENERAL, STATIC_EXPERIENCE_DESIGN, STATIC_BRANDING, STATIC_CREATIVE_DIRECTION, EXAMPLES, ADDITIONAL_GUARDRAILS
import logging

logging.basicConfig(level=logging.DEBUG)

# Inject custom CSS
# st.markdown("""
#     <style>
#         /* Target the chat input field when focused */
#         textarea:focus {
#             border: 2px solid black !important;
#         }
#     </style>
# """, unsafe_allow_html=True)


def initialize_contexts() -> Dict[str, str]:
  """Initialize default context values if they don't exist in session state"""
  if 'identity' not in st.session_state:
    st.session_state.identity = IDENTITY
  if 'contexts' not in st.session_state:
    st.session_state.contexts = {
        'greeting_and_general': STATIC_GREETINGS_AND_GENERAL,
        'experience_design': STATIC_EXPERIENCE_DESIGN,
        'branding': STATIC_BRANDING,
        'creative_direction': STATIC_CREATIVE_DIRECTION,
        'example_questions': EXAMPLES,
        'guard_rails': ADDITIONAL_GUARDRAILS,
    }
  return st.session_state.contexts


def initialize_chatbot():
  st.session_state.display_messages = []
  st.session_state.api_messages = [
      {'role': "user", "content": combine_contexts()},
      {'role': "assistant", "content": "Understood"},
    ]
  # Reinitialize chatbot with new identity
  chatbot = ChatBot(st.session_state.identity, st.session_state)
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


def context_manager():
  """Create a management interface for context texts"""
  contexts = initialize_contexts()
  keys_to_remove = []
  with st.sidebar:
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


def handle_stream_response(stream_response):
  """Handle the streaming response and UI updates"""
  try:
    # Use write_stream to handle the streaming content
    with stream_response as stream:
      full_response = st.write_stream(
          (chunk.delta.text for chunk in stream if chunk.type == "content_block_delta")
      )
    return full_response

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

  except Exception as e:
    st.error(f"handle_stream_response:error: {str(e)}")
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

  context_manager()
  chatbot = initialize_chatbot()

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
        logging.debug('User Message')
        logging.debug(st.session_state.user_msg)
        logging.debug(st.session_state.identity)
        logging.debug(st.session_state.contexts)

        stream_response = await chatbot.process_user_input(user_msg)
        full_response = handle_stream_response(stream_response)

        # Update chat history if response was successful
        if full_response is not None:
          st.session_state.display_messages.append({
              "role": "assistant",
              "content": full_response
          })
          st.session_state.api_messages.append({
              "role": "assistant",
              "content": full_response
          })


if __name__ == "__main__":
  import asyncio
  asyncio.run(main())
