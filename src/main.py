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
#from api_keys import *
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

os.environ["GOOGLE_CLOUD_PROJECT"] = 'eci-ugi-digital-ccaipoc'
os.environ["GOOGLE_CLOUD_LOCATION"] = 'us-central1'
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
runner = None
# Set up Session Management and Runners ---
session_service = InMemorySessionService()

# load initial user data
initial_state = user_data




print(APP_NAME, USER_ID, SESSION_ID)
# Initialize custom root agent, comment block and uncomment next to run skip custom agent
root_agent = CustomerSupportAgent(
                name="root_agent",
                orchestrator=orchestrator_agent,
                authenticator=authentication_agent,
                )

async def setup_runner():
    global runner
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state=initial_state
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

# # Create a runner, uncomment this to run orchestrator agent without custom 
# runner = Runner(
#     agent=orchestrator_agent,
#     app_name=APP_NAME,
#     session_service=session_service
# )

# Define Agent Interaction Logic ---
async def call_agent(
    user_input: str
):
    """Sends a user input to the agent and provide output."""

    content = types.Content(role='user', parts=[types.Part(text=user_input)])
    output_response = ""
    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        # You can uncomment the line below to see *all* events during execution
        # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

        # if event.is_final_response():
        #     if event.content and event.content.parts:
        #         # Assuming text response in the first part
        #         final_response_text = event.content.parts[0].text
        #     elif event.actions and event.actions.escalate: # Handle potential errors/escalations
        #         final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
        #     # Add more checks here if needed (e.g., specific error codes)
        #     break # Stop processing events once the final response is found
        if event.content.parts[0].text:
            output_response += event.content.parts[0].text

    final_session = await session_service.get_session(app_name=APP_NAME, 
                                                user_id=USER_ID, 
                                                session_id=SESSION_ID)
    logging.info("Session State Snapshot:")
    logging.info(json.dumps(final_session.state, indent=2))
    logging.info("Event Stream:")
    for event in final_session.events:
        logging.info(event.content)
    return output_response.replace("\n","")


#Run Interactions ---
async def main():
    await setup_runner()
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