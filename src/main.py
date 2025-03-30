from fastapi import FastAPI
from agentic_workflow import graph
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

app = FastAPI()

class ChatInput(BaseModel):
    messages: str
    thread_id: str

@app.post("/chat")
async def chat(input: ChatInput):
    config = {"configurable": {"thread_id": input.thread_id}}
    response = await graph.ainvoke({"messages": [HumanMessage(content=input.messages)]}, config=config)
    res_msg = response["messages"][-1].content
    res_state = response["current_process_identified"]
    return {"message":res_msg,"state":res_state}