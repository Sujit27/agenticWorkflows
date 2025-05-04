# @title Import necessary libraries
import os
import asyncio
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm # For multi-model support
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types # For creating message Content/Parts
from api_keys import *

import warnings
# Ignore all warnings
warnings.filterwarnings("ignore")

import logging
logging.basicConfig(level=logging.ERROR)

from prompt import prompt_system_task

os.environ["GOOGLE_API_KEY"] = google_api_key # <--- REPLACE
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"

AGENT_MODEL = "gemini-2.0-flash"

banking_agent = Agent(
    name="banking_agent",
    model=AGENT_MODEL, # Can be a string for Gemini or a LiteLlm object
    description="Provides bank account and credit card details",
    instruction=prompt_system_task,
)

session_service = InMemorySessionService()

APP_NAME = "banking_app"
USER_ID = "user_1"
SESSION_ID = "session_001" 

session = session_service.create_session(
    app_name=APP_NAME,
    user_id=USER_ID,
    session_id=SESSION_ID
)
print(f"Session created: App='{APP_NAME}', User='{USER_ID}', Session='{SESSION_ID}'")

# --- Runner ---
runner = Runner(
    agent=banking_agent, # The agent we want to run
    app_name=APP_NAME,   # Associates runs with our app
    session_service=session_service # Uses our session manager
)

async def call_agent_async(query: str, runner, user_id, session_id):
  """Sends a query to the agent and prints the final response."""
  print(f"\n>>> User Query: {query}")
  # Prepare the user's message in ADK format
  content = types.Content(role='user', parts=[types.Part(text=query)])

  final_response_text = "Agent did not produce a final response." # Default

  async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
      # You can uncomment the line below to see *all* events during execution
    #   print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

      # Key Concept: is_final_response() marks the concluding message for the turn.
      if event.is_final_response():
          if event.content and event.content.parts:
             # Assuming text response in the first part
             final_response_text = event.content.parts[0].text
          elif event.actions and event.actions.escalate: # Handle potential errors/escalations
             final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
          # Add more checks here if needed (e.g., specific error codes)
          break # Stop processing events once the final response is found

  print(f"<<< Agent Response: {final_response_text}")

async def run_conversation():
    quit_condition = False
    while True:
        if quit_condition:
            break
        user_input = input("User (q/Q to quit): ")
        if user_input in {"q", "Q"}:
            print("Conversation Terminated by User!")
            break
        await call_agent_async(user_input,
                                       runner=runner,
                                       user_id=USER_ID,
                                       session_id=SESSION_ID)

if __name__ == "__main__":
    try:
        asyncio.run(run_conversation())
    except Exception as e:
        print(f"An error occurred: {e}")