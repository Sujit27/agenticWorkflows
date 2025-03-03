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

from prompt import prompt_system_task, prompt_auth_task, prompt_compare_data
from utility import create_db_connection, execute_query, read_query, get_dict_by_policy_num

from api_keys import openai_api_key,langsmith_api_key


os.environ["OPENAI_API_KEY"] = openai_api_key
os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
os.environ['LANGSMITH_ENDPOINT'] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "pr-authorized-someplace-95"

connection = create_db_connection("localhost", "root", "weakPassword@123","user")

class StateSchema(BaseModel):
    messages: Annotated[list, add_messages]
    user_authenticated: bool = Field(default=0, description="Whether user has been authenticated")
    user_policy_number: int = Field(default=None, description="policy number of the user")
    user_first_name: str = Field(default=None, description="first name of the user")

class AuthenticationProfile(BaseModel):
    """Information about authentication fields"""
    policy_number: str = Field(default=None, description="The policy number of the user")
    last_name: str = Field(default=None, description="The last name of the user")
    date_of_birth: str = Field(default=None, description="The date of birth of the user")

class ResponseFormatter(BaseModel):
    """Always use this tool to structure the output"""
    answer: bool = Field(description="1 or 0 depending if actual and extracted fields matched or not")

def domain_state_tracker(messages,user_authenticated):
    if user_authenticated==1:
        return [SystemMessage(content=prompt_system_task)] + messages
    else:
        return [SystemMessage(content=prompt_system_task + prompt_auth_task)] + messages

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    
)

# user_info = {"policy_number":"0123456789","last_name":"Sahoo","date_of_birth":"27 Dec 1990"}

llm_to_authenticate = llm.bind_tools([AuthenticationProfile])
llm_to_compare_data = llm.bind_tools([ResponseFormatter])


def call_llm(state: StateSchema):
    """
    talk_to_user node function, adds the prompt_system_task to the messages,
    calls the LLM and returns the response
    """
    messages = domain_state_tracker(state.messages,state.user_authenticated)
    if state.user_authenticated==1:
        response = llm.invoke(messages)
    else:
        response = llm_to_authenticate.invoke(messages)
    return {"messages": [response]}

def build_prompt_to_authenticate(messages: list):
    tool_call = None
    user_info = None
    other_msgs = []
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls: #tool_calls is from the OpenAI API
            tool_call = m.tool_calls[0]["args"]
            policy_num = m.tool_calls[0]["args"]['policy_number']
            user_info = get_dict_by_policy_num(connection,policy_num)
        elif isinstance(m, ToolMessage):
            continue
        elif tool_call is not None:
            other_msgs.append(m)
    return [SystemMessage(content=prompt_compare_data.format(reqs=tool_call,user_info=user_info))] + other_msgs, user_info

def call_model_to_authenticate(state):
    messages, user_info = build_prompt_to_authenticate(state.messages)
    response = llm_to_compare_data.invoke(messages)
    if response.tool_calls[0]["args"]['answer']==True:
        return {"messages": [response],"user_authenticated":1,"user_policy_number":\
            user_info["policy_number"],"user_first_name":user_info["first_name"]}
    else:
        return {"messages": [response]}

def define_next_action(state) -> Literal["authenticate_user", END]:
    messages = state.messages

    if isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return "authenticate_user"
    else:
        return END

workflow = StateGraph(StateSchema)
workflow.add_node("talk_to_user", call_llm)
workflow.add_edge(START, "talk_to_user")
workflow.add_node("authenticate_user", call_model_to_authenticate)
workflow.add_conditional_edges("talk_to_user", define_next_action)
workflow.add_edge("authenticate_user", END)

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

while True:
    user = input("User (q/Q to quit): ")
    if user in {"q", "Q"}:
        print("Conversation Terminated by User!")
        break
    output = None
    for output in graph.stream({"messages": [HumanMessage(content=user)]}, config=config, stream_mode="updates"):
        # print(output)
        last_message = next(iter(output.values()))["messages"][-1]
        last_message.pretty_print()

    
    





