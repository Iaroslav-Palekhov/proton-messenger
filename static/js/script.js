// ============================================================
// ТЕМА: глобальное управление темой и акцентом
// ============================================================
(function () {
    var ACCENT_PALETTES = {
        green:  { light: { accent: '#25a87e', hover: '#1e9370', sent: '#d9fdd3', sentDark: '#005c4b' }, dark: { accent: '#00a884', hover: '#039b7b', sent: '#005c4b', sentDark: '#005c4b' } },
        olive:  { light: { accent: '#6b8e23', hover: '#5a7a1a', sent: '#e5edcc', sentDark: '#3a4e10' }, dark: { accent: '#8fb33a', hover: '#7a9c2e', sent: '#3a4e10', sentDark: '#3a4e10' } },
        blue:   { light: { accent: '#1d72b8', hover: '#155d9e', sent: '#cce4f7', sentDark: '#0a3d6b' }, dark: { accent: '#3b9edd', hover: '#2e8ac6', sent: '#0a3d6b', sentDark: '#0a3d6b' } },
        red:    { light: { accent: '#c0392b', hover: '#a93226', sent: '#fad7d3', sentDark: '#6b1510' }, dark: { accent: '#e05c4f', hover: '#cc4a3d', sent: '#6b1510', sentDark: '#6b1510' } },
        purple: { light: { accent: '#7c3aed', hover: '#6d28d9', sent: '#ede0fc', sentDark: '#3b1a7a' }, dark: { accent: '#9f60f5', hover: '#8b4de0', sent: '#3b1a7a', sentDark: '#3b1a7a' } }
    };

    function getCookie(n) {
        var m = document.cookie.match('(?:^|; )' + n + '=([^;]*)');
        return m ? decodeURIComponent(m[1]) : null;
    }

    function setCookie(n, v) {
        var d = new Date();
        d.setFullYear(d.getFullYear() + 1);
        document.cookie = n + '=' + encodeURIComponent(v) + ';expires=' + d.toUTCString() + ';path=/;SameSite=Lax';
    }

    function resolveTheme(pref) {
        if (pref === 'dark') return 'dark';
        if (pref === 'light') return 'light';
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function applyAccent(accentKey, resolvedTheme) {
        var palette = ACCENT_PALETTES[accentKey] || ACCENT_PALETTES['green'];
        var colors = palette[resolvedTheme] || palette['dark'];
        var root = document.documentElement;
        root.style.setProperty('--accent', colors.accent);
        root.style.setProperty('--accent-hover', colors.hover);
        root.style.setProperty('--success', colors.accent);
        root.style.setProperty('--sent-message', colors.sent);
        root.style.setProperty('--sent-message-text', resolvedTheme === 'light' ? '#111b21' : '#ffffff');
        root.style.setProperty('--messages-bg', resolvedTheme === 'light' ? '#efeae2' : '#0e1c26');
        root.style.setProperty('--messages-bg-pattern', resolvedTheme === 'light' ? 'none' : 'radial-gradient(circle at 10% 20%, rgba(0, 168, 132, 0.03) 0%, transparent 20%)');
    }

    function applyAll(themePref, accentKey) {
        var resolved = resolveTheme(themePref);
        document.documentElement.setAttribute('data-theme', resolved);
        applyAccent(accentKey || 'purple', resolved);
    }

    window.ThemeManager = {
        get: function () {
            return { theme: getCookie('theme') || 'system', accent: getCookie('accent') || 'purple' };
        },
        setTheme: function (pref) {
            setCookie('theme', pref);
            applyAll(pref, getCookie('accent') || 'purple');
            document.querySelectorAll('[data-theme-btn]').forEach(function (btn) {
                btn.classList.toggle('active', btn.getAttribute('data-theme-btn') === pref);
            });
        },
        setAccent: function (key) {
            setCookie('accent', key);
            applyAll(getCookie('theme') || 'system', key);
            document.querySelectorAll('[data-accent-btn]').forEach(function (btn) {
                btn.classList.toggle('active', btn.getAttribute('data-accent-btn') === key);
            });
        },
        palettes: ACCENT_PALETTES
    };

    applyAll(getCookie('theme') || 'system', getCookie('accent') || 'purple');

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
        if ((getCookie('theme') || 'system') === 'system') {
            applyAll('system', getCookie('accent') || 'purple');
        }
    });

    // ============================================================
    // ПКМ: глобальный перехват — браузерное меню только там где нужно
    // ============================================================
    document.addEventListener('contextmenu', function (e) {
        var t = e.target;
        // Разрешаем стандартное меню только для полей ввода и выделяемого текста
        var isInput = t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable;
        // Если есть выделенный текст — тоже разрешаем (чтобы можно было скопировать)
        var hasSelection = window.getSelection && window.getSelection().toString().length > 0;
        if (isInput || hasSelection) return;
        e.preventDefault();
    }, true); // capture=true — перехватываем раньше всех остальных обработчиков
})();

// Дополнительные функции JavaScript

// Закрытие модальных окон при клике вне их
document.addEventListener('DOMContentLoaded', function() {
    // Для модального окна изображений
    const imageModal = document.getElementById('imageModal');
    if (imageModal) {
        imageModal.addEventListener('click', function(e) {
            if (e.target === this || e.target.classList.contains('close-modal')) {
                this.style.display = 'none';
            }
        });
    }
    
    // Для формы нового чата
    const newChatForm = document.querySelector('.new-chat-form');
    const overlay = document.querySelector('.overlay');
    
    if (newChatForm && overlay) {
        overlay.addEventListener('click', function() {
            newChatForm.style.display = 'none';
            this.style.display = 'none';
        });
    }
});

// Функция для плавной прокрутки
function smoothScrollToBottom(element) {
    element.scrollTo({
        top: element.scrollHeight,
        behavior: 'smooth'
    });
}

// Форматирование времени
function formatTime(date) {
    return date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Валидация email
function isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

// Уведомления
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 10px;
        color: white;
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    
    if (type === 'success') {
        notification.style.background = 'linear-gradient(135deg, #2ed573 0%, #1abc9c 100%)';
    } else if (type === 'error') {
        notification.style.background = 'linear-gradient(135deg, #ff4757 0%, #ff3838 100%)';
    } else {
        notification.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
    }
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Анимации
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
`;
document.head.appendChild(style);

// Функция для обработки ошибок загрузки изображений
function handleImageError(img) {
    img.onerror = null;
    img.src = '/static/images/default-error.png';
    img.alt = 'Не удалось загрузить изображение';
}

// Добавляем обработчики ко всем изображениям
document.addEventListener('DOMContentLoaded', function() {
    const images = document.querySelectorAll('img');
    images.forEach(img => {
        img.addEventListener('error', function() {
            handleImageError(this);
        });
    });
});
