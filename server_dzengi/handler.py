"""
🔌 HANDLER ДЛЯ ПОДКЛЮЧЕНИЯ К API
"""

import asyncio
from server_dzengi.SocketClient import SocketClient
from server_dzengi.mongo_storage import read_payload
from server_dzengi.mongo_storage import load_json_data

# API ключи (заполните своими)
API_KEY = ''
API_SECRET = ''


async def socket() -> SocketClient:
    """Создает и подключает WebSocket клиент"""
    socket_api = SocketClient(api_key=API_KEY, api_secret=API_SECRET)
    await socket_api.connect()
    await asyncio.sleep(1)
    print("🔌 WebSocket готов к работе")
    return socket_api


async def connection(time: int = 5):
    """Основная функция подключения"""
    print(f"🚀 Запуск connection на {time} секунд...")

    # Подключаемся к WebSocket
    socket1 = await socket()

    if not socket1:
        print("❌ Не удалось подключиться к WebSocket")
        return 1

    try:
        # Загружаем payload из MongoDB
        payloads = read_payload()
        print(f"📋 Загружено символов: {len(payloads.get('symbols', []))}")

        # Подписываемся на рыночные данные
        await socket1.send_message("marketData.subscribe", payload=payloads)
        print("✅ Подписка на marketData оформлена")

        # Ждем указанное время
        print(f"⏳ Сбор данных в течение {time} секунд...")
        await asyncio.sleep(time)

        print("✅ Сбор данных завершен")
        return 0

    except Exception as e:
        print(f"❌ Ошибка в connection: {e}")
        return 1

    finally:
        # Закрываем соединение
        await socket1.close()
        print("🔌 WebSocket соединение закрыто")