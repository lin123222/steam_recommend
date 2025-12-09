"""
简易接口冒烟脚本：
1) 注册/登录一个测试用户
2) 调用健康检查、游戏列表、推荐接口

用法：
    python -m backend.tasks.smoke_api

可选环境变量：
    BASE_URL          默认 http://localhost:8000
    USERNAME          默认 smoke_user1
    PASSWORD          默认 password123
    REGISTER_PATH     默认 /api/v1/auth/register
    LOGIN_PATH        默认 /api/v1/auth/login
    GAMES_PATH        默认 /api/v1/games
    RECO_PATH         默认 /api/v1/recommendations
"""

import asyncio
import os
import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
USERNAME = os.getenv("USERNAME", "smoke_user1")
PASSWORD = os.getenv("PASSWORD", "password123")
REGISTER_PATH = os.getenv("REGISTER_PATH", "/api/v1/auth/register")
LOGIN_PATH = os.getenv("LOGIN_PATH", "/api/v1/auth/login")
GAMES_PATH = os.getenv("GAMES_PATH", "/api/v1/games")
RECO_PATH = os.getenv("RECO_PATH", "/api/v1/recommendations")


async def register(client: httpx.AsyncClient):
    try:
        r = await client.post(f"{BASE_URL}{REGISTER_PATH}", json={
            "username": USERNAME,
            "email": f"{USERNAME}@example.com",
            "password": PASSWORD
        })
        print("Register status:", r.status_code, r.text[:200])
    except Exception as e:
        print("Register failed:", e)


async def login(client: httpx.AsyncClient) -> str:
    r = await client.post(f"{BASE_URL}{LOGIN_PATH}", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    print("Login status:", r.status_code, r.text[:200])
    r.raise_for_status()
    data = r.json()
    # 兼容不同字段命名
    token = data.get("access_token") or data.get("token") or data.get("accessToken")
    if not token:
        raise RuntimeError("No access_token in login response")
    return token


async def call_health(client: httpx.AsyncClient):
    r = await client.get(f"{BASE_URL}/health")
    print("Health:", r.status_code, r.text[:200])


async def call_games(client: httpx.AsyncClient):
    r = await client.get(f"{BASE_URL}{GAMES_PATH}", params={"limit": 3})
    print("Games:", r.status_code, r.text[:200])


async def call_reco(client: httpx.AsyncClient, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.get(
        f"{BASE_URL}{RECO_PATH}",
        params={"user_id": 1, "topk": 5, "algorithm": "embedding"},
        headers=headers
    )
    print("Reco:", r.status_code, r.text[:200])


async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        await call_health(client)
        await register(client)
        token = await login(client)
        await call_games(client)
        await call_reco(client, token)


if __name__ == "__main__":
    asyncio.run(main())

