#!/bin/bash

# 🚀 Автоматический скрипт развертывания Speech Analytics
# Использование: bash deploy.sh [опции]

set -e  # Останавливаем при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для цветного вывода
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                     Speech Analytics Deployment                      ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NC}"
}

# Переменные
PROJECT_NAME="speech-analytics"
PROJECT_DIR="/home/speechanalytics/$PROJECT_NAME"
USER="speechanalytics"
PYTHON_VERSION="3.9"

# Функция проверки системы
check_system() {
    print_info "Проверка системы..."
    
    # Проверка OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/ubuntu-release ] || [ -f /etc/debian_version ]; then
            OS="ubuntu"
        elif [ -f /etc/redhat-release ] || [ -f /etc/centos-release ]; then
            OS="centos"
        else
            print_error "Неподдерживаемая операционная система"
            exit 1
        fi
    else
        print_error "Скрипт поддерживает только Linux"
        exit 1
    fi
    
    print_success "Операционная система: $OS"
    
    # Проверка прав root
    if [[ $EUID -ne 0 ]]; then
        print_error "Запустите скрипт с правами root: sudo bash deploy.sh"
        exit 1
    fi
}

# Установка системных зависимостей
install_system_deps() {
    print_info "Установка системных зависимостей..."
    
    if [ "$OS" = "ubuntu" ]; then
        apt update
        apt install -y \
            python$PYTHON_VERSION \
            python$PYTHON_VERSION-pip \
            python$PYTHON_VERSION-venv \
            python$PYTHON_VERSION-dev \
            ffmpeg \
            portaudio19-dev \
            git \
            nginx \
            supervisor \
            curl \
            htop \
            nano \
            build-essential
    elif [ "$OS" = "centos" ]; then
        yum update -y
        yum install -y \
            python39 \
            python39-pip \
            python39-devel \
            ffmpeg \
            portaudio-devel \
            git \
            nginx \
            supervisor \
            curl \
            htop \
            nano \
            gcc \
            gcc-c++
    fi
    
    print_success "Системные зависимости установлены"
}

# Создание пользователя
create_user() {
    print_info "Создание пользователя $USER..."
    
    if ! id "$USER" &>/dev/null; then
        useradd -m -s /bin/bash $USER
        print_success "Пользователь $USER создан"
    else
        print_warning "Пользователь $USER уже существует"
    fi
}

# Установка приложения
install_app() {
    print_info "Установка приложения..."
    
    # Создание директории
    mkdir -p $PROJECT_DIR
    chown $USER:$USER $PROJECT_DIR
    
    # Переключение на пользователя приложения
    sudo -u $USER bash << EOF
        cd $PROJECT_DIR
        
        # Клонирование репозитория (если еще не клонирован)
        if [ ! -d ".git" ]; then
            if [ -z "$REPO_URL" ]; then
                print_error "Установите переменную REPO_URL"
                exit 1
            fi
            git clone $REPO_URL .
        else
            git pull origin main
        fi
        
        # Создание виртуального окружения
        python$PYTHON_VERSION -m venv venv
        source venv/bin/activate
        
        # Установка зависимостей
        pip install --upgrade pip
        pip install -r requirements.txt
        
        # Создание директорий
        mkdir -p uploads logs static
        
        # Копирование конфигурации
        if [ ! -f ".env" ]; then
            cp .env.example .env || touch .env
            echo "FLASK_ENV=production" >> .env
            echo "SECRET_KEY=\$(openssl rand -hex 32)" >> .env
        fi
EOF
    
    print_success "Приложение установлено"
}

# Настройка Gunicorn
setup_gunicorn() {
    print_info "Настройка Gunicorn..."
    
    cat > $PROJECT_DIR/gunicorn.conf.py << 'EOF'
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
pid = "/var/run/gunicorn/speechanalytics.pid"
access_log = "/var/log/speechanalytics/access.log"
error_log = "/var/log/speechanalytics/error.log"
log_level = "info"
EOF
    
    # Создание директорий для логов
    mkdir -p /var/log/speechanalytics /var/run/gunicorn
    chown $USER:$USER /var/log/speechanalytics /var/run/gunicorn
    
    print_success "Gunicorn настроен"
}

# Настройка Supervisor
setup_supervisor() {
    print_info "Настройка Supervisor..."
    
    cat > /etc/supervisor/conf.d/speechanalytics.conf << EOF
[program:speechanalytics]
command=$PROJECT_DIR/venv/bin/gunicorn -c $PROJECT_DIR/gunicorn.conf.py speech_analytics_server:app
directory=$PROJECT_DIR
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/speechanalytics/supervisor.log
environment=PATH="$PROJECT_DIR/venv/bin"
EOF
    
    # Перезагрузка конфигурации Supervisor
    supervisorctl reread
    supervisorctl update
    
    print_success "Supervisor настроен"
}

# Настройка Nginx
setup_nginx() {
    print_info "Настройка Nginx..."
    
    # Получение домена от пользователя
    if [ -z "$DOMAIN" ]; then
        read -p "Введите ваш домен (например, example.com): " DOMAIN
    fi
    
    if [ -z "$DOMAIN" ]; then
        DOMAIN="localhost"
        print_warning "Использован домен по умолчанию: localhost"
    fi
    
    cat > /etc/nginx/sites-available/speechanalytics << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    
    client_max_body_size 100M;
    client_body_timeout 300s;
    client_header_timeout 300s;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
    
    location /static {
        alias $PROJECT_DIR/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    access_log /var/log/nginx/speechanalytics_access.log;
    error_log /var/log/nginx/speechanalytics_error.log;
}
EOF
    
    # Активация сайта
    ln -sf /etc/nginx/sites-available/speechanalytics /etc/nginx/sites-enabled/
    
    # Удаление дефолтного сайта
    rm -f /etc/nginx/sites-enabled/default
    
    # Проверка конфигурации
    nginx -t
    
    # Перезагрузка Nginx
    systemctl reload nginx
    
    print_success "Nginx настроен для домена: $DOMAIN"
}

