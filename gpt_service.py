# gpt_service.py
from flask import Flask, request, jsonify
import openai
import os
import httpx
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
from openai.types.completion_usage import PromptTokensDetails

# OpenAI API 키


# 가격 기준(3.5)
PROMPT_COST = 0.5 / 1_000_000
COMPLETION_COST = 1.5 / 1_000_000
MAX_BUDGET = 5.0 # 달러 기준

# 누적 토근/요금 추적
used_tokens = 0
used_cost = 0.0

load_dotenv()   #.env 파일을 불러와 환경변수로 등록
API_KEY = os.getenv("TOGETHER_API_KEY")
print("API_KEY", API_KEY)

#Together.ai에서 사용할 모델(최신 고성능 무료 모델)
TOGETHER_MODEL = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
# 비용 기준( opneAI 대비 단가는 정확히 없지만, 대략 동일 기준 사용 가능)
PROMPT_COST = 0.5 / 1_000_000          # 입력 토큰 단가 (USD)
COMPLETION_COST = 1.5 / 1_000_000      # 출력 토큰 단가 (USD)
MAX_BUDGET = 5.0                       # 최대 허용 예산 (달러 기준)

# 사용량 추적 변수 (전역)
used_tokens = 0
used_cost = 0.0

async def ask_gpt_with_tracking(prompt: str) -> str:
    """
    Together.ai의 Mixtral 모델에 질문을 보내고 응답을 받아오는 함수,
    또한 토큰 수와 예상 비용을 추적해서 예산 초과 여부도 관리함.
    :param promt:
    :return:
    """
    global used_tokens, used_cost

    # 한도 초과 체크
    if used_cost >= MAX_BUDGET:
        return "! GPT 무료 사용 한도를 초과했습니다. 다음 달에 다시 이용해 주세요."

    try:
        # GPT 요청 메시지 구성: 항상 한국어로 답하라는 system  메시지 포함
        messages = [
            {"role": "system", "content": "당신은 친절하고 유익한 AI이며, 항상 한국어로 응답해야 합니다."},
            {"role": "user", "content": prompt}
        ]


        # 비동기 HTTP POST 요청으로 GPT 호출
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": TOGETHER_MODEL,

                    "messages": messages


                }
            )

            # 응답 JSON 파싱
            data = response.json()

            # 오류 으답일 경우 메시지 리턴
            if "error"  in data:
                return f"x GPT 오류: {data['error'].get('message', '알 수 없는 오류')}"

            # 응답 메시지 추출
            gpt_reply = data["choices"][0]["message"]["content"]

            # 사용량 추정(Together는 정확한 usage 제공 안 함 -> 임의 추정
            estimated_tokens = len(prompt) + len(gpt_reply)
            estimated_cost = estimated_tokens * (PROMPT_COST + COMPLETION_COST)

            # 사용량 누적
            used_tokens += estimated_tokens
            used_cost += estimated_cost

            # 콘솔 출력으로 사용량 추적
            print(f" 사용 토큰: {used_tokens}, 사용 비용: &{used_cost:.4f}")

            return gpt_reply

    except Exception as e:
        # 네트워크 또는 서버 오류 처리
        return f"X GPT 응답 실패: {str(e)}"













        """
        response = await client.chat.completions.create(
            model = "gpt-3.5-turbo",
            messages=[{"role": "user", "content": promt}]
        )
        usage = response.usage
        prompt_tk = usage.prompt_tokens
        completion_tk = usage.completion_tokens
        total_tk = usage.total_tokens

        # 비용 계산
        cost = prompt_tk * PROMPT_COST + completion_tk * COMPLETION_COST
        used_tokens += total_tk
        used_cost += cost

        print(f"GPT 사용량: {used_tokens} tokens, ${used_cost:.4f} 사용됨")

        return response.choices[0].message.content
        """
    except Exception as e:
        return f"X GPT 응답 실패: {e}"
