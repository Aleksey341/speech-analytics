# 🚀 Пошаговое развертывание Speech Analytics на сервере

## 📋 Выбор платформы

### Рекомендуемые платформы:
1. **Amvera Cloud** (Россия) - простой деплой
2. **VPS/Dedicated** - полный контроль
3. **Docker** - контейнеризация
4. **Heroku** - быстрый старт

---

## 🎯 Вариант 1: Развертывание на Amvera Cloud

### Шаг 1: Подготовка проекта

1. **Создайте Git репозиторий:**
```bash
cd "C:\Users\cobra\Desktop\Речевая Аналитика"
git init
git add .
git commit -m "Initial commit: Speech Analytics System"
```

2. **Загрузите на GitHub:**
```bash
# Создайте новый репозиторий на github.com
# Затем подключите его:
git remote add origin https://github.com/ВАШЕ_ИМЯ/speech-analytics.git
git branch -M main
git push -u origin main
```

### Шаг 2: Создание проекта на Amvera

1. Перейдите на https://cloud.amvera.ru/
2. Зарегистрируйтесь или войдите в аккаунт
3. Нажмите **"Создать проект"**
4. Выберите **"Из Git репозитория"**
5. Подключите ваш GitHub аккаунт
6. Выберите репозиторий `speech-analytics`

### Шаг 3: Настройка проекта

1. **Основные настройки:**
   - Название: `speech-analytics`
   - Ветка: `main`
   - Директория: оставьте пустой

2. **Переменные окружения:**
   Добавьте следующие переменные:
   ```
   FLASK_ENV=production
   SECRET_KEY=your-super-secret-key-123
   OPENAI_API_KEY=sk-ваш-ключ-openai
   MISTRAL_API_KEY=ваш-ключ-mistral
   PYTHONPATH=/app
   ```

3. **Команды сборки (если нужно):**
   ```bash
   pip install -r requirements.txt
   ```

### Шаг 4: Деплой

1. Нажмите **"Развернуть"**
2. Дождитесь завершения сборки (5-10 минут)
3. Проверьте логи на наличие ошибок
4. Получите URL вашего приложения

### Шаг 5: Тестирование

```bash
# Проверьте здоровье приложения
curl https://ваш-домен.amvera.ru/health

# Ожидаемый ответ:
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00",
  "microphone_available": false
}
```

---

## 🖥️ Вариант 2: Развертывание на VPS/выделенном сервере

### Шаг 1: Подготовка сервера

1. **Требования к серверу:**
   - OS: Ubuntu 20.04+ / CentOS 8+
   - RAM: минимум 2GB, рекомендуется 4GB
   - CPU: 2+ ядра
   - Диск: 20GB+ свободного места
   - Интернет: стабильное соединение

2. **Подключение к серверу:**
```bash
ssh root@ваш-ip-адрес
# или
ssh пользователь@ваш-ip-адрес
```

### Шаг 2: Установка зависимостей

1. **Обновление системы:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

2. **Установка Python 3.9+:**
```bash
# Ubuntu/Debian
sudo apt install python3.9 python3.9-pip python3.9-venv -y

# CentOS/RHEL
sudo yum install python39 python39-pip -y
```

3. **Установка системных зависимостей:**
```bash
# Ubuntu/Debian
sudo apt install -y \
    ffmpeg \
    portaudio19-dev \
    python3-pyaudio \
    git \
    nginx \
    supervisor

# CentOS/RHEL
sudo yum install -y \
    ffmpeg \
    portaudio-devel \
    git \
    nginx \
    supervisor
```

### Шаг 3: Настройка приложения

1. **Создание пользователя:**
```bash
sudo useradd -m -s /bin/bash speechanalytics
sudo su - speechanalytics
```

2. **Клонирование репозитория:**
```bash
git clone https://github.com/ВАШЕ_ИМЯ/speech-analytics.git
cd speech-analytics
```

3. **Создание виртуального окружения:**
```bash
python3.9 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

4. **Настройка переменных окружения:**
```bash
cp .env.example .env
nano .env

# Отредактируйте:
FLASK_ENV=production
SECRET_KEY=ваш-секретный-ключ
OPENAI_API_KEY=sk-ваш-ключ
MISTRAL_API_KEY=ваш-ключ
```

### Шаг 4: Настройка Gunicorn

1. **Создание конфигурации:**
```bash
nano gunicorn.conf.py
```

Содержимое:
```python
bind = "127.0.0.1:5000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 300
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
user = "speechanalytics"
group = "speechanalytics"
```

2. **Тестовый запуск:**
```bash
source venv/bin/activate
gunicorn -c gunicorn.conf.py speech_analytics_server:app
```

### Шаг 5: Настройка Supervisor

1. **Создание конфигурации:**
```bash
sudo nano /etc/supervisor/conf.d/speechanalytics.conf
```

Содержимое:
```ini
[program:speechanalytics]
command=/home/speechanalytics/speech-analytics/venv/bin/gunicorn -c gunicorn.conf.py speech_analytics_server:app
directory=/home/speechanalytics/speech-analytics
user=speechanalytics
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/speechanalytics.log
environment=PATH="/home/speechanalytics/speech-analytics/venv/bin"
```

2. **Запуск сервиса:**
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start speechanalytics
sudo supervisorctl status
```

