
import streamlit as st
from chatbot import ChatBot
from config import TASK_SPECIFIC_INSTRUCTIONS

def main():
  st.title("📄 Gin Lane Documentation question answering")  
  # 
  # Show title and description.
  #    st.title("Chat with Eva, Acme Insurance Company's Assistant🤖")
#   st.write(
#     "Upload a document below and ask a question about it – GPT will answer! "
#     "To use this app, you need to provide an OpenAI API key, which you can get [here](https://platform.openai.com/account/api-keys). "
# )

  if "messages" not in st.session_state:
    st.session_state.messages = [
      {'role': "user", "content": TASK_SPECIFIC_INSTRUCTIONS},
      {'role': "assistant", "content": "Understood"},
    ]
  
  chatbot = ChatBot(st.session_state)
  
  for message in st.session_state.messages[2:]:
    # ignore tool use blocks
    if isinstance(message["content"], str):
      with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
  if user_msg := st.chat_input("Type your message here..."):
    st.chat_message("User").markdown(user_msg)
      
    with st.chat_message("assistant"):
      with st.spinner("🐧 Gin is thinking..."):
        response_placeholder = st.empty()
        full_response = chatbot.process_user_input(user_msg)
        response_placeholder.markdown(full_response)


if __name__ == "__main__":
  main()

