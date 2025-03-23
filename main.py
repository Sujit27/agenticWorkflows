from fastapi import FastAPI
from graph import graph
from pydantic import BaseModel

app = FastAPI()

class ChatInput(BaseModel):
    messages: list[str]
    thread_id: str

@app.post("/chat")
async def chat(input: ChatInput):
    config = {"configurable": {"thread_id": input.thread_id}}
    response = await graph.ainvoke({"messages": input.messages}, config=config)
    return response["messages"][-1].content