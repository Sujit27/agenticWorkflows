# Graph based agentic workflow 

Python based framework for creating simple graph based agentic workflows

## Installation

```bash
pip install -r requirements.txt
```

## Usage

###Test on terminal
```bash
cd src
python agentic_workflow.py
```

###Run server
```bash
cd src
uvicorn main:app --reload
```

###API call
```bash
curl --location 'http://127.0.0.1:8000/chat' \
--header 'Content-Type: application/json' \
--data '{
           "messages": "Hello!",
           "thread_id": "0"
         }'
```

## Sample output
![sample conversation](https://github.com/Sujit27/agenticWorkflows/blob/main/output/agentic_conv_sample1.png)

## Sample Trace
![sample Langsmith Trace](https://github.com/Sujit27/agenticWorkflows/blob/main/output/agentic_graph_trace.png)
