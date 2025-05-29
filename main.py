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
from prompt import *

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
APP_NAME = "banking_bot_app"
USER_ID = "test_user_42"
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
def authenticate_user(last_name: str,last_digits: str, tool_context: ToolContext) -> dict:
    """Authenticates a user
    Args:
        last_name (str): Last name provided by the user.
        last_digits (str): Last 4 digits of debit card provided by the user.

    Returns:
        dict: A dictionary providing whether the user was authenticated.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'is_authenticated' key.
              If 'error', includes an 'error_message' key.
    """
    try:
        last_name_normalized = last_name
        last_name_from_db =  tool_context.state["user_name"].split()[-1]
        # print(last_name_from_db)
        last_digits_from_db = tool_context.state["user_debit_card_digits"]
        # print(last_digits_from_db)
        is_name_match = last_name_normalized == last_name_from_db
        is_number_match = last_digits == last_digits_from_db
        if is_name_match and is_number_match:
            tool_context.state["user_authenticated"]=1
            return {"status": "success", "is_authenticated": 'True'}
        else:
            tool_context.state["user_authenticated"]=0
            return {"status": "success", "is_authenticated": 'False'}
    except:
        return {"status": "error", "error_message": f"Sorry, I am not to authenticate at the moment."}

def pay_credit_card_bill(amount_to_pay: int,tool_context: ToolContext) -> dict:
    """Pays the credit card bill for the user
    Args:
        amount_to_pay (int): amount to be paid by the user as credit card bill payment.

    Returns:
        dict: A dictionary providing whether the payment was completed.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'is_payment_completed' key.
              If 'error', includes an 'error_message' key.
    """
    try:
        min_amount = tool_context.state["user_credit_card_bill_min_pay"]
        max_amount = tool_context.state["user_credit_card_bill"]
        account_balance = tool_context.state["user_account_balance"]
        if min_amount <= amount_to_pay <= max_amount:
            tool_context.state["user_credit_card_bill"] = max_amount - amount_to_pay
            tool_context.state["user_account_balance"] = account_balance - amount_to_pay
            return {"status": "success", "is_payment_completed": 'True'}
        else:
            return {"status": "success", "is_payment_completed": 'False'}
    except:
        return {"status": "error", "error_message": f"Sorry, I am not able to pay credit card bill at the moment."}

def update_address(house_number: int, street_name:str, zip_code:str, tool_context: ToolContext) -> dict:
    """Updates the billing address for the user
    Args:
        house_number (int): house number in the updated address provided by the user.
        street_name (str): street name in the updated address provided by the user.
        zip_code (str): zip code in the updated address provided by the user.

    Returns:
        dict: A dictionary providing whether the address update was completed.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'is_address_updated' key.
              If 'error', includes an 'error_message' key.
    """
    try:
        tool_context.state["user_house_number"] = house_number
        tool_context.state["user_street_name"] = street_name
        tool_context.state["user_zip_code"] = zip_code
        
        return {"status": "success", "is_address_updated": 'True'}
    except:
        return {"status": "error", "error_message": f"Sorry, I am not able to update your billing address at the moment."}

# --- 4. Configure Agents ---


authentication_agent = LlmAgent(
    model=MODEL_NAME,
    name="authentication_agent",
    description="Authenticates a user",
    instruction=prompt_auth_task,
    tools=[authenticate_user],
)

account_info_agent = LlmAgent(
    model=MODEL_NAME,
    name="account_info_agent",
    description="Provides information about account and credit card bill and billing address",
    instruction=prompt_account_info_task,
)

bill_payment_agent = LlmAgent(
    model=MODEL_NAME,
    name="bill_payment_agent",
    description="Pays the credit card bill for the user",
    instruction=prompt_make_payment_task,
    tools=[pay_credit_card_bill],
)

address_update_agent = LlmAgent(
    model=MODEL_NAME,
    name="address_update_agent",
    description="Updates the billing address for the user",
    instruction=prompt_update_address_task,
    tools=[update_address],
)

root_agent = LlmAgent(
    model=MODEL_NAME,
    name="root_agent",
    description="Primary agent that talks to the user and orchestrates tasks",
    instruction=prompt_system_task,
    sub_agents=[authentication_agent,account_info_agent,bill_payment_agent,address_update_agent],
)

# --- 5. Set up Session Management and Runners ---
session_service = InMemorySessionService()

initial_state = {
    "user_authenticated": 0,
    "user_name": "John Doe",
    "user_debit_card_digits": "1890",
    "user_account_balance": 10000,
    "user_credit_card_bill":1500,
    "user_credit_card_bill_min_pay":100,
    "user_house_number":42,
    "user_street_name":"Oak St",
    "user_zip_code":"89530"
}

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
    # print("Current Session State:")
    # print(json.dumps(final_session.state, indent=2))
    # print("-------------------------------\n")
    # print("All events in current session:")
    # for event in final_session.events:
    #     print(event.content)
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