import os
from dotenv import load_dotenv
from anthropic import Anthropic

from config import IDENTITY, MODEL, TOOLS
from tools import get_quote
from vectordb import VectorDB

# Load environment variables from .env file
load_dotenv()


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
    self.session_state.messages.append({"role": "user", "content": user_input})

    response_message = self.vector_db.search(user_input)

    if response_message:
      response_text = response_message[0]['metadata']['content']
      self.session_state.messages.append(
        {"role": "assistant", "content": response_text})
      return response_text
    else:
      response_text = "No relevant documents found."
      self.session_state.messages.append(
        {"role": "assistant", "content": response_text})

    # Include the response from the vector database as context for the LLM
    context_message = {"role": "system",
                       "content": f"Context: {response_text}"}
    self.session_state.messages.append(context_message)

    stream_response = self.generate_message(
      messages=self.session_state.messages,
      max_tokens=2048
    )

    # if "error" in response_message:
    if isinstance(stream_response, dict) and "error" in stream_response:
      return f"An error occurred: {stream_response['error']}"

    return stream_response

    # except Exception as e:
    #     return f"Error during streaming {str(e)}"
    # if response_message.content[-1].type == "tool_use":
    #   tool_use = response_message.content[-1]
    #   func_name = tool_use.name
    #   func_params = tool_use.input
    #   tool_use_id = tool_use.id
    #   result = self.handle_tool_use(func_name, func_params)
    #   self.session_state.messages.append(
    #     {"role": "assistant", "content": response_message.content}
    #   )

    #   self.session_state.messages.append({
    #     "role": "user",
    #     "content": [{
    #       "type": "tool_result",
    #       "tool_use_id": tool_use_id,
    #       "content": f"{result}",
    #     },]
    #   })

    #   follow_up_response = self.generate_message(
    #     messages=self.session_state.messages,
    #     max_tokens=2048
    #   )

    #   if "error" in follow_up_response:
    #     return f"An error occurred: {follow_up_response['error']}"

    #   response_text = follow_up_response.content[0].text
    #   self.session_state.messages.append(
    #     {"role": "assistant", "content": response_text}
    #   )
    #   return response_text

    # elif response_message.content[0].type == "text":
    #   response_text = response_message.content[0].text
    #   self.session_state.messages.append(
    #     {"role": "assistant", "content": response_text}
    #   )
    #   return response_text

    # else:
    #  raise Exception("An error occurred: Unexpected response type")

  def handle_tool_use(self, func_name, func_params):
    if func_name == "get_quote":
      premium = get_quote(**func_params)
      return f"Quote generated: ${premium: .2f} per month"

    raise Exception(f"An unexpected tool was used: {func_name}")