### Шаг 6: Настройка Nginx

1. **Создание конфигурации:**
```bash
sudo nano /etc/nginx/sites-available/speechanalytics
```

Содержимое:
```nginx
server {
    listen 80;
    server_name ваш-домен.com;  # замените на ваш домен
    
    client_max_body_size 100M;
    client_body_timeout 300s;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Увеличиваем таймауты для обработки больших файлов
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    location /static {
        alias /home/speechanalytics/speech-analytics/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Логи
    access_log /var/log/nginx/speechanalytics_access.log;
    error_log /var/log/nginx/speechanalytics_error.log;
}
```

2. **Активация сайта:**
```bash
sudo ln -s /etc/nginx/sites-available/speechanalytics /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Шаг 7: Настройка SSL (Let's Encrypt)

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx -y

# Получение сертификата
sudo certbot --nginx -d ваш-домен.com

# Автообновление
sudo crontab -e
# Добавьте строку:
0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 🐳 Вариант 3: Развертывание с Docker

### Шаг 1: Создание Dockerfile

```dockerfile
FROM python:3.9-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    portaudio19-dev \
    python3-pyaudio \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Создание директорий
RUN mkdir -p logs uploads

EXPOSE 5000

# Запуск
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "300", "speech_analytics_server:app"]
```

### Шаг 2: Docker Compose

```yaml
version: '3.8'

services:
  speech-analytics:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=your-secret-key
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MISTRAL_API_KEY=${MISTRAL_API_KEY}
    volumes:
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    restart: unless-stopped
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - speech-analytics
    restart: unless-stopped
```

### Шаг 3: Запуск

```bash
# Сборка и запуск
docker-compose up -d

# Проверка логов
docker-compose logs -f speech-analytics

# Остановка
docker-compose down
```

---

## 🔧 Финальная настройка и тестирование

### Шаг 1: Проверка работоспособности

1. **Тест API:**
```bash
curl https://ваш-домен.com/health
curl https://ваш-домен.com/protocols/types
```

2. **Тест загрузки:**
```bash
curl -X POST https://ваш-домен.com/analyze \
  -F "media=@test.mp4" \
  -v
```

### Шаг 2: Мониторинг

1. **Настройка логирования:**
```bash
# Просмотр логов
sudo tail -f /var/log/speechanalytics.log
sudo tail -f /var/log/nginx/speechanalytics_error.log
```

2. **Мониторинг ресурсов:**
```bash
# Использование CPU и памяти
htop

# Дисковое пространство
df -h

# Сетевые соединения
netstat -tulpn | grep :5000
```

### Шаг 3: Резервное копирование

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/speechanalytics"
APP_DIR="/home/speechanalytics/speech-analytics"

mkdir -p $BACKUP_DIR

# Архивирование приложения
tar -czf $BACKUP_DIR/app_$DATE.tar.gz -C $APP_DIR .

# Архивирование загруженных файлов
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz -C $APP_DIR uploads/

# Очистка старых бэкапов (старше 7 дней)
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

### Шаг 4: Автоматические обновления

```bash
#!/bin/bash
# update.sh

cd /home/speechanalytics/speech-analytics

# Остановка сервиса
sudo supervisorctl stop speechanalytics

# Обновление кода
git pull origin main

# Установка зависимостей
source venv/bin/activate
pip install -r requirements.txt

# Запуск сервиса
sudo supervisorctl start speechanalytics

echo "Update completed"
```

---

## 🎯 Чек-лист развертывания

### Перед деплоем:
- [ ] Получены API ключи OpenAI/Mistral
- [ ] Код загружен в Git репозиторий
- [ ] Настроены переменные окружения
- [ ] Проверен requirements.txt

### После деплоя:
- [ ] Приложение отвечает на /health
- [ ] Работает загрузка файлов
- [ ] Создаются протоколы с ИИ
- [ ] Настроен SSL сертификат
- [ ] Работает мониторинг логов
- [ ] Настроено резервное копирование

### Безопасность:
- [ ] Изменены все пароли по умолчанию
- [ ] Настроен firewall
- [ ] Ограничен доступ SSH
- [ ] Настроены регулярные обновления
- [ ] API ключи в переменных окружения

---

## 📞 Поддержка

При возникновении проблем:

1. **Проверьте логи:**
   - Приложения: `/var/log/speechanalytics.log`
   - Nginx: `/var/log/nginx/speechanalytics_error.log`
   - Система: `journalctl -u nginx` или `journalctl -u supervisor`

2. **Частые проблемы:**
   - FFmpeg не установлен → установите пакет `ffmpeg`
   - Нет API ключей → проверьте переменные окружения
   - Превышен размер файла → увеличьте `client_max_body_size`
   - Таймауты → увеличьте настройки таймаутов в Nginx/Gunicorn

3. **Полезные команды:**
```bash
# Перезапуск сервисов
sudo supervisorctl restart speechanalytics
sudo systemctl reload nginx

# Проверка портов
sudo netstat -tulpn | grep :5000
sudo netstat -tulpn | grep :80

# Проверка процессов
ps aux | grep gunicorn
ps aux | grep nginx
```

Удачного развертывания! 🚀