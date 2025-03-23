curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "messages": ["Hello, my name is agent0."],
           "thread_id": "0"
         }' &
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "messages": ["Hello, my name is agent1."],
           "thread_id": "1"
         }' &
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "messages": ["Hello, my name is agent2."],
           "thread_id": "2"
         }' &
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "messages": ["Hello, my name is agent3."],
           "thread_id": "3"
         }' &
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "messages": ["Hello, my name is agent4."],
           "thread_id": "4"
         }' &
curl -X POST "http://127.0.0.1:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
           "messages": ["Hello, my name is agent5."],
           "thread_id": "5"
         }' 