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
from prompt import prompt_auth_task

import warnings
# Ignore all warnings
warnings.filterwarnings("ignore")

import logging
logging.basicConfig(level=logging.ERROR)

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("Libraries imported.")

os.environ["GOOGLE_CLOUD_PROJECT"] = google_project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = google_project_region
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

# --- 1. Define Constants ---
APP_NAME = "agent_comparison_app"
USER_ID = "test_user_456"
SESSION_ID = "session_tool_agent_xyz"
SESSION_ID_SCHEMA_AGENT = "session_schema_agent_xyz"
MODEL_NAME = "gemini-2.0-flash"

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

# --- 3. Define the Tool (Only for the first agent) ---
def authenticate_user(last_name: str,tool_context: ToolContext) -> dict:
    """Authenticates a user
    Args:
        last_name (str): Last name provided by the user.

    Returns:
        dict: A dictionary providing whether the user was authenticated.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'is_authenticated' key.
              If 'error', includes an 'error_message' key.
    """
    try:
        last_name_normalized = last_name.lower() # Basic normalization
        last_name_list = ['doe','smith']
        if last_name_normalized in last_name_list:
            tool_context.state["user_authenticated"]=1
            return {"status": "success", "is_authenticated": 'True'}
        else:
            tool_context.state["user_authenticated"]=0
            return {"status": "success", "is_authenticated": 'False'}
    except:
        return {"status": "error", "error_message": f"Sorry, I am not to authenticate at the moment."}

# --- 4. Configure Agents ---

# Agent 1: Uses a tool and output_key
authentication_agent = LlmAgent(
    model=MODEL_NAME,
    name="authentication_agent",
    description="Authenticates a user",
    instruction=prompt_auth_task,
    tools=[authenticate_user],
)

# # Agent 2: Uses output_schema (NO tools possible)
# structured_info_agent_schema = LlmAgent(
#     model=MODEL_NAME,
#     name="structured_info_agent_schema",
#     description="Provides capital and estimated population in a specific JSON format.",
#     instruction=f"""You are an agent that provides country information.
# The user will provide the country name in a JSON format like {{"country": "country_name"}}.
# Respond ONLY with a JSON object matching this exact schema:
# {json.dumps(CapitalInfoOutput.model_json_schema(), indent=2)}
# Use your knowledge to determine the capital and estimate the population. Do not use any tools.
# """,
#     # *** NO tools parameter here - using output_schema prevents tool use ***
#     input_schema=CountryInput,
#     output_schema=CapitalInfoOutput, # Enforce JSON output structure
#     output_key="structured_info_result", # Store final JSON response
# )

# --- 5. Set up Session Management and Runners ---
session_service = InMemorySessionService()

initial_state = {
    "user_authenticated": 0
}

# Create separate sessions for clarity, though not strictly necessary if context is managed
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID,\
     session_id=SESSION_ID,state=initial_state)
# session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID_SCHEMA_AGENT)

# Create a runner for EACH agent
runner = Runner(
    agent=authentication_agent,
    app_name=APP_NAME,
    session_service=session_service
)
# structured_runner = Runner(
#     agent=structured_info_agent_schema,
#     app_name=APP_NAME,
#     session_service=session_service
# )

# --- 6. Define Agent Interaction Logic ---
async def call_agent(
    user_input: str
):
    """Sends a user input to the agent and provide output."""
    # current_session = session_service.get_session(app_name=APP_NAME, 
    #                                               user_id=USER_ID, 
    #                                               session_id=SESSION_ID)
    # if not current_session:
    #     logger.error("Session not found!")
    #     return

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
    print("Current Session State:")
    print(json.dumps(final_session.state, indent=2))
    print("-------------------------------\n")
    print("All events in current session:")
    for event in final_session.events:
        if event.author == "user":  # Check if it's a user message
            print("User:", event.content)
        else:  # Check if it's an agent response
            print("Agent:", event.content)
        print("------\n")
    print("-------------------------------\n")
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