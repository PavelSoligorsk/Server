FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Исправляем mongo_storage.py ПЕРЕД запуском
RUN sed -i "s/localhost:27017/mongodb:27017/g" server_dzengi/mongo_storage.py && \
    sed -i "s/client.admin.command('ping')  # Проверяем подключение/pass  # Пропускаем проверку при импорте/g" server_dzengi/mongo_storage.py

CMD ["python", "main.py"]