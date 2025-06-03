import os

from typing import AsyncGenerator
from typing_extensions import override
from google.adk.agents import LlmAgent,BaseAgent,LoopAgent,SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from prompt import *
from tools import *
from config import *

class CustomerSupportAgent(BaseAgent):
    """
    Custom Agent for customer support for user in banking domain.
    """
    # --- Field Declarations for Pydantic ---
    # Declare the agents passed during initialization as class attributes with type hints
    orchestrator: LlmAgent
    authenticator: LlmAgent

    authentication_pipeline: SequentialAgent

    def __init__(self,
                name: str,
                orchestrator: LlmAgent,
                authenticator: LlmAgent,
                ):
        """
        Initializes the CustomerSupportAgent.

        Args:
            name: The name of the agent.
            orchestrator: An LlmAgent to talk to the user and perform tasks.
            authenticator: An LlmAgent to autheticate the user.
        """
        authentication_pipeline = SequentialAgent(name="Authentication_pipeline",sub_agents=[orchestrator,authenticator])

        super().__init__(name=name,
                        orchestrator=orchestrator,
                        authenticator=authenticator,
                        authentication_pipeline=authentication_pipeline)

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Implements the custom logic for the customer support.
        Uses the instance attributes assigned by Pydantic (e.g., self.authentication_pipeline).
        """
        is_authentication_completed = ctx.session.state.get("user_authenticated")
        if is_authentication_completed == 0:
            async for event in self.authentication_pipeline.run_async(ctx):
                yield event
        else:
            async for event in self.orchestrator.run_async(ctx):
                yield event

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

## uncomment this and comment next block to run without custom agent
# orchestrator_agent = LlmAgent(
#     model=MODEL_NAME,
#     name="orchestrator_agent",
#     description="Primary agent that talks to the user and orchestrates tasks",
#     instruction=prompt_system_task,
#     sub_agents=[authentication_agent,account_info_agent,bill_payment_agent,address_update_agent],
# )

## custom agent run
orchestrator_agent = LlmAgent(
    model=MODEL_NAME,
    name="orchestrator_agent",
    description="Primary agent that talks to the user and orchestrates tasks",
    instruction=prompt_system_task,
    sub_agents=[account_info_agent,bill_payment_agent,address_update_agent],
)
