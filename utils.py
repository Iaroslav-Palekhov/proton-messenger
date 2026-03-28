import os
import uuid
import io
import mimetypes
from PIL import Image
from werkzeug.utils import secure_filename

def create_upload_folders(app):
    """Создает все необходимые папки для загрузок"""
    folders = [
        'avatars',
        'group_icons',
        'images',
        'videos',
        'audio',
        'documents',
        'archives',
        'executables',
        'other'
    ]
    
    for folder in folders:
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], folder), exist_ok=True)

def create_default_avatars(app):
    """Создает дефолтные аватарки и иконки групп"""
    # Дефолтная аватарка
    default_avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', 'default.png')
    if not os.path.exists(default_avatar_path):
        os.makedirs(os.path.dirname(default_avatar_path), exist_ok=True)
        img = Image.new('RGB', (200, 200), color='#00a884')
        img.save(default_avatar_path)
    
    # Дефолтная иконка группы
    default_group_icon_path = os.path.join(app.config['UPLOAD_FOLDER'], 'group_icons', 'default.png')
    if not os.path.exists(default_group_icon_path):
        os.makedirs(os.path.dirname(default_group_icon_path), exist_ok=True)
        img = Image.new('RGB', (200, 200), color='#3b4a54')
        img.save(default_group_icon_path)

def compress_image(image_data, max_size=(800, 800), quality=85):
    try:
        img = Image.open(io.BytesIO(image_data))
        original_format = img.format

        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')

        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        if original_format == 'WEBP':
            img.save(buffer, format='WEBP', quality=quality)
        else:
            img.save(buffer, format='JPEG', quality=quality, optimize=True)

        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        print(f"Ошибка при сжатии изображения: {e}")
        return image_data

def allowed_file(filename):
    return True

def get_file_category(filename):
    """Определяет категорию файла по расширению"""
    # Получаем расширение файла
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
    else:
        ext = ''

    # Проверяем на специальные случаи
    # .docx, .xlsx, .pptx и другие офисные форматы
    if ext in ['docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 'odt', 'ods', 'odp', 'rtf', 'pdf']:
        return 'document'
    
    # Другие расширения
    image_ext = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'heic', 'raw'}
    video_ext = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm', 'm4v', '3gp', 'mpg', 'mpeg'}
    audio_ext = {'mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma', 'opus'}
    document_ext = {'pdf', 'doc', 'docx', 'odt', 'rtf', 'txt', 'xls', 'xlsx', 'ods', 'csv', 'ppt', 'pptx', 'odp', 'md'}
    archive_ext = {'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'iso', 'dmg'}
    executable_ext = {'exe', 'msi', 'sh', 'bat', 'cmd', 'appimage', 'deb', 'rpm', 'apk', 'ipa'}

    if ext in image_ext:
        return 'image'
    elif ext in video_ext:
        return 'video'
    elif ext in audio_ext:
        return 'audio'
    elif ext in document_ext:
        return 'document'
    elif ext in archive_ext:
        return 'archive'
    elif ext in executable_ext:
        return 'executable'
    else:
        return 'other'

def get_file_icon(filename):
    """Возвращает иконку для файла по расширению"""
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
    else:
        ext = ''

    icons = {
        # Изображения
        'jpg': '[img]', 'jpeg': '[img]', 'png': '[img]', 'gif': '[img]', 'webp': '[img]', 'svg': '[img]', 'bmp': '[img]',
        # Видео
        'mp4': '[video]', 'avi': '[video]', 'mov': '[video]', 'mkv': '[video]', 'webm': '[video]',
        # Аудио
        'mp3': '[audio]', 'wav': '[audio]', 'ogg': '[audio]', 'flac': '[audio]', 'm4a': '[audio]',
        # Документы
        'pdf': '[pdf]', 'doc': '[doc]', 'docx': '[doc]', 'txt': '[txt]', 'rtf': '[txt]',
        'xls': '[xls]', 'xlsx': '[xls]', 'csv': '[csv]', 'ppt': '[ppt]', 'pptx': '[ppt]',
        # Архивы
        'zip': '[zip]', 'rar': '[zip]', '7z': '[zip]', 'tar': '[zip]', 'gz': '[zip]',
        # Исполняемые
        'exe': '[exe]', 'msi': '[exe]', 'sh': '[sh]', 'bat': '[bat]', 'apk': '[apk]',
    }
    #return icons.get(ext, '[file]')
    return icons.get(ext, icons['default'])

def format_file_size(size_bytes):
    if size_bytes is None:
        return '0 B'
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def is_file_too_large(file_size, app):
    max_size = app.config.get('MAX_CONTENT_LENGTH', 500 * 1024 * 1024)
    return file_size > max_size

def save_file(file, category, app):
    """Универсальная функция сохранения файлов"""
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{filename}"
    
    category_folders = {
        'image': 'images',
        'video': 'videos',
        'audio': 'audio',
        'document': 'documents',
        'archive': 'archives',
        'executable': 'executables',
        'avatar': 'avatars',
        'group_icon': 'group_icons',
        'other': 'other'
    }
    
    folder = category_folders.get(category, 'other')
    
    if category == 'image' or category == 'avatar' or category == 'group_icon':
        image_data = file.read()
        compressed_data = compress_image(image_data)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], folder, unique_filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(compressed_data)
        return f'{folder}/{unique_filename}', len(compressed_data)
    else:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], folder, unique_filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        return f'{folder}/{unique_filename}', os.path.getsize(file_path)


