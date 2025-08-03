# 🔧 Решение проблем Speech Analytics

## Проблема: Неправильная транскрипция видео

### Причины:
1. **Демо-режим был активен** - система показывала заготовленный текст
2. **Ошибки извлечения аудио** - проблемы с ffmpeg
3. **Низкое качество аудио** - шумы, тихий звук
4. **Неподдерживаемый формат** - старые кодеки

### Решения:

#### 1. Проверьте системные требования:
```bash
# Убедитесь что ffmpeg установлен
ffmpeg -version

# Для Windows (установка через chocolatey):
choco install ffmpeg

# Для Ubuntu/Debian:
sudo apt update
sudo apt install ffmpeg

# Для macOS:
brew install ffmpeg
```

#### 2. Проверьте формат файла:
- **Поддерживаемые видео**: MP4, AVI, MOV, MKV, FLV, WebM
- **Поддерживаемые аудио**: MP3, WAV, FLAC, AAC, OGG
- **Рекомендуемый формат**: MP4 с AAC аудио

#### 3. Проверьте качество аудио:
- Минимальная частота дискретизации: 16 кГц
- Рекомендуемая частота: 44.1 кГц или 48 кГц
- Формат: моно или стерео
- Битрейт: минимум 128 кбит/с

#### 4. Проверьте логи сервера:
```bash
# Запустите сервер с отладкой
python speech_analytics_server.py

# Проверьте логи в консоли на ошибки:
# - "ffmpeg not found"
# - "Audio extraction failed"
# - "Speech recognition error"
```

## Проблема: Протокол не создается

### Причины:
1. **Отсутствуют API ключи** - не настроены OpenAI/Mistral
2. **Нет транскрипции** - анализ не был выполнен
3. **Ошибки сети** - проблемы с доступом к API
4. **Превышены лимиты** - закончился баланс API

### Решения:

#### 1. Настройте API ключи:
```bash
# В файле .env добавьте:
OPENAI_API_KEY=sk-your-actual-key-here
MISTRAL_API_KEY=your-mistral-key-here

# Или через веб-интерфейс:
# POST /config/ai
{
  "openai_api_key": "sk-your-key",
  "mistral_api_key": "your-key"
}
```

#### 2. Проверьте баланс API:
- **OpenAI**: https://platform.openai.com/usage
- **Mistral**: https://console.mistral.ai/usage

#### 3. Проверьте доступность API:
```bash
# Тест OpenAI API
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Тест Mistral API  
curl https://api.mistral.ai/v1/models \
  -H "Authorization: Bearer $MISTRAL_API_KEY"
```

#### 4. Последовательность действий:
1. Загрузите файл
2. Нажмите "Анализировать" и дождитесь завершения
3. Убедитесь что появилась транскрипция
4. Перейдите на вкладку "Протоколы"
5. Выберите тип протокола
6. Нажмите "Создать протокол"

## Проблема: Медленная обработка

### Причины:
1. **Большой размер файла** - длинные записи
2. **Медленный интернет** - долгие запросы к API
3. **Высокая нагрузка API** - очереди у провайдеров

### Решения:

#### 1. Оптимизируйте файлы:
```bash
# Сжатие видео (ffmpeg)
ffmpeg -i input.mp4 -vn -acodec aac -ar 16000 -ac 1 output.aac

# Обрезка длинных записей
ffmpeg -i input.mp4 -t 300 -c copy output.mp4  # первые 5 минут
```

#### 2. Используйте сегментацию:
- Разделите длинные записи на части по 5-10 минут
- Обрабатывайте по частям
- Объединяйте результаты

#### 3. Выберите быстрый провайдер:
```python
# В .env файле:
PREFERRED_AI_PROVIDER=mistral  # обычно быстрее чем OpenAI
```

## Проблема: Ошибки при деплое на Amvera

### Причины:
1. **Отсутствует ffmpeg** - не установлен в контейнере
2. **Превышен лимит памяти** - большие файлы
3. **Таймауты** - долгая обработка

### Решения:

#### 1. Обновите Dockerfile:
```dockerfile
FROM python:3.9-slim

# Установка ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE $PORT

CMD gunicorn speech_analytics_server:app --bind 0.0.0.0:$PORT --timeout 300 --max-requests 1000
```

#### 2. Ограничьте размер файлов:
```python
# В speech_analytics_server.py
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@app.before_request
def limit_file_size():
    if request.content_length and request.content_length > MAX_FILE_SIZE:
        abort(413)  # Payload Too Large
```

#### 3. Добавьте обработку таймаутов:
```python
# В ai_integration.py
async def generate_response(self, prompt: str, system_prompt: str = "") -> Optional[str]:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            # ... код запроса
    except asyncio.TimeoutError:
        logger.error("API request timeout")
        return None
```

## Проблема: Низкое качество протоколов

### Причины:
1. **Плохая транскрипция** - шумы, неразборчивая речь
2. **Неподходящий промпт** - не тот тип анализа
3. **Неструктурированная встреча** - хаотичное обсуждение

### Решения:

#### 1. Улучшите качество аудио:
- Используйте внешний микрофон
- Записывайте в тихом помещении
- Говорите четко и громко
- Минимизируйте фоновые шумы

#### 2. Структурируйте встречи:
- Используйте повестку дня
- Четко формулируйте вопросы
- Резюмируйте принятые решения
- Назначайте ответственных и сроки

#### 3. Кастомизируйте промпты:
```javascript
// Пример специализированного промпта
const customPrompt = `
Проанализируйте техническое совещание и выделите:
1. Принятые архитектурные решения
2. Выбранные технологии и версии
3. Выявленные технические риски
4. Поставленные технические задачи с оценками времени
5. Вопросы для дальнейшего исследования

Сохраняйте все технические термины и версии.
`;
```

## Частые ошибки и решения

### "ffmpeg not found"
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg

# Windows
# Скачайте с https://ffmpeg.org/download.html
# Добавьте в PATH
```

### "No AI provider configured"
```bash
# Проверьте переменные окружения
echo $OPENAI_API_KEY
echo $MISTRAL_API_KEY

# Или установите через API
curl -X POST http://localhost:5000/config/ai \
  -H "Content-Type: application/json" \
  -d '{"openai_api_key": "sk-your-key"}'
```

### "Transcript not found"
1. Обязательно сначала выполните анализ файла
2. Дождитесь появления транскрипции
3. Только потом создавайте протоколы

### "Rate limit exceeded"
1. Проверьте лимиты API на платформе провайдера
2. Добавьте задержки между запросами
3. Используйте менее загруженного провайдера

## Логирование и отладка

### Включение подробных логов:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Проверка API запросов:
```bash
# Проверьте сетевые запросы в браузере (F12 -> Network)
# Найдите запросы к /analyze, /generate/protocol
# Проверьте статус коды и ответы
```

### Мониторинг производительности:
```python
import time

def monitor_performance(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.time() - start:.2f}s")
        return result
    return wrapper
```