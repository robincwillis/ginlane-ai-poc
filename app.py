
import streamlit as st
from chatbot import ChatBot
from config import TASK_SPECIFIC_INSTRUCTIONS
import logging


logging.basicConfig(level=logging.DEBUG)

logging.debug("hello from app.py")


def handle_stream_response(stream_response):
  """Handle the streaming response and UI updates"""
  if isinstance(stream_response, dict) and "error" in stream_response:
    st.error(f"Error: {stream_response['error']}")
    return None

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


def main():
  st.title("Welcome to Gin Lane. 🌊")

  st.write(
    "We’re here to help you with any and all req uests related to: ",
    "brand, ",
    "interactive, ",
    "positioning.",
  )

  if "display_messages" not in st.session_state:
    st.session_state.display_messages = []

  if "api_messages" not in st.session_state:
    st.session_state.api_messages = [
      {'role': "user", "content": TASK_SPECIFIC_INSTRUCTIONS},
      {'role': "assistant", "content": "Understood"},
    ]

  # if "messages" not in st.session_state:
  #   st.session_state.messages = [
  #     {'role': "user", "content": TASK_SPECIFIC_INSTRUCTIONS},
  #     {'role': "assistant", "content": "Understood"},
  #   ]

  chatbot = ChatBot(st.session_state)

  for message in st.session_state.display_messages:

    # ignore tool use blocks
    if isinstance(message["content"], str):
      with st.chat_message(message["role"]):
        st.markdown(message["content"])

  if user_msg := st.chat_input("Type your message here..."):
    st.chat_message("User").markdown(user_msg)

    with st.chat_message("assistant"):
      with st.spinner("🐧 Gin Lane AI is thinking..."):
        response_placeholder = st.empty()
        stream_response = chatbot.process_user_input(user_msg)
        full_response = handle_stream_response(stream_response)

        # full_response = chatbot.process_user_input(user_msg)
        # response_placeholder.markdown(full_response)

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
  main()
