"""
🗄️ MONGODB ХРАНИЛИЩЕ (Ленивая инициализация)
"""

import os
import datetime
import logging
from typing import Dict, List, Optional
import requests
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# Настройка логирования
logger = logging.getLogger(__name__)

# Получаем настройки из переменных окружения
MONGO_URI = os.getenv("MONGO_URI", "mongodb://host.docker.internal:27017")
DB_NAME = os.getenv("DB_NAME", "dzengi_api")

# Глобальные переменные для ленивой инициализации
_client = None
_db = None
_payload_collection = None
_market_collection = None
_unknown_collection = None


# ========== ЛЕНИВАЯ ИНИЦИАЛИЗАЦИЯ ==========

def init_mongo_connection() -> None:
    """Инициализирует подключение к MongoDB при первом вызове"""
    global _client, _db, _payload_collection, _market_collection, _unknown_collection

    if _client is None:
        try:
            logger.info(f"🔄 Попытка подключения к MongoDB: {MONGO_URI}")
            _client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000
            )

            # Проверяем подключение
            _client.admin.command('ping')

            # Получаем базу данных
            _db = _client[DB_NAME]

            # Инициализируем коллекции
            _payload_collection = _db["payload"]
            _market_collection = _db["market_data"]
            _unknown_collection = _db["unknown_data"]

            logger.info(f"✅ MongoDB подключен: {DB_NAME}")
            logger.info("   📋 Коллекции: payload, market_data, unknown_data")

        except ConnectionFailure as e:
            logger.error(f"❌ Ошибка подключения к MongoDB: {e}")
            _client = None
            _db = None
            _payload_collection = None
            _market_collection = None
            _unknown_collection = None
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при подключении к MongoDB: {e}")
            _client = None
            _db = None
            _payload_collection = None
            _market_collection = None
            _unknown_collection = None
            raise


def get_client() -> Optional[MongoClient]:
    """Возвращает клиент MongoDB (ленивая инициализация)"""
    if _client is None:
        init_mongo_connection()
    return _client


def get_db():
    """Возвращает базу данных (ленивая инициализация)"""
    if _db is None:
        init_mongo_connection()
    return _db


def get_payload_collection():
    """Возвращает коллекцию payload (ленивая инициализация)"""
    if _payload_collection is None:
        init_mongo_connection()
    return _payload_collection


def get_market_collection():
    """Возвращает коллекцию market_data (ленивая инициализация)"""
    if _market_collection is None:
        init_mongo_connection()
    return _market_collection


def get_unknown_collection():
    """Возвращает коллекцию unknown_data (ленивая инициализация)"""
    if _unknown_collection is None:
        init_mongo_connection()
    return _unknown_collection


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
    """Читает payload из MongoDB"""
    collection = get_payload_collection()
    if collection is None:
        logger.warning("MongoDB недоступна, возвращаем пустой payload")
        return {"symbols": []}

    temp = collection.find_one({})
    if temp:
        return {"symbols": temp.get("symbols", [])}
    return {"symbols": []}


def save_payload(payload_data: dict):
    """ОБНОВЛЯЕТ payload (подписки) в MongoDB"""
    collection = get_payload_collection()
    if collection is None:
        logger.error("MongoDB недоступна, не могу сохранить payload")
        return

    symbols_list = payload_data.get("symbols", [])

    # Ищем ЛЮБОЙ документ
    existing_doc = collection.find_one({})

    if existing_doc:
        # ОБНОВЛЯЕМ существующий документ
        result = collection.update_one(
            {"_id": existing_doc["_id"]},
            {
                "$set": {
                    "symbols": symbols_list,
                    "timestamp": datetime.datetime.utcnow()
                }
            }
        )
        logger.info(f"✅ Документ ОБНОВЛЕН: {len(symbols_list)} символов")
    else:
        # Создаем новый если коллекция пуста
        document = {
            "symbols": symbols_list,
            "timestamp": datetime.datetime.utcnow()
        }
        collection.insert_one(document)
        logger.info(f"✅ Документ СОЗДАН: {len(symbols_list)} символов")


def write_payload(data: str, delete: bool = False) -> dict:
    """Добавляет или удаляет символ из подписок"""
    try:
        current_payload = read_payload()
        symbols_list = current_payload.get('symbols', [])
        data_formatted = data.replace('_', '/')

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
        logger.error(f"ValueError: {e}")
        return {404: str(e)}
    except KeyError as e:
        logger.error(f"KeyError: {e}")
        return {404: str(e)}
    except NameError as e:
        logger.error(f"NameError: {e}")
        return {404: str(e)}
    except Exception as e:
        logger.error(f"Ошибка сервера: {e}")
        return {500: f"Ошибка сервера: {str(e)}"}


def clear_payload():
    """Очищает подписки (ОБНУЛЯЕТ список символов)"""
    save_payload({"symbols": []})
    logger.info("✅ Подписки ОЧИЩЕНЫ (обнулены) в MongoDB")


