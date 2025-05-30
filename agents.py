import os

from google.adk.agents import LlmAgent

from prompt import *
from tools import *
from config import *


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
