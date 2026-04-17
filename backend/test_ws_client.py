import json
import websocket

ws = websocket.WebSocket()
ws.connect("ws://127.0.0.1:8000/ws/conversation")

ws.send(json.dumps({
    "type": "start_session",
    "payload": {"language": "en"}
}))

ws.send(json.dumps({
    "type": "user_transcript",
    "payload": {"text": "Hello, Do you know who is Naruto?"}
}))

while True:
    try:
        print(ws.recv())
    except KeyboardInterrupt:
        break

ws.close()