GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Gamma Messenger для Linux      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo

echo "Python3 найден: $(python3 --version)"

sudo apt install python3-venv -y

echo "Скачивание репозитория"
git clone https://github.com/Iaroslav-Palekhov/proton-messenger.git
echo "Скачано. Переходим в gamma-messenger/"

cd proton-messenger/

if [ ! -d "venv" ]; then
    echo "Создание виртуального окружения..."
    python3 -m venv venv
fi

echo "Активация виртуального окружения..."
source venv/bin/activate

echo "Установка зависимостей..."
pip install -r requirements.txt


echo -e "${GREEN}Готово!${NC}"
echo
echo -e "${GREEN}Запуск Gamma Messenger...${NC}"
echo "Сервер запущен на: http://localhost:2200"
echo "Для остановки нажмите Ctrl+C"
echo

# Запуск приложения
python3 app.py
