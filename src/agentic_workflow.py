#!/usr/bin/env python
# coding: utf-8

import uuid
import getpass
import os
import json

from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage, RemoveMessage
from langchain_core.tools import tool

from langchain_openai import ChatOpenAI
from pydantic import BaseModel,Field
from typing import List, Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from prompt import prompt_system_task, prompt_auth_task, prompt_compare_data,\
     prompt_payment_status_task, prompt_process_identification_task,\
        prompt_make_payment_task,prompt_update_address_task,prompt_summarize,summary_placeholder
from utility import load_data_files,get_user_info_by_acc,make_payment,update_address

# from api_keys import openai_api_key,langsmith_api_key
from dotenv import load_dotenv
load_dotenv()


os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
os.environ['LANGSMITH_ENDPOINT'] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "pr-authorized-someplace-95"

account_information_file_path = "../data/accountInformation.csv"
credit_card_file_path = "../data/creditCard.csv"
df_array = load_data_files(account_information_file_path,credit_card_file_path)
df_accountInformation = df_array[0]
df_creditCard = df_array[1]
print("User Database Loaded !")

llm_light = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    
)

llm_heavy = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    
)

class StateSchema(BaseModel):
    messages: Annotated[list, add_messages]
    summary: str = Field(default="", description="Summary of the conversation")
    user_authenticated: int = Field(default=0, description="Whether user has been authenticated")
    user_account_fields: dict = Field(default=None, description="The account fields extracted for the user from database")
    user_payment_fields: dict = Field(default=None, description="The payment fields extracted for the user from database")
    current_process_identified: int = Field(default=None, description="The process category identified from user query")

class DataCompare(BaseModel):
    """Compare data fields to check if they match"""
    answer: int = Field(description="1 or 0 depending if the data fields' was successful or not")

class ProcessIdentify(BaseModel):
    """Identify the right process category according to user request"""
    processIdentified: int = Field(description="1,2,3 or 100 depending on the process Category identified")

class makePayment(BaseModel):
    """Make credit card bill payment given once the user confirm to pay FULL or MIN
    """
    payment_mode: str = Field(description="FULL or MIN depending if the user wants to pay in full or minimum amount due")

class updateAddress(BaseModel):
    """Update address for the user once house number, street name and zip code are provided
    """
    house_number: int = Field(description="House number in new address provided by user")
    street_name: str = Field(description="Street name in new address provided by user")
    zip_code: str = Field(description="Zip Code in new address provided by user")

llm_to_compare_data = llm_light.with_structured_output(DataCompare)
llm_to_identify_process = llm_light.with_structured_output(ProcessIdentify)

@tool
def authentication(account_number: int,last_name: str,date_of_birth: str):
    """Gets user authetication information from database given a policy number, returns
    true if aunthenticated succesfully, else returns false"""
    provided_user_info = {"account_number":account_number,"last_name":last_name,"date_of_birth":date_of_birth}
    actual_user_info = get_user_info_by_acc(df_accountInformation,account_number)
    compare_data_prompt = [SystemMessage(content=prompt_compare_data.format(reqs=provided_user_info,user_info=actual_user_info))]
    response = llm_to_compare_data.invoke(compare_data_prompt)
    return int(response.answer),actual_user_info


tools = [authentication,makePayment,updateAddress]
tool_dict = {"authentication":authentication}

llm_with_tools = llm_light.bind_tools(tools)


def identify_process(state: StateSchema):
    """
    Identify the category of the current process to be followed based on the past conversation and latest user utterance
    """
    if state.user_authenticated!=1:
        process_identified=0
    else:
        messages = [SystemMessage(content=prompt_system_task + \
            prompt_process_identification_task + \
                summary_placeholder.format(existing_summary=state.summary))] + state.messages
        process_identified = llm_to_identify_process.invoke(messages).processIdentified

    return {"messages": [AIMessage(content=str(process_identified))],\
        "current_process_identified":process_identified}


