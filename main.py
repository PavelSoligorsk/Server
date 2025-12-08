"""
🏁 ГЛАВНЫЙ ФАЙЛ FASTAPI СЕРВЕРА
"""

import json
from typing import List
from fastapi import FastAPI, HTTPException
import uvicorn
import requests
from fastapi.middleware.cors import CORSMiddleware
import asyncio

# Импортируем функции из нашего проекта
from server_dzengi.handler import connection
from server_dzengi.mongo_storage import (
    load_json_data,
    write_payload,
    read_payload,
    save_json_data,
    clear_payload,
    save_unknown_data,
    load_unknown_data
)



# Создаем FastAPI приложение
app = FastAPI(
    title="Official CryptoKobra Api",
    description="API для работы с криптовалютными данными",
    docs_url="/",
    version="1.0.0"
)

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:9000",
]

# ДОБАВЬТЕ ЭТОТ БЛОК ↓
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", summary="Главная страница")
async def root():
    """Возвращает информацию о API"""
    return {
        "message": "🚀 CryptoKobra API с MongoDB!",
        "version": "1.0.0",
        "storage": "MongoDB",
        "collections": ["payload (подписки)", "market_data (данные токенов)", "unknown_data"],
        "endpoints": [
            {"GET /start/{time}": "Запустить сбор данных"},
            {"GET /get/{symbol}": "Получить данные токена по символу"},
            {"GET /get/all": "Все токены"},
            {"GET /add/{symbol}": "Добавить символ в подписки"},
            {"GET /get/payload": "Список подписок"},
            {"GET /payload/clear": "Очистить подписки"},
            {"GET /search/{name}": "Поиск символов"}
        ]
    }


@app.get("/start/{time}", summary="Время жизни сервера")
async def start(time: int = 5):
    """Запускает WebSocket соединение и сбор данных"""
    result = await connection(time)

    if result == 0:
        try:
            # Загружаем unknown данные из MongoDB
            unknown_data = load_unknown_data()

            # Фильтруем символы с статусом PROCESSED
            processed_symbols = []

            if "subscriptions" in unknown_data:
                processed_symbols = [
                    sym for sym, desc in unknown_data["subscriptions"].items()
                    if desc == 'PROCESSED'
                ]

            return 'success'

        except Exception as e:
            return 'failed'

    return 'failed'


@app.get("/get/{symbol}", summary="Получить данные токена по символу")
async def get_token(symbol: str):
    """Возвращает данные по конкретному символу из market_data"""
    try:
        # Преобразуем символ для поиска
        filename = symbol.replace('/', '_')
        data = load_json_data(filename)
        return data

    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/get/all/", summary="Получить все токены")
async def get_all():
    """Возвращает все доступные токены из market_data"""
    try:
        # Получаем текущие подписки (payload)
        current_payload = read_payload()
        subscribed_symbols = current_payload["symbols"]

        # Загружаем данные только для подписанных символов
        result = {}
        for symbol in subscribed_symbols:
            try:
                filename = symbol.replace('/', '_')
                result[symbol] = load_json_data(filename)
            except:
                continue

        return list(result.values())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/add/{symbol}", summary="Добавить символ в подписки")
async def add_token(symbol: str, delete: bool = False):
    """Добавляет или удаляет символ из подписок (payload коллекция)"""
    result = write_payload(symbol, delete)

    if 200 in result:
        return 'success'
    else:
        error_code = list(result.keys())[0]
        error_message = result[error_code]
        raise HTTPException(status_code=int(error_code), detail=error_message)


@app.get("/get/payload/", summary="Получить список подписок")
async def get_payload():
    try:
        current_payload = read_payload()
        return current_payload.get("symbols")
    except HTTPException as e:
        raise HTTPException(status_code=404, detail=str(e))
    # return {
    #     "symbols": subscribed_symbols,
    #     "count": len(subscribed_symbols),
    #     "collection": "payload",
    #     "storage": "MongoDB"
    # }


@app.get("/payload/clear/", summary="Очистить подписки")
async def clear_payload_endpoint():
    """Очищает подписки из payload коллекции"""
    clear_payload()
    return "status"


@app.get("/search/{name}", summary="Поиск символов по названию")
async def search_symbols(name: str):
    """Ищет символы на бирже по названию"""
    try:
        response = requests.get(
            "https://api-adapter.dzengi.com/api/v1/exchangeInfo",
            timeout=10
        )

        symbols_data = response.json()
        all_symbols = [symbol['symbol'] for symbol in symbols_data.get("symbols", [])]

        # Ищем совпадения
        found_symbols = []
        search_lower = name.lower()

        for symbol in all_symbols:
            if search_lower in symbol.lower():
                found_symbols.append(symbol)

        if not found_symbols:
            raise HTTPException(status_code=404, detail="Символы не найдены")

        return found_symbols


    except requests.exceptions.Timeout:
        raise HTTPException(status_code=408, detail="Таймаут при поиске символов")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", summary="Проверка здоровья сервера")
async def health_check():
    """Проверяет работоспособность сервера и MongoDB"""
    from server_dzengi.mongo_storage import (
        payload_collection,
        market_collection,
        unknown_collection
    )

    try:
        payload_count = payload_collection.count_documents({})
        market_count = market_collection.count_documents({})
        unknown_count = unknown_collection.count_documents({})

        return {
            "status": "healthy",
            "mongodb": "connected",
            "collections": {
                "payload (подписки)": payload_count,
                "market_data (данные токенов)": market_count,
                "unknown_data": unknown_count
            },
            "storage": "MongoDB"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "mongodb": "disconnected",
            "error": str(e)
        }


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 CRYPTOKOBRA API С MONGODB")
    print("=" * 50)
    print("🗄️ Хранилище: MongoDB")
    print("📊 Коллекции:")
    print("   📋 payload - только управление подписками")
    print("   📈 market_data - данные токенов из WebSocket")
    print("   ❓ unknown_data - unknown.json данные")
    print("🌐 API: http://localhost:8000")
    print("📚 Документация: http://localhost:8000/docs")
    print("=" * 50)

    # Запускаем сервер
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
