import uuid
import getpass
import os
import streamlit as st

from langgraph.graph.message import add_messages
from typing import TypedDict, Annotated
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel
from typing import List, Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

os.environ["OPENAI_API_KEY"] = "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"
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ['LANGSMITH_ENDPOINT'] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "pr-authorized-someplace-95"

# Streamlit UI
st.title("User Story Generator")

prompt_system_task = """Your job is to gather information from the user about the User Story they need to create.

You should obtain the following information from them:

- Objective: the goal of the user story. should be concrete enough to be developed in 2 weeks.
- Success criteria the sucess criteria of the user story
- Plan_of_execution: the plan of execution of the initiative
- Deliverables: the deliverables of the initiative

If you are not able to discern this info, ask them to clarify! Do not attempt to wildly guess. 
Whenever the user responds to one of the criteria, evaluate if it is detailed enough to be a criterion of a User Story. If not, ask questions to help the user better detail the criterion.
Do not overwhelm the user with too many questions at once; ask for the information you need in a way that they do not have to write much in each response. 
Always remind them that if they do not know how to answer something, you can help them.

After you are able to discern all the information, call the relevant tool."""

class StateSchema(TypedDict):
    messages: Annotated[list, add_messages]

class UserStoryCriteria(BaseModel):
    """Instructions on how to prompt the LLM."""
    objective: str
    success_criteria: str
    plan_of_execution: str

def domain_state_tracker(messages):
    return [SystemMessage(content=prompt_system_task)] + messages

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)

llm_with_tool = llm.bind_tools([UserStoryCriteria])
workflow = StateGraph(StateSchema)

def call_llm(state: StateSchema):
    """
    talk_to_user node function, adds the prompt_system_task to the messages,
    calls the LLM and returns the response
    """
    messages = domain_state_tracker(state["messages"])
    response = llm_with_tool.invoke(messages)
    return {"messages": [response]}

workflow.add_node("talk_to_user", call_llm)
workflow.add_edge(START, "talk_to_user")

def finalize_dialogue(state: StateSchema):
    """
    Add a tool message to the history so the graph can see that it`s time to create the user story
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

prompt_generate_user_story = """Based on the following requirements, write a good user story:

{reqs}"""

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
    return [SystemMessage(content=prompt_generate_user_story.format(reqs=tool_call))] + other_msgs


def call_model_to_generate_user_story(state):
    messages = build_prompt_to_generate_user_story(state["messages"])
    response = llm.invoke(messages)
    return {"messages": [response]}

workflow.add_node("create_user_story", call_model_to_generate_user_story)

def define_next_action(state) -> Literal["finalize_dialogue", END]:
    messages = state["messages"]

    if isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
        return "finalize_dialogue"
    else:
        return END

workflow.add_conditional_edges("talk_to_user", define_next_action)
workflow.add_edge("finalize_dialogue", "create_user_story")
workflow.add_edge("create_user_story", END)

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": str(uuid.uuid4())}}

if "disabled" not in st.session_state:
    st.session_state["disabled"] = False

# Initialize chat history if not present
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_input := st.chat_input("How can I help ? enter q/Q to exit"):
    if user_input in ['q','Q']:
        st.session_state.messages = []
        with st.chat_message("assistant"):
                st.markdown("Restarting session, enter hi to start again")
    else:
        # Add user message to chat history
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        output = None
        for output in graph.stream({"messages": [HumanMessage(content=user_input)]}, config=config, stream_mode="updates"):
            last_message = next(iter(output.values()))["messages"][-1]
            # last_message.pretty_print()
            with st.chat_message("assistant"):
                st.markdown(last_message.content)
            st.session_state.messages.append({"role": "assistant", "content": last_message.content})