def call_llm(state: StateSchema):
    """
    talk_to_user node function, adds the prompt_system_task to the messages,
    calls the LLM and returns the response
    """
    if state.user_authenticated==1:
        if state.current_process_identified==1:
            messages = [SystemMessage(content=prompt_system_task + \
                prompt_payment_status_task.format(user_credit_card_info=state.user_payment_fields,\
                    user_account_info=state.user_account_fields) + \
                        summary_placeholder.format(existing_summary=state.summary))] + state.messages
        elif state.current_process_identified==2:
            messages = [SystemMessage(content=prompt_system_task + \
                prompt_make_payment_task.format(user_credit_card_info=state.user_payment_fields,\
                    ) + summary_placeholder.format(existing_summary=state.summary))] + state.messages
        elif state.current_process_identified==3:
            messages = [SystemMessage(content=prompt_system_task + \
                prompt_update_address_task + summary_placeholder.format(existing_summary=state.summary))] + state.messages
        else:
            messages = [SystemMessage(content=prompt_system_task + \
                prompt_payment_status_task.format(user_credit_card_info=state.user_payment_fields,\
                    user_account_info=state.user_account_fields) + \
                        summary_placeholder.format(existing_summary=state.summary))] + state.messages
    else:
        messages = [SystemMessage(content=prompt_system_task + prompt_auth_task.format(\
            is_auth_completed=state.user_authenticated) + \
                summary_placeholder.format(existing_summary=state.summary))] + state.messages
    response = llm_with_tools.invoke(messages)    
    return {"messages": [response],"current_process_identified":state.current_process_identified}

def execute_tool(state: StateSchema):
    """
    Add a tool message to the history so the graph can see that it`s time to autheticate
    """
    tool_selected = state.messages[-1].tool_calls[0]
    if tool_selected['name'] == 'authentication':
        tool_runnable = tool_dict[tool_selected['name']]
        is_authenticated,user_db_info = tool_runnable.invoke(tool_selected["args"])
        if is_authenticated==1:
            tool_message = ToolMessage(is_authenticated,tool_call_id=tool_selected["id"])
            user_payment_fields = get_user_info_by_acc(df_creditCard,user_db_info["account_number"])
            return {"messages": [tool_message],"user_authenticated":1,\
                "user_payment_fields":user_payment_fields,"user_account_fields":user_db_info}
        else:
            tool_message = ToolMessage(user_db_info,tool_call_id=tool_selected["id"])
            return {"messages": [tool_message]}

    elif tool_selected['name'] == 'makePayment':
        user_account_fields,user_payment_fields = make_payment(state.user_payment_fields,\
            state.user_account_fields,tool_selected["args"]['payment_mode'])
        tool_message = ToolMessage("Payment Completed",tool_call_id=tool_selected["id"])
        return {"messages": [tool_message],\
                "user_payment_fields":user_payment_fields,"user_account_fields":user_account_fields}

    elif tool_selected['name'] == 'updateAddress':
        user_account_fields = update_address(state.user_account_fields,tool_selected["args"]["house_number"],\
            tool_selected["args"]["street_name"],tool_selected["args"]["zip_code"])
        tool_message = ToolMessage("Address Update Completed",tool_call_id=tool_selected["id"])
        return {"messages": [tool_message],\
                "user_account_fields":user_account_fields}


def response_generator(state: StateSchema):
    messages = [SystemMessage(content=prompt_system_task + \
            prompt_payment_status_task.format(user_credit_card_info=state.user_payment_fields,\
                user_account_info=state.user_account_fields) + \
                    summary_placeholder.format(existing_summary=state.summary))] + state.messages
    response = llm_light.invoke(messages)
    return {"messages": [response]}

def define_next_action(state) -> Literal["execute_tool", END]:
    messages = state.messages

    if isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return "execute_tool"
    else:
        return END

def summarize_conversation(state: StateSchema):
    # First, we summarize the conversation
    messages = [SystemMessage(content=prompt_summarize.format(existing_summary=state.summary))] + state.messages
    response = llm_heavy.invoke(messages)
    # We now need to delete messages that we no longer want to show up
    # I will delete all but the last two messages, but you can change this
    delete_messages = [RemoveMessage(id=m.id) for m in state.messages[:-1]]
    return {"summary": response.content, "messages": delete_messages}

workflow = StateGraph(StateSchema)
workflow.add_node("identify_process", identify_process)
workflow.add_edge(START, "identify_process")
workflow.add_node("talk_to_user", call_llm)
workflow.add_edge("identify_process", "talk_to_user")
workflow.add_node("execute_tool", execute_tool)
workflow.add_conditional_edges("talk_to_user", define_next_action)
workflow.add_node("response_generator",response_generator)
workflow.add_edge("execute_tool", "response_generator")
workflow.add_node("summarize_conversation",summarize_conversation)
workflow.add_edge("response_generator", "summarize_conversation")
workflow.add_edge("summarize_conversation", END)

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

def main():
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    quit_condition = False
    while True:
        
        if quit_condition:
            break
        
        user = input("User (q/Q to quit): ")
        if user in {"q", "Q"}:
            print("Conversation Terminated by User!")
            break
        
        output = graph.invoke({"messages": [HumanMessage(content=user)]}, config=config)
        msg = output['messages'][-1].content
        print(f"Agent: {msg}")

if __name__=="__main__":
    main()


    
    





