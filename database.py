# database.py
from typing import Optional

import aiosqlite
from datetime import datetime, date

# SQLite 파일 경로
DB_PATH = "chat_log.db"

# DB 초기화 함수 (서버 시작 시 1회 실행)
# 메시지 저장용 테이블이 없을 경우 생성
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 메시지 고유 ID
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL -- ISO 8601 형식(yyyy-mm--ddTHH:MM:SS)
            )
        """)
        await add_created_at_column()
        await db.commit()


# 메시지 저장 함수( 채팅 시마다 호출)
# sender와 message를 DB에 삽입, timestamp는 현재 시간 자동 생성, 새로 삽입된 ID 반환
async def save_message(sender: str, message: str) -> int:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO messages (sender, message, timestamp)
            VALUES (?, ?, ?)
        """, (sender, message, timestamp))
        await db.commit()
        return cursor.lastrowid # <- 삽입된 행의 ID 반환, timestamp 함께 반환

# 읽은 메시지 위치를 저장할 테이블 생성
async def init_read_state():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS read_state (
                username TEXT PRIMARY KEY,
                last_read_id INTEGER -- 마지막 읽은 메시지의 ID 저장
            )
        """)
        await db.commit()

# 읽은 메시지 수 저장
async def save_read_count(username: str, count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO read_state (username, count)
            VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET count=excluded.count
        """, (username, count))
        await db.commit()
"""
# 사용자의 마지막 읽은 메시지 수를 불러오는 함수
async def load_read_count(username: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT count FROM read_state WHERE username = ?", (username,)) as cursor:
            row = await cursor.fetchone()

            if row is not None:
                return row[0]   # 저장된 메시지 수 반환
            else:
                return 0 # 값이 없다면 처음 접속하 사용자 -> 0으로 초기화
"""
# 마지막 읽은 ID 불러오기
async def load_last_read_id(username: str) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_read_id FROM read_state WHERE username = ?", (username,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# 마지막 읽은 ID 저장하기
async def save_last_read_id(username: str, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO read_state (username, last_read_id)
            VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET last_read_id = excluded.last_read_id
        """, (username, message_id))
        await db.commit()




# 오늘 날짜의 메시지 불러오가ㅣ
# 서버에서 클라이언트가 접속하면 오늘 채팅 내용을 보내기 위해 호출
async def load_today_messages():
    today_str = date.today().isoformat()    # "2025-04-21"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
        SELECT id, sender, message, timestamp FROM messages
        WHERE DATE(timestamp) = ?
        ORDER BY id ASC
        """, (today_str,))
        rows = await cursor.fetchall()

    # 결과를 딕셔너리 리스트 형태로 반환
    return [
        {   "id": row[0],
            "sender": row[1],
            "message": row[2],
            "timestamp": row[3]
        }
        for row in rows
    ]


async def add_created_at_column():
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            # 1. 컬럼만 추가
            await db.execute("ALTER TABLE messages ADD COLUMN created_at TEXT")
            await db.commit()
            print("✅ created_at 컬럼 추가 완료 (기본값 없음)")

            # 2. 기존 데이터에 시간 채워주기
            await db.execute("UPDATE messages SET created_at = datetime('now') WHERE created_at IS NULL")
            await db.commit()
            print("✅ created_at 컬럼 추가 완료")
        except Exception as e:
            print("⚠️ 이미 컬럼이 있거나 실패: ", e)