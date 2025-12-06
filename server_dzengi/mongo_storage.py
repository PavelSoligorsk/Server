"""
🗄️ MONGODB ХРАНИЛИЩЕ
"""

import datetime
from typing import Dict, List
import requests
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# MongoDB подключение
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "dzengi_api"

# Подключаемся к MongoDB
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')  # Проверяем подключение
    db = client[DB_NAME]

    # РАЗНЫЕ КОЛЛЕКЦИИ
    payload_collection = db["payload"]  # Только подписки
    market_collection = db["market_data"]  # Данные токенов
    unknown_collection = db["unknown_data"]  # unknown.json данные

    print(f"✅ MongoDB подключен: {DB_NAME}")
    print(f"   📋 Коллекции: payload, market_data, unknown_data")

except ConnectionFailure as e:
    print(f"❌ Ошибка подключения к MongoDB: {e}")
    raise


# ========== PAYLOAD ФУНКЦИИ (только подписки) ==========

def check_symbol(symbol: str) -> bool:
    """Проверяет существование символа через API"""
    url = "https://api-adapter.dzengi.com/api/v1/depth"
    try:
        response = requests.get(
            url,
            params={'symbol': symbol.replace('_', '/')},
            headers={'Content-Type': '*/*'},
            timeout=5
        )
        return response.status_code == 200
    except:
        return False


def read_payload() -> dict:
    temp = payload_collection.find_one({})
    return {"symbols": temp.get("symbols", [])}


def save_payload(payload_data: dict):
    """ОБНОВЛЯЕТ payload (подписки) в MongoDB"""
    symbols_list = payload_data.get("symbols", [])

    # Ищем ЛЮБОЙ документ (как в read_payload)
    existing_doc = payload_collection.find_one({})

    if existing_doc:
        # ОБНОВЛЯЕМ существующий документ
        result = payload_collection.update_one(
            {"_id": existing_doc["_id"]},
            {
                "$set": {
                    "symbols": symbols_list,
                    "timestamp": datetime.datetime.utcnow()
                }
            }
        )
        print(f"✅ Документ ОБНОВЛЕН: {len(symbols_list)} символов")
    else:
        # Создаем новый если коллекция пуста
        document = {
            "symbols": symbols_list,
            "timestamp": datetime.datetime.utcnow()
        }
        payload_collection.insert_one(document)
        print(f"✅ Документ СОЗДАН: {len(symbols_list)} символов")

def write_payload(data: str, delete: bool = False) -> dict:
    """Добавляет или удаляет символ из подписок"""
    current_payload = read_payload()
    symbols_list = current_payload.get('symbols', [])
    data_formatted = data.replace('_', '/')

    try:
        if delete:
            if data_formatted not in symbols_list:
                raise ValueError(f"Символ {data_formatted} не найден")
            symbols_list.remove(data_formatted)
        else:
            if data_formatted in symbols_list:
                raise KeyError(f"Символ {data_formatted} уже существует")
            elif check_symbol(data_formatted):
                symbols_list.append(data_formatted)
            else:
                raise NameError(f"Символ {data_formatted} не найден на сервере")

        # ОБНОВЛЯЕМ payload
        save_payload({"symbols": symbols_list})
        return {200: "success"}

    except ValueError as e:
        return {404: str(e)}
    except KeyError as e:
        return {404: str(e)}
    except NameError as e:
        return {404: str(e)}
    except Exception as e:
        return {500: f"Ошибка сервера: {str(e)}"}


def clear_payload():
    """Очищает подписки (ОБНУЛЯЕТ список символов)"""
    save_payload({"symbols": []})
    print("✅ Подписки ОЧИЩЕНЫ (обнулены) в MongoDB")


# ========== MARKET DATA ФУНКЦИИ (данные токенов) ==========

def save_json_data(data: dict, filename: str = None) -> str:
    """Сохраняет JSON данные токенов в market_data коллекцию (ОБНОВЛЯЕТ документ токена)"""
    if "payload" not in data:
        data = {"payload": data}

    # Извлекаем имя символа
    symbol = data['payload'].get('symbolName', 'unknown')

    # Если filename не указан, создаем его из символа
    if not filename:
        filename = symbol.replace('/', '_')

    document = {
        "type": "market_data",
        "symbol": symbol,
        "data": data['payload'],
        "filename": filename,
        "timestamp": datetime.datetime.utcnow()
    }

    # ОБНОВЛЯЕМ существующий документ или создаем новый
    result = market_collection.update_one(
        {"symbol": symbol},  # Фильтр: ищем документ с таким символом
        {"$set": document},  # Обновляем все поля
        upsert=True  # Создать новый, если не найден
    )

    if result.upserted_id:
        print(f"✅ Документ токена СОЗДАН в MongoDB: {symbol}")
        return str(result.upserted_id)
    elif result.modified_count > 0:
        print(f"✅ Документ токена ОБНОВЛЕН в MongoDB: {symbol}")
        # Находим ID обновленного документа
        updated_doc = market_collection.find_one({"symbol": symbol})
        return str(updated_doc["_id"])
    else:
        print(f"ℹ️ Документ токена НЕ ИЗМЕНЕН: {symbol}")
        existing_doc = market_collection.find_one({"symbol": symbol})
        return str(existing_doc["_id"]) if existing_doc else ""


def load_json_data(filename: str) -> dict:
    """Загружает JSON данные токена из MongoDB"""
    # Пробуем найти по имени файла
    doc = market_collection.find_one(
        {"filename": filename},
        sort=[("timestamp", -1)]
    )

    # Если не найдено по имени файла, пробуем по символу
    if not doc:
        # Убираем .json и преобразуем к формату символа
        if filename.endswith('.json'):
            symbol = filename.replace('.json', '').replace('_', '/')
        else:
            symbol = filename.replace('_', '/')

        doc = market_collection.find_one(
            {"symbol": symbol},
            sort=[("timestamp", -1)]
        )

    if not doc:
        raise FileNotFoundError(f"Данные токена не найдены в MongoDB: {filename}")

    print(f"✅ Данные токена загружены из MongoDB: {filename}")
    return doc.get("data", {})


def save_unknown_data(data: dict) -> str:
    """Сохраняет unknown.json данные в отдельную коллекцию"""
    document = {
        "type": "unknown",
        "data": data,
        "timestamp": datetime.datetime.utcnow()
    }

    result = unknown_collection.insert_one(document)
    print(f"✅ Unknown данные сохранены в MongoDB")
    return str(result.inserted_id)


def load_unknown_data() -> dict:
    """Загружает unknown данные"""
    doc = unknown_collection.find_one(
        {"type": "unknown"},
        sort=[("timestamp", -1)]
    )

    if not doc:
        return {"subscriptions": {}}

    return doc.get("data", {})


def get_collection_stats() -> dict:
    """Получает статистику по коллекциям"""
    stats = {
        "payload": {
            "documents": payload_collection.count_documents({}),
            "subscriptions_count": 0
        },
        "market_data": {
            "documents": market_collection.count_documents({}),
            "unique_symbols": len(market_collection.distinct("symbol"))
        },
        "unknown_data": {
            "documents": unknown_collection.count_documents({})
        }
    }

    # Получаем количество подписок
    payload_doc = payload_collection.find_one({"type": "subscriptions"})
    if payload_doc:
        stats["payload"]["subscriptions_count"] = len(payload_doc.get("symbols", []))

    return stats