# Настройка SSL
setup_ssl() {
    print_info "Настройка SSL сертификата..."
    
    if [ "$DOMAIN" != "localhost" ]; then
        # Установка Certbot
        if [ "$OS" = "ubuntu" ]; then
            apt install -y certbot python3-certbot-nginx
        elif [ "$OS" = "centos" ]; then
            yum install -y certbot python3-certbot-nginx
        fi
        
        # Получение сертификата
        certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
            print_warning "Не удалось получить SSL сертификат. Проверьте DNS настройки."
        }
        
        # Настройка автообновления
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
        
        print_success "SSL настроен"
    else
        print_warning "SSL пропущен для localhost"
    fi
}

# Запуск сервисов
start_services() {
    print_info "Запуск сервисов..."
    
    # Запуск приложения
    supervisorctl start speechanalytics
    
    # Включение автозапуска
    systemctl enable nginx
    systemctl enable supervisor
    
    # Проверка статуса
    sleep 5
    
    if supervisorctl status speechanalytics | grep -q RUNNING; then
        print_success "Приложение запущено"
    else
        print_error "Ошибка запуска приложения"
        supervisorctl status speechanalytics
        exit 1
    fi
    
    if systemctl is-active --quiet nginx; then
        print_success "Nginx запущен"
    else
        print_error "Ошибка запуска Nginx"
        systemctl status nginx
        exit 1
    fi
}

# Тестирование развертывания
test_deployment() {
    print_info "Тестирование развертывания..."
    
    # Тест локального подключения
    if curl -s http://127.0.0.1:5000/health > /dev/null; then
        print_success "Приложение отвечает локально"
    else
        print_error "Приложение не отвечает локально"
        return 1
    fi
    
    # Тест через Nginx
    if curl -s http://$DOMAIN/health > /dev/null; then
        print_success "Приложение доступно через Nginx"
    else
        print_warning "Приложение может быть недоступно извне"
    fi
    
    # Проверка API endpoints
    local endpoints=("/health" "/protocols/types")
    for endpoint in "${endpoints[@]}"; do
        if curl -s http://127.0.0.1:5000$endpoint > /dev/null; then
            print_success "Endpoint $endpoint работает"
        else
            print_warning "Endpoint $endpoint недоступен"
        fi
    done
}

# Показ финальной информации
show_final_info() {
    print_header
    print_success "🎉 Развертывание завершено!"
    echo
    print_info "📋 Информация о развертывании:"
    echo "   🌐 URL: http://$DOMAIN"
    echo "   📁 Директория: $PROJECT_DIR"
    echo "   👤 Пользователь: $USER"
    echo "   📊 Логи приложения: /var/log/speechanalytics/"
    echo "   📊 Логи Nginx: /var/log/nginx/speechanalytics_*.log"
    echo
    print_info "🔧 Полезные команды:"
    echo "   Перезапуск приложения: sudo supervisorctl restart speechanalytics"
    echo "   Просмотр логов: sudo tail -f /var/log/speechanalytics/supervisor.log"
    echo "   Статус сервисов: sudo supervisorctl status"
    echo "   Обновление кода: cd $PROJECT_DIR && git pull && sudo supervisorctl restart speechanalytics"
    echo
    print_warning "⚠️  Не забудьте:"
    echo "   1. Настроить переменные окружения в $PROJECT_DIR/.env"
    echo "   2. Добавить API ключи OpenAI/Mistral"
    echo "   3. Настроить DNS для домена $DOMAIN"
    echo "   4. Настроить firewall (порты 80, 443)"
    echo
    print_info "🧪 Тестирование:"
    echo "   curl http://$DOMAIN/health"
    echo
}

# Основная функция
main() {
    print_header
    
    # Проверка аргументов
    while [[ $# -gt 0 ]]; do
        case $1 in
            --repo)
                REPO_URL="$2"
                shift 2
                ;;
            --domain)
                DOMAIN="$2"
                shift 2
                ;;
            --no-ssl)
                NO_SSL=true
                shift
                ;;
            -h|--help)
                echo "Использование: $0 [опции]"
                echo "Опции:"
                echo "  --repo URL     URL Git репозитория"
                echo "  --domain NAME  Доменное имя"
                echo "  --no-ssl       Пропустить настройку SSL"
                echo "  -h, --help     Показать эту справку"
                exit 0
                ;;
            *)
                print_error "Неизвестная опция: $1"
                exit 1
                ;;
        esac
    done
    
    # Выполнение этапов развертывания
    check_system
    install_system_deps
    create_user
    install_app
    setup_gunicorn
    setup_supervisor
    setup_nginx
    
    if [ "$NO_SSL" != true ]; then
        setup_ssl
    fi
    
    start_services
    test_deployment
    show_final_info
}

# Обработка сигналов
trap 'print_error "Развертывание прервано"; exit 1' INT TERM

# Запуск
main "$@"