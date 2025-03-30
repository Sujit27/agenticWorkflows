import streamlit as st
import json
import requests
import random

st.title("Customer Support Bot")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
if "state" not in st.session_state:
    st.session_state.state = 0

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("How can I help"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

inputs = {"messages": prompt,"thread_id": str(st.session_state.state)}

# Display assistant response in chat message container
with st.chat_message("assistant"):
    res = requests.post(url="http://127.0.0.1:8000/chat", data=json.dumps(inputs))
    if "message" in res.json():
        out_msg = res.json()["message"]
        out_state = res.json()["state"]
        if int(out_state) == 100:
            st.session_state.state = random.randint(1,1000)
    else:
        out_msg = "Hi, there"
    response = st.write(out_msg)
    

# Add assistant response to chat history
st.session_state.messages.append({"role": "assistant", "content": out_msg})
# print(st.session_state.messages)