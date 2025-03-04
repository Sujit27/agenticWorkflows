#!/usr/bin/env python
# coding: utf-8

import uuid
import getpass
import os
import json

from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

from langchain_openai import ChatOpenAI
from pydantic import BaseModel,Field
from typing import List, Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from prompt import prompt_system_task, prompt_auth_task, prompt_compare_data, prompt_payment_status_task
from utility import load_data_files,get_user_info_by_acc

from api_keys import openai_api_key,langsmith_api_key


os.environ["OPENAI_API_KEY"] = openai_api_key
os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
os.environ['LANGSMITH_ENDPOINT'] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "pr-authorized-someplace-95"

account_information_file_path = "accountInformation.csv"
credit_card_file_path = "creditCard.csv"
df_array = load_data_files(account_information_file_path,credit_card_file_path)
df_accountInformation = df_array[0]
df_creditCard = df_array[1]
print("User Database Loaded !")

class StateSchema(BaseModel):
    messages: Annotated[list, add_messages]
    user_provided_auth_fields: dict = Field(default=None, description="The authentication fields provided by the user")
    user_authenticated: int = Field(default=0, description="Whether user has been authenticated")
    user_account_fields: dict = Field(default=None, description="The account fields extracted for the user from database")
    user_payment_fields: dict = Field(default=None, description="The payment fields extracted for the user from database")

class Authentication(BaseModel):
    """Information about authentication fields"""
    account_number: int = Field(default=None, description="The policy number of the user")
    last_name: str = Field(default=None, description="The last name of the user")
    date_of_birth: str = Field(default=None, description="The date of birth of the user")

class ResponseFormatter(BaseModel):
    """Always use this tool to structure the output"""
    answer: str = Field(description="True or False depending if user authentication was successful or not")

@tool
def authentication(account_number: int,last_name: str,date_of_birth: str):
    """Gets user authetication information from database given a policy number"""
    provided_user_info = {"account_number":account_number,"last_name":last_name,"date_of_birth":date_of_birth}
    actual_user_info = get_user_info_by_acc(df_accountInformation,account_number)
    return actual_user_info


llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    
)

tools = [authentication]
tool_dict = {"authentication":authentication}

llm_to_authenticate = llm.bind_tools(tools)
llm_to_compare_data = llm.with_structured_output(ResponseFormatter)


def call_llm(state: StateSchema):
    """
    talk_to_user node function, adds the prompt_system_task to the messages,
    calls the LLM and returns the response
    """
    if state.user_authenticated==1:
        messages = [SystemMessage(content=prompt_system_task + \
            prompt_payment_status_task.format(user_credit_card_info=state.user_payment_fields,\
                user_account_info=state.user_account_fields))] + state.messages
    else:
        messages = [SystemMessage(content=prompt_system_task + prompt_auth_task)] + state.messages
    # messages = domain_state_tracker(state.messages,state.user_authenticated,state.user_payment_fields)
    response = llm_to_authenticate.invoke(messages)
    return {"messages": [response]}

def finalize_dialogue(state: StateSchema):
    """
    Add a tool message to the history so the graph can see that it`s time to autheticate
    """
    print("Tool called")
    tool_selected = state.messages[-1].tool_calls[0]
    tool_runnable = tool_dict[tool_selected['name'].lower()]
    tool_output = tool_runnable.invoke(tool_selected["args"])
    tool_message = ToolMessage(tool_output,tool_call_id=tool_selected["id"])
    return {"messages": [tool_message],"user_provided_auth_fields":tool_selected["args"]}


def call_model_to_authenticate(state: StateSchema):
    tool_message = state.messages[-1]
    user_provided_info = state.user_provided_auth_fields
    user_db_info = eval(tool_message.content)
    compare_data_prompt = [SystemMessage(content=prompt_compare_data.format(reqs=user_provided_info,user_info=user_db_info))]
    response = llm_to_compare_data.invoke(compare_data_prompt)
    if response.answer.lower()=='true':
        account_number = int(user_db_info["account_number"])
        user_payment_fields = get_user_info_by_acc(df_creditCard,account_number)
        return {"messages": [AIMessage(content=response.answer)],"user_authenticated":1,
                "user_payment_fields":user_payment_fields,"user_account_fields":user_db_info}
    else:
        return {"messages": [AIMessage(content=response.answer)]}
    

def define_next_action(state) -> Literal["finalize_dialogue", END]:
    messages = state.messages

    if isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return "finalize_dialogue"
    else:
        return END

workflow = StateGraph(StateSchema)
workflow.add_node("talk_to_user", call_llm)
workflow.add_edge(START, "talk_to_user")
workflow.add_node("finalize_dialogue", finalize_dialogue)
workflow.add_conditional_edges("talk_to_user", define_next_action)
workflow.add_node("authenticate_user", call_model_to_authenticate)
workflow.add_edge("finalize_dialogue", "authenticate_user")
workflow.add_edge("authenticate_user", END)
# workflow.add_edge("talk_to_user", END)

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

    
    





