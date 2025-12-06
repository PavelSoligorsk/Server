"""
📡 WEBSOCKET КЛИЕНТ
"""

import asyncio
import websockets
import hmac
import hashlib
import time
from typing import Dict, Any
import json

# Импортируем MongoDB функции
from server_dzengi.mongo_storage import save_json_data, save_unknown_data


class SocketClient:
    def __init__(self, base_url: str = None, api_key: str = '', api_secret: str = ''):
        self.base_url = base_url or 'wss://api-adapter.dzengi.com/connect'
        self.api_key = api_key
        self.api_secret = api_secret
        self.websocket = None
        self.correlation_id = 0
        self.is_connected = False

    async def connect(self):
        """Подключение к WebSocket"""
        try:
            self.websocket = await websockets.connect(self.base_url, ping_timeout=1)
            self.is_connected = True
            print(f"✅ WebSocket подключен к {self.base_url}")

            # Запускаем прослушивание
            asyncio.create_task(self._listen())
            # Запускаем heartbeat
            asyncio.create_task(self._heartbeat())

        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")

    async def _listen(self):
        """Прослушивание входящих сообщений"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)

                    # Определяем тип данных
                    symbol = data.get('symbol', '')
                    payload = data.get('payload', {})

                    if symbol == "unknown":
                        # Сохраняем unknown данные
                        save_unknown_data(payload)
                        print(f"📥 Unknown данные сохранены в MongoDB")
                    else:
                        # Сохраняем данные токена в market_data
                        save_json_data(data)
                        print(f"📥 Данные токена сохранены в market_data")

                    # Выводим в консоль
                    print('\033[93mПолучены данные:\033[0m')
                    print(json.dumps(data, indent=2, ensure_ascii=False))

                except json.JSONDecodeError:
                    print(f"📥 Получен не-JSON текст: {message[:100]}...")
                except Exception as e:
                    print(f"⚠️ Ошибка обработки сообщения: {e}")

        except Exception as e:
            print(f"❌ Ошибка прослушивания: {e}")
            self.is_connected = False

    async def _heartbeat(self):
        """Отправка ping сообщений"""
        while self.is_connected:
            try:
                if self.websocket:
                    await self.websocket.ping()
                    print("💓 PING")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"💔 Heartbeat error: {e}")
                self.is_connected = False
                break

    def _get_hash(self, payload: Dict[str, Any]) -> str:
        """Генерация подписи для приватных запросов"""
        sorted_payload = sorted(payload.items())
        payload_str = "&".join([f"{key}={value}" for key, value in sorted_payload])

        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    async def send_message(self, destination: str, payload: Dict[str, Any] = None, access: str = None):
        """Отправка сообщения"""
        if not self.is_connected or not self.websocket:
            print("⚠️ WebSocket не подключен")
            return

        if payload is None:
            payload = {}

        request = {
            "destination": destination,
            "correlationId": self.correlation_id,
            "payload": payload.copy()
        }

        self.correlation_id += 1

        if access == 'private':
            request["payload"]["timestamp"] = int(time.time() * 1000)
            request["payload"]["apiKey"] = self.api_key
            request["payload"]["signature"] = self._get_hash(request["payload"])

        message = json.dumps(request)

        print('\033[93m📤 Отправка сообщения:\033[0m')
        print(message)

        await self.websocket.send(message)

    async def close(self):
        """Закрытие соединения"""
        self.is_connected = False
        if self.websocket:
            await self.websocket.close()
        print("🔌 WebSocket соединение закрыто")