# ========== MARKET DATA ФУНКЦИИ (данные токенов) ==========

def save_json_data(data: dict, filename: str = None) -> str:
    """Сохраняет JSON данные токенов в market_data коллекцию"""
    collection = get_market_collection()
    if collection is None:
        logger.error("MongoDB недоступна, не могу сохранить данные")
        return ""

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
    result = collection.update_one(
        {"symbol": symbol},  # Фильтр: ищем документ с таким символом
        {"$set": document},  # Обновляем все поля
        upsert=True  # Создать новый, если не найден
    )

    if result.upserted_id:
        logger.info(f"✅ Документ токена СОЗДАН в MongoDB: {symbol}")
        return str(result.upserted_id)
    elif result.modified_count > 0:
        logger.info(f"✅ Документ токена ОБНОВЛЕН в MongoDB: {symbol}")
        # Находим ID обновленного документа
        updated_doc = collection.find_one({"symbol": symbol})
        return str(updated_doc["_id"])
    else:
        logger.info(f"ℹ️ Документ токена НЕ ИЗМЕНЕН: {symbol}")
        existing_doc = collection.find_one({"symbol": symbol})
        return str(existing_doc["_id"]) if existing_doc else ""


def load_json_data(filename: str) -> dict:
    """Загружает JSON данные токена из MongoDB"""
    collection = get_market_collection()
    if collection is None:
        logger.error("MongoDB недоступна, не могу загрузить данные")
        raise FileNotFoundError(f"MongoDB недоступна: {filename}")

    # Пробуем найти по имени файла
    doc = collection.find_one(
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

        doc = collection.find_one(
            {"symbol": symbol},
            sort=[("timestamp", -1)]
        )

    if not doc:
        raise FileNotFoundError(f"Данные токена не найдены в MongoDB: {filename}")

    logger.info(f"✅ Данные токена загружены из MongoDB: {filename}")
    return doc.get("data", {})


def save_unknown_data(data: dict) -> str:
    """Сохраняет unknown.json данные в отдельную коллекцию"""
    collection = get_unknown_collection()
    if collection is None:
        logger.error("MongoDB недоступна, не могу сохранить unknown данные")
        return ""

    document = {
        "type": "unknown",
        "data": data,
        "timestamp": datetime.datetime.utcnow()
    }

    result = collection.insert_one(document)
    logger.info(f"✅ Unknown данные сохранены в MongoDB")
    return str(result.inserted_id)


def load_unknown_data() -> dict:
    """Загружает unknown данные"""
    collection = get_unknown_collection()
    if collection is None:
        logger.warning("MongoDB недоступна, возвращаем пустые unknown данные")
        return {"subscriptions": {}}

    doc = collection.find_one(
        {"type": "unknown"},
        sort=[("timestamp", -1)]
    )

    if not doc:
        return {"subscriptions": {}}

    return doc.get("data", {})


def get_collection_stats() -> dict:
    """Получает статистику по коллекциям"""
    try:
        payload_coll = get_payload_collection()
        market_coll = get_market_collection()
        unknown_coll = get_unknown_collection()

        if not all([payload_coll, market_coll, unknown_coll]):
            return {
                "error": "MongoDB недоступна",
                "payload": {"documents": 0, "subscriptions_count": 0},
                "market_data": {"documents": 0, "unique_symbols": 0},
                "unknown_data": {"documents": 0}
            }

        stats = {
            "payload": {
                "documents": payload_coll.count_documents({}),
                "subscriptions_count": 0
            },
            "market_data": {
                "documents": market_coll.count_documents({}),
                "unique_symbols": len(market_coll.distinct("symbol"))
            },
            "unknown_data": {
                "documents": unknown_coll.count_documents({})
            }
        }

        # Получаем количество подписок
        payload_doc = payload_coll.find_one({"type": "subscriptions"})
        if payload_doc:
            stats["payload"]["subscriptions_count"] = len(payload_doc.get("symbols", []))
        else:
            # Ищем в любом документе
            any_doc = payload_coll.find_one({})
            if any_doc:
                stats["payload"]["subscriptions_count"] = len(any_doc.get("symbols", []))

        return stats
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return {
            "error": str(e),
            "payload": {"documents": 0, "subscriptions_count": 0},
            "market_data": {"documents": 0, "unique_symbols": 0},
            "unknown_data": {"documents": 0}
        }


# ========== АЛИАСЫ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ ==========

# Свойства для импорта (не вызываются при импорте, только при доступе)
@property
def payload_collection():
    return get_payload_collection()


@property
def market_collection():
    return get_market_collection()


@property
def unknown_collection():
    return get_unknown_collection()


# ========== ИНИЦИАЛИЗАЦИЯ ПРИ ИМПОРТЕ ==========

# Только логирование, без подключения к БД
logger.info(f"🗄️ MongoDB хранилище инициализировано")
logger.info(f"   URI: {MONGO_URI}")
logger.info(f"   База данных: {DB_NAME}")
logger.info("   Режим: ленивая инициализация (подключение при первом обращении)")