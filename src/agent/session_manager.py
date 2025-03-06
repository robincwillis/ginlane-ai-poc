import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from anthropic import Anthropic
import streamlit as st

from config import MAX_INPUT_TOKENS_PER_MINUTE, TOKEN_BUFFER


class SessionManager:
  def __init__(
    self,
    anthropic_client: Anthropic,
    model: str,
    max_tokens: int = MAX_INPUT_TOKENS_PER_MINUTE,
    token_buffer: int = TOKEN_BUFFER,
    system_prompt: str = "",
    session_state: Optional[Any] = None
  ):

    self.anthropic = anthropic_client
    self.model = model
    self.max_tokens = max_tokens
    self.token_buffer = token_buffer
    self.system_prompt = system_prompt
    self.st_session = session_state

    # Initialize session variables if they don't exist
    if self.st_session:
      if "api_messages" not in self.st_session:
        self.st_session.api_messages = []
      if "display_messages" not in self.st_session:
        self.st_session.display_messages = []
      if "token_usage" not in self.st_session:
        self.st_session.token_usage = 0
      if "message_tokens" not in self.st_session:
        self.st_session.message_tokens = []

    # Local state for non-Streamlit usage
    self.api_messages = []
    self.display_messages = []
    self.current_token_usage = 0
    self.message_tokens = []

  def get_api_messages(self) -> List[Dict[str, str]]:
    """Get the current message history."""
    if self.st_session:
      return self.st_session.api_messages
    return self.api_messages

  def get_display_messages(self) -> List[Dict[str, str]]:
    """Get the current display message history."""
    if self.st_session:
      return self.st_session.display_messages
    return self.display_messages

  def _get_token_usage(self) -> int:
    """Get current token usage."""
    if self.st_session:
      return self.st_session.token_usage
    return self.current_token_usage

  def _get_message_tokens(self) -> List[Dict[str, Any]]:
    """Get token metadata for all messages."""
    if self.st_session:
      return self.st_session.message_tokens
    return self.message_tokens

  def _update_api_messages(self, messages: List[Dict[str, str]]) -> None:
    """Update the message history."""
    if self.st_session:
      self.st_session.api_messages = messages
    else:
      self.api_messages = messages

  def _update_display_messages(self, messages: List[Dict[str, str]]) -> None:
    """Update the display message history."""
    if self.st_session:
      self.st_session.display_messages = messages
    else:
      self.display_messages = messages

  def _update_token_usage(self, usage: int) -> None:
    """Update token usage count."""
    if self.st_session:
      self.st_session.token_usage = usage
    else:
      self.current_token_usage = usage

  def _update_message_tokens(self, msg_tokens: List[Dict[str, Any]]) -> None:
    """Update token metadata for messages."""
    if self.st_session:
      self.st_session.message_tokens = msg_tokens
    else:
      self.message_tokens = msg_tokens

  def count_tokens(self, message: Dict[str, str]) -> int:
    """
    Count tokens in a message using Anthropic's API.
    Args:
        message: The message to count tokens for
    Returns:
        Number of tokens in the message
    """
    try:
      # Use Anthropic's token counting endpoint
      response = self.anthropic.messages.count_tokens(
        model=self.model,
        messages=[message]
      )
      token_count = response.input_tokens
      return token_count

    except Exception as e:
      logging.warning(f"Error counting tokens: {str(e)}")
      return 0

  async def add_message(self, role: str, content: str, add_to_api: bool = True, add_to_display: bool = True, is_context: bool = False) -> None:
    """
    Add a message to the conversation history and track tokens.

    Args:
        role: Message role (user, assistant, system)
        content: Message content
        add_to_api: If True, add to API messages for model context
        add_to_display: If True, add to display messages for UI
        is_context: If True, mark this message as a context message (for trimming strategy)
    """
    message = {"role": role, "content": content}

    # Handle display messages
    if add_to_display:
      display_messages = self.get_display_messages()
      display_messages.append(message)
      self._update_display_messages(display_messages)

    # Handle API messages
    if add_to_api:
      # Count tokens in the new message
      token_count = self.count_tokens(message)

      # Get current state
      api_messages = self.get_api_messages()
      current_usage = self._get_token_usage()
      message_tokens = self._get_message_tokens()

      # Add token metadata
      message_with_metadata = {
          "message": message,
          "tokens": token_count,
          "timestamp": time.time(),
          "is_context": is_context  # Mark as context message if specified
      }
      message_tokens.append(message_with_metadata)
      self._update_message_tokens(message_tokens)

      # Add to API messages
      api_messages.append(message)
      self._update_api_messages(api_messages)

      # Update token usage
      current_usage += token_count
      self._update_token_usage(current_usage)

      # Check if we need to trim history
      if current_usage > (self.max_tokens - self.token_buffer):
        await self.trim_history()

  async def trim_history(self) -> None:
    """
    Trim conversation history to stay under token limits.
    Strategy: Remove oldest messages first, prioritizing context messages
    over conversation messages.
    """
    current_usage = self._get_token_usage()
    api_messages = self.get_api_messages()
    message_tokens = self._get_message_tokens()
    display_messages = self._get_display_messages()

    logging.info(
      f"Token limit approaching ({current_usage}/{self.max_tokens}). Trimming history...")

    # Sort message metadata by age (oldest first)
    message_tokens.sort(key=lambda x: x["timestamp"])

    # Keep removing messages until we're under the safe threshold
    token_reduction = 0
    safe_threshold = self.max_tokens - \
        (self.token_buffer * 2)  # Target well below limit
    messages_to_keep = []

    # Process messages to determine which to keep
    for idx, msg_data in enumerate(message_tokens):
      # Always keep the most recent context message and the last few conversation turns
      # This allows for context-aware responses even after trimming
      # Keep last 2 turns (4 messages)
      is_recent = idx >= len(message_tokens) - 4

      if current_usage - token_reduction <= safe_threshold:
        # We've removed enough tokens, keep the rest
        messages_to_keep.append(msg_data)
      elif is_recent:
        # Keep recent messages even if we're over threshold
        messages_to_keep.append(msg_data)
      else:
        # Remove this message to reduce token count
        token_reduction += msg_data["tokens"]
        logging.info(f"Removed message with {msg_data['tokens']} tokens")

    # Update current usage
    new_usage = current_usage - token_reduction
    self._update_token_usage(new_usage)

    # Rebuild API messages from the messages we're keeping
    new_api_messages = [msg_data["message"] for msg_data in messages_to_keep]
    self._update_messages(new_api_messages)
    self._update_message_tokens(messages_to_keep)

    # Also trim display messages to maintain consistency
    # We keep more display messages since they don't count against token limit
    if len(display_messages) > 20:  # Arbitrary limit for display messages
      self._update_display_messages(display_messages[-20:])

    logging.info(
      f"Trimmed {token_reduction} tokens. New usage: {new_usage}/{self.max_tokens}")

  async def reset(self) -> None:
    """Reset the session manager."""
    self._update_messages([])
    self._update_display_messages([])
    self._update_token_usage(0)
    self._update_message_tokens([])

    # If we have a system prompt, add it
    # if self.system_prompt:
    #   greeting_message = {"role": "user", "content": self.system_prompt}
    #   assistant_ack = {"role": "assistant", "content": "Understood"}

    #   await self.add_message(greeting_message["role"], greeting_message["content"])
    #   await self.add_message(assistant_ack["role"], assistant_ack["content"])

  def get_stats(self) -> Dict[str, Any]:
    """Get current token usage statistics."""
    current_usage = self._get_token_usage()
    return {
        "current_usage": current_usage,
        "max_tokens": self.max_tokens,
        "percent_used": round((current_usage / self.max_tokens) * 100, 2),
        "message_count": len(self.get_api_messages()),
        "remaining_tokens": self.max_tokens - current_usage
    }