import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

def extract_link_preview(url):
    """Извлекает метаданные со страницы (title, description, image)"""
    try:
        # Проверяем, что URL валидный
        parsed = urlparse(url)
        if not parsed.scheme:
            url = 'https://' + url
            parsed = urlparse(url)
        
        # Заголовки для имитации браузера
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Делаем запрос с таймаутом
        response = requests.get(url, headers=headers, timeout=5, verify=False)
        response.raise_for_status()
        
        # Парсим HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Извлекаем title
        title = None
        if soup.find('meta', property='og:title'):
            title = soup.find('meta', property='og:title')['content']
        elif soup.find('meta', attrs={'name': 'title'}):
            title = soup.find('meta', attrs={'name': 'title'})['content']
        elif soup.title:
            title = soup.title.string
        
        # Извлекаем description
        description = None
        if soup.find('meta', property='og:description'):
            description = soup.find('meta', property='og:description')['content']
        elif soup.find('meta', attrs={'name': 'description'}):
            description = soup.find('meta', attrs={'name': 'description'})['content']
        
        # Извлекаем image
        image = None
        if soup.find('meta', property='og:image'):
            image = soup.find('meta', property='og:image')['content']
            image = urljoin(url, image)
        elif soup.find('meta', attrs={'name': 'twitter:image'}):
            image = soup.find('meta', attrs={'name': 'twitter:image'})['content']
            image = urljoin(url, image)
        else:
            # Пробуем найти первую картинку на странице
            img_tag = soup.find('img', src=True)
            if img_tag:
                image = urljoin(url, img_tag['src'])
        
        # Очищаем и ограничиваем данные
        if title:
            title = title.strip()[:200]
        if description:
            description = description.strip()[:500]
        
        return {
            'url': url,
            'title': title,
            'description': description,
            'image': image
        }
        
    except Exception as e:
        print(f"Ошибка при извлечении превью ссылки: {e}")
        return None

def contains_url(text):
    """Проверяет, содержит ли текст URL"""
    if not text:
        return False
    
    url_pattern = re.compile(
        r'(https?://)?'
        r'(www\.)?'
        r'[-a-zA-Z0-9@:%._\+~#=]{1,256}'
        r'\.[a-zA-Z0-9()]{1,6}'
        r'\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)',
        re.IGNORECASE
    )
    
    return bool(url_pattern.search(text))

def extract_urls_from_text(text):
    """Извлекает все URL из текста"""
    if not text:
        return []
    
    url_pattern = re.compile(
        r'(https?://[^\s<>"{}|\\^`\[\]]+|'
        r'www\.[^\s<>"{}|\\^`\[\]]+)',
        re.IGNORECASE
    )
    
    return url_pattern.findall(text)