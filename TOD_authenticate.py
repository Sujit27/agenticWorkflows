#!/usr/bin/env python
# coding: utf-8



import uuid
import getpass
import os

from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List, Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver


os.environ["OPENAI_API_KEY"] = "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"
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ['LANGSMITH_ENDPOINT'] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "pr-authorized-someplace-95"




class StateSchema(TypedDict):
    messages: Annotated[list, add_messages]




prompt_system_task = """Your job is to gather information from the user and authenticate.

You should obtain the following authentication fields from them:

1. policy number
2. last name
3. date of birth

Ask the user for authentication fields. 
If the use does not provide value for a field after repeated requests, let them know you would not be able to proceed further without it.
If the use tries to engage them in any other conversation, bring them to the task of authenticating themselves in a polite and humorous way.

ONLY OFTER you are able to get all the 3 authentication fields from the user, call the relevant tool."""




def domain_state_tracker(messages):
    return [SystemMessage(content=prompt_system_task)] + messages



llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)



class AuthenticationProfile(BaseModel):
    """Information about authentication fields"""
    policy_number: str = Field(default=None, description="The policy number of the user")
    last_name: str = Field(default=None, description="The last name of the user")
    date_of_birth: str = Field(default=None, description="The date of birth of the user")



class ResponseFormatter(BaseModel):
    """Always use this tool to structure the output"""
    answer: bool = Field(description="True or False depending if user authentication was successful or not")



user_info = {"policy_number":"0123456789","last_name":"Sahoo","date_of_birth":"27 Dec 1990"}



llm_to_collect_info = llm.bind_tools([AuthenticationProfile])



llm_to_authenticate = llm.bind_tools([ResponseFormatter])



workflow = StateGraph(StateSchema)



def call_llm(state: StateSchema):
    """
    talk_to_user node function, adds the prompt_system_task to the messages,
    calls the LLM and returns the response
    """
    messages = domain_state_tracker(state["messages"])
    response = llm_to_collect_info.invoke(messages)
    return {"messages": [response]}




workflow.add_node("talk_to_user", call_llm)



workflow.add_edge(START, "talk_to_user")



def finalize_dialogue(state: StateSchema):
    """
    Add a tool message to the history so the graph can see that it`s time to autheticate
    """
    return {
        "messages": [
            ToolMessage(
                content="Prompt generated!",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        ]
    }

workflow.add_node("finalize_dialogue", finalize_dialogue)



prompt_generate_user_story = """Based on the following extracted fields from the user and the actual field values from database,/
 authenticate the user by providing True or False in output:

extracted fields: {reqs}

actual fields: {user_info}

"""

def build_prompt_to_generate_user_story(messages: list):
    tool_call = None
    other_msgs = []
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls: #tool_calls is from the OpenAI API
            tool_call = m.tool_calls[0]["args"]
        elif isinstance(m, ToolMessage):
            continue
        elif tool_call is not None:
            other_msgs.append(m)
    return [SystemMessage(content=prompt_generate_user_story.format(reqs=tool_call,user_info=user_info))] + other_msgs


def call_model_to_generate_user_story(state):
    messages = build_prompt_to_generate_user_story(state["messages"])
    response = llm_to_authenticate.invoke(messages)
    return {"messages": [response]}

workflow.add_node("authenticate_user", call_model_to_generate_user_story)



def define_next_action(state) -> Literal["finalize_dialogue", END]:
    messages = state["messages"]

    if isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return "finalize_dialogue"
    else:
        return END

workflow.add_conditional_edges("talk_to_user", define_next_action)



workflow.add_edge("finalize_dialogue", "authenticate_user")
workflow.add_edge("authenticate_user", END)



memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

while True:
    user = input("User (q/Q to quit): ")
    if user in {"q", "Q"}:
        print("User NOT Authenticated!")
        break
    output = None
    for output in graph.stream({"messages": [HumanMessage(content=user)]}, config=config, stream_mode="updates"):
        # print(output)
        last_message = next(iter(output.values()))["messages"][-1]
        last_message.pretty_print()

    if last_message.tool_calls:
        if last_message.tool_calls[0]['args']['answer'] == True:
            print("User Authenticated!")
        elif last_message.tool_calls[0]['args']['answer'] == False:
            print("User NOT Authenticated!")
        break
    





