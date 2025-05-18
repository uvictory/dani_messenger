#main.py
import base64
import json

from typing import Optional
import aiosqlite
import openai
import packet
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from win32print import JOB_READ

from database import init_db, save_message, load_today_messages, init_read_state, save_read_count, \
    save_last_read_id, DB_PATH, load_last_read_id
from gpt_service import ask_gpt_with_tracking
import os
import uuid #  고유 reply_id 생성용

app = FastAPI()

# 전역으로 한 번만 변환해두고 캐싱
with open("images/ChatGPT.png", "rb") as f:
    gpt_icon_b64 = base64.b64encode(f.read()).decode("utf-8")

# 이후 응답마다 이 변수만 사용
gpt_profile = gpt_icon_b64


# CORS 설정: 모든 origin 허용 (개발 중에는 괜찮지만, 배포 시에는 제한하는 것이 안전)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 현재 연결된 클라이언트 {username: WebSocket}
connected_clients = {}
notice_clients = {}  # /notice/{username} for announcement

# 서버 시작 시 DB 초기화
@app.on_event("startup")
async def startup():
    await init_db()
    await init_read_state()
    print("✅ 서버 시작 및 DB 초기화 완료")

# ✅ 공지용 WebSocket 엔드포인트 추가
@app.websocket("/notice/{username}")
async def notice_socket(websocket: WebSocket, username: str):
    await websocket.accept()
    notice_clients[username] = websocket
    print(f"📢 공지 연결됨: {username}, 현재 notice_clients = {list(notice_clients.keys())}")


    try:
        while True:
            await websocket.receive_text()  # 연결 유지용 (아무 동작 없음)
    except WebSocketDisconnect:
        print(f"❌ 공지 연결 종료: {username}")
        notice_clients.pop(username, None)

# 공지 전송 함수 예시 (사용 시 호출)
async def broadcast_announcement(sender, message):
    print(f"📢 공지 브로드캐스트 시도: {sender} → {message}")  # ✅ 이 줄 추가

    packet = json.dumps({
        "type": "announcement",
        "sender": sender,
        "message": message
    })
    disconnected_users = []

    for user, client in list(notice_clients.items()):
        try:
            await client.send_text(packet)
        except Exception as e:
            print(f"⚠️ {user} 에게 공지 전송 실패: {e}")
            disconnected_users.append(user)

    # ✅ 끊긴 사용자 제거
    for user in disconnected_users:
        notice_clients.pop(user, None)
        print(f"( 공지용 )연결 끊긴 사용자 제거: {user}")
        await broadcast_user_list()  # 🧩 이 위치에서도 갱신해야 함

