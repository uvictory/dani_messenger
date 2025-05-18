# view_logs.py

import sqlite3


# 현재 폴더에 있는 DB 파일 열기
conn = sqlite3.connect("chat_log.db")
cursor = conn.cursor()

print("📋 저장된 채팅 로그:")
print("-" * 50)

# ✅ 1. 메시지 테이블 전체 출력
cursor.execute("SELECT id, sender, message, created_at FROM messages ORDER BY id ASC")
messages = cursor.fetchall()

for msg in messages:
    message_id, sender, message, timestamp = msg
    print(f"{message_id:03d}. [{timestamp}] {sender}: {message}")

print("\n📍 사용자별 마지막 읽은 메시지 (read_state):")
print("-" * 50)

# ✅ 2. 사용자별 마지막 읽은 메시지 출력
try:
    cursor.execute("SELECT username, last_read_id FROM read_state")
    read_states = cursor.fetchall()

    if read_states:
        for username, last_read_id in read_states:
            print(f"👤 {username} → 마지막으로 읽은 메시지 ID: {last_read_id}")
    else:
        print("⚠️ 아직 저장된 읽은 정보가 없습니다.")
except sqlite3.OperationalError as e:
    print(f"❌ 테이블 없음 또는 에러 발생: {e}")

conn.close()
