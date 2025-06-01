import os
import asyncio
import json # Needed for pretty printing dicts
import logging

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from pydantic import BaseModel, Field
from api_keys import *
from config import *
from agents import *

import warnings
warnings.filterwarnings("ignore") # Ignores all warnings

import logging
logging.basicConfig(
    filename='app.log',  # Specify the log file name
    level=logging.INFO,  # Set the minimum logging level to INFO (or DEBUG, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(levelname)s - %(message)s',  # Define the log message format
    filemode='w'
)


os.environ["GOOGLE_CLOUD_PROJECT"] = google_project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = google_project_region
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

# --- 1. Define Constants ---

# --- 2. Define Schemas ---

# # Input schema used by both agents
# class CountryInput(BaseModel):
#     country: str = Field(description="The country to get information about.")

# # Output schema ONLY for the second agent
# class CapitalInfoOutput(BaseModel):
#     capital: str = Field(description="The capital city of the country.")
#     # Note: Population is illustrative; the LLM will infer or estimate this
#     # as it cannot use tools when output_schema is set.
#     population_estimate: str = Field(description="An estimated population of the capital city.")



# --- 4. Configure Agents ---

# --- 5. Set up Session Management and Runners ---
session_service = InMemorySessionService()

initial_state = user_data

# Create separate sessions for clarity, though not strictly necessary if context is managed
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID,\
     session_id=SESSION_ID,state=initial_state)
# session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID_SCHEMA_AGENT)

# Create a runner for EACH agent
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service
)

# --- 6. Define Agent Interaction Logic ---
async def call_agent(
    user_input: str
):
    """Sends a user input to the agent and provide output."""

    content = types.Content(role='user', parts=[types.Part(text=user_input)])

    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        # You can uncomment the line below to see *all* events during execution
        # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

        # Key Concept: is_final_response() marks the concluding message for the turn.
        if event.is_final_response():
            if event.content and event.content.parts:
                # Assuming text response in the first part
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate: # Handle potential errors/escalations
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            # Add more checks here if needed (e.g., specific error codes)
            break # Stop processing events once the final response is found

    final_session = session_service.get_session(app_name=APP_NAME, 
                                                user_id=USER_ID, 
                                                session_id=SESSION_ID)
    logging.info("Session State Snapshot:")
    logging.info(json.dumps(final_session.state, indent=2))
    # print("-------------------------------\n")
    logging.info("Event Stream:")
    for event in final_session.events:
        logging.info(event.content)
    #     print("------\n")
    # print("-------------------------------\n")
    return final_response_text


# --- 7. Run Interactions ---
async def main():
    quit_condition = False
    while True:
        if quit_condition:
            break
        user_input = input("User (q/Q to quit): ")
        if user_input in {"q", "Q"}:
            print("Conversation Terminated by User!")
            break
        agent_response = await call_agent(user_input)
        print(f"Agent: {agent_response}")

if __name__ == "__main__":
    asyncio.run(main())