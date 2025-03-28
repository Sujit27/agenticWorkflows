import streamlit as st
import json
import requests

st.title("Customer Support Bot")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

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

inputs = {"messages": prompt,"thread_id": "0"}

# Display assistant response in chat message container
with st.chat_message("assistant"):
    res = requests.post(url="http://127.0.0.1:8000/chat", data=json.dumps(inputs))
    response = st.write(res.text)

# Add assistant response to chat history
st.session_state.messages.append({"role": "assistant", "content": response})