# GPT 에게 질문 요청 함수
async def ask_gpt(prompt: str) -> str:
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", # 또는 gpt-4
            messages=[{"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"GPT 오류: {str(e)}"

@app.websocket("/validate")
async def validate_nickname(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()
    nickname = data.get("nickname")  # ✅ 바로 사용

    try:
        if nickname in connected_clients:   # 접속 중인 사용자로 확인
            await websocket.send_text(json.dumps({"available": False}))
        else:
            await websocket.send_text(json.dumps({"available": True}))
    except Exception as e:
        print(f"⚠️ WebSocket 전송 실패: {e}")


# 웹소켓 핸들링
@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    connected_clients[username] = websocket
    print(f"📥 연결됨: {username}")

    """Websocket 연결 직후 -> 메시지+last_read_id 함께 전송"""
    # 사용자별 마지막 일긍 메시지 ID 로드
    last_read_id = await load_last_read_id(username)

    await broadcast_user_list() #여기에서만 호출, 유저리스트 갱신

    # DB에서 해당사용자의 읽은 메시지 수 조회
    #read_count = await load_read_count(username)
    #print(f"📌 {username}의 마지막 읽은 메시지 수: {read_count}")

    # 클라이언트가 연결되면 오늘 메시지 + 읽은 수 불러와서 전송
    history = await load_today_messages()

    try:
        # 클라이언트에게 히스토리 + 마지막 읽은 메시지 ID 함께 전송
        await websocket.send_text(json.dumps({
            "type": "history",
            "messages": history,
            "last_read_id": last_read_id
        }))
    except Exception as e:
        print(f"⚠️ WebSocket 전송 실패: {e}")


    print("📦 오늘 메시지 수:", len(history))
    print(" 마지막으로 읽은 메시지 id = ", last_read_id)

    # 이후 채팅 대기 루프 진입...

    try:
        while True:
            try:
                data = await websocket.receive_text()
            except RuntimeError:
                print("❌ 클라이언트가 먼저 연결을 끊음")
                break

            try:
                data_packet = json.loads(data)  # 클라이언트로부터 받은 JSON 메시지 파싱

                """개인 메시지 처리: packet -> data_packet 수정"""
                if data_packet.get("type") == "private_room":
                    sender = data_packet["sender"]
                    receiver = data_packet["receiver"]
                    msg = data_packet["message"]
                    target_ws = connected_clients.get(receiver)
                    sender_ws = connected_clients.get(sender)

                    if target_ws:
                        await target_ws.send_text(json.dumps({
                            "type": "private_room",
                            "sender": sender,
                            "receiver": receiver,
                            "message": msg
                        }))
                    if sender_ws:
                        await sender_ws.send_text(json.dumps({
                            "type": "private_room",
                            "sender": sender,
                            "receiver": receiver,
                            "message": msg
                        }))
                    continue    # 더 이상 처리하지 않고 다음 반복으로



                # 메시지 타입이 "update_read_id"일 경우 (앱 종료 직전 클라이언트에서 전송)
                if data_packet.get("type") == "update_read_id":
                    print("update_read_id")
                    await save_last_read_id(data_packet.get("username"), data_packet.get("message_id"))



                # 일반 메시지 수신 처리
                message_text = data_packet.get("message", "")
                profile_image = data_packet.get("profile", None)
                file_info = data_packet.get("file", None)  # ✅ 파일 정보 가져오기

                # 일반 메시지 저장 후 ID 획득
                message_id = await save_message(username, message_text)

                #await save_message(username, message_text)  # DB에 메시지 저장
                # ✅ 공지용 메시지인 경우 broadcast_announcement 호출
                if message_text.startswith("@"):
                    print("공지 출력", message_text)
                    await broadcast_announcement(username, message_text[1:].strip())


                # GPT 메시지인 경우
                if message_text.startswith('#'):     #gpt 메시지인지 확인
                    print("this is gpt message")
                    message = message_text

                    # GPT용 질문이면 응답 생성, # 제거
                    prompt = message.replace("#", "").strip()

                    # reply_id 고유값 생성
                    reply_id = f"gpt_{uuid.uuid4().hex[:8]}"    # 고유 ID 생성

                    # 1. 먼저 "답변 생성 중..." 프롬프트 클라이언트에 전송
                    thinking_packet = {
                        "type": "message",
                        "sender": "GPT",
                        "message": "⏳ 답변을 생성 중입니다", # 깜빡이는 건 클라이언트가 함
                        "profile": gpt_profile,
                        "reply_id": reply_id  # 고유 식별자 추가
                    }
                    await websocket.send_text(json.dumps(thinking_packet))

                    # 2. 실제 GPT 호출
                    gpt_response = await ask_gpt_with_tracking(prompt)

                    # 3. 실제 응답 전송
                    # GPT 응답을 질문자에게만 전달 ->
                    gpt_packet = {
                        "type": "message",
                        "sender": "GPT",
                        "message": gpt_response,
                        "profile": gpt_profile,
                        "reply_id": reply_id  # 고유 식별자 추가
                    }

                    #for client in connected_clients.values():
                        #await client.send_text(json.dumps(gpt_packet))
                    # 질문자에게만 답변
                    await websocket.send_text(json.dumps(gpt_packet))
                    #await websocket.send_text(json.dumps(gpt_packet))


                # 일반 텍스트/파일 메시지 처리
                else:
                    # 클라이언트에게 보낼 패킷 구성
                    message_packet = {
                        "type": "message", # 명시적으로 type 포함
                        "sender": username,
                        "message": message_text,
                        "profile": profile_image,
                        "id": message_id,
                    }

                    if file_info:
                        message_packet["file"] = file_info  # 파일 정보 포함

                    print(f"💬 메시지 수신 from {username}: {message_text} ")

                    #print("패킷 정보 보기",message_packet)
                    # 공백 메시지는 무시
                    if not message_text.strip() and not file_info:
                        print(f"⚠️ 공백 메시지 무시됨: {username}")
                        continue

                    # 전체 클라이언트에게 메시지 전송
                    for client in connected_clients.values():
                        await client.send_text(json.dumps(message_packet))




            except json.JSONDecodeError:
                print("❌ 메시지 파싱 실패")

    except WebSocketDisconnect:
        print(f"❌ 연결 종료: {username}")
        if username in connected_clients:
            del connected_clients[username]
        await broadcast_user_list() # 유저 리스트 갱신


# 유저 목록 브로드캐스트
async def broadcast_user_list():
    print("📡 유저 목록 전송")
    disconnected_clients = []
    users_list = list(connected_clients.keys()) # 유저 이름 리스트

    packet = json.dumps({
        "type" : "user_list",
        "users": users_list
    })

    for username, client in list(connected_clients.items()):  # ✅ 리스트로 복사
        try:
            await client.send_text(packet)
        except Exception as e:
            print(f"❌ 유저 목록 전송 실패: {username} → {e}")
            disconnected_clients.append(username)

    # 끊긴 클라이언트 제거
    for username in disconnected_clients:
        connected_clients.pop(username, None)  # 안전하게 제거

