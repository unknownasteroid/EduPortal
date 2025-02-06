// ====================
// Конфигурация
// ====================
const API_BASE_URL = '/forum';
const NAVBAR_COLOR = 'linear-gradient(135deg, #2980b9, #2c3e50)';

// ====================
// Инициализация
// ====================
document.addEventListener('DOMContentLoaded', () => {
    initNavbarStyles();
    initMessageHandlers();
});

// ====================
// Обработка сообщений
// ====================
const initMessageHandlers = () => {
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', handleDelete);
    });
    console.log('Обработчики инициализированы');
};



// ====================
// Проверка прав
// ====================


const canDeleteMessage = (messageElement) => {
    if (!messageElement) return false;

    const isAdmin = messageElement.dataset.isAdmin === 'True';
    const isOwner = messageElement.dataset.userId === CURRENT_USER_ID;

    return isAdmin || isOwner;
};


const handleDelete = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    try {
        const btn = event.currentTarget;
        const messageId = btn.dataset.id;
        const messageElement = btn.closest('[data-message-id]');
        console.log(messageElement.dataset.isAdmin);
        console.log('Начало удаления сообщения:', messageId);

        // Проверка прав
        if (!canDeleteMessage(messageElement)) {
            alert('Нет прав на удаление');
            return;
        }

        // Подтверждение удаления
        if (!confirm('Вы точно хотите удалить это сообщение?')) {
            return;
        }

        // Отправка запроса
        const response = await fetch(`/forum/delete/${messageId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': CSRF_TOKEN
            }
        });
        console.log(CSRF_TOKEN);
        console.log('Ответ сервера:', response);

        if (!response.ok) {
            throw new Error('Ошибка сервера');
        }

        const result = await response.json();
        console.log('Результат удаления:', result);

        if (result.success) {
            messageElement.remove();
            console.log('Сообщение удалено');
        } else {
            throw new Error(result.error || 'Ошибка при удалении');
        }

    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка при удалении: ' + error.message);
    }
};



// ====================
// Инициализация навбара
// ====================
const initNavbarStyles = () => {
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        navbar.style.background = NAVBAR_COLOR;
        navbar.style.color = 'white';
    }
};


// Инициализация
document.querySelectorAll('.like-btn').forEach(btn => {
    btn.addEventListener('click', () => handleReaction('like', btn));
});

document.querySelectorAll('.dislike-btn').forEach(btn => {
    btn.addEventListener('click', () => handleReaction('dislike', btn));
});


const updateButtons = (btn, reaction) => {
    const likeBtn = btn.closest('.card').querySelector('.like-btn');
    const dislikeBtn = btn.closest('.card').querySelector('.dislike-btn');

    // Сбрасываем все стили
    likeBtn.classList.remove('active');
    dislikeBtn.classList.remove('active');

    // Применяем стиль к активной кнопке
    if (reaction === 'like') {
        likeBtn.classList.add('active');
    } else if (reaction === 'dislike') {
        dislikeBtn.classList.add('active');
    }
};

const updateReactionStyles = (messageId, reaction) => {
    const card = document.querySelector(`[data-message-id="${messageId}"]`);
    if (!card) return;

    const likeBtn = card.querySelector('.like-btn');
    const dislikeBtn = card.querySelector('.dislike-btn');

    likeBtn?.classList.remove('liked');
    dislikeBtn?.classList.remove('disliked');

    if (reaction === 'like') {
        likeBtn?.classList.add('liked');
    } else if (reaction === 'dislike') {
        dislikeBtn?.classList.add('disliked');
    }
};

const handleReaction = async (type, btn) => {
    const messageId = btn.dataset.id;

    try {
        const response = await fetch(`/forum/${type}/${messageId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': CSRF_TOKEN
            }
        });

        const result = await response.json();

        if (result.success) {
            // Обновляем счетчики
            btn.closest('.card').querySelector('.like-btn .count').textContent = result.likes;
            btn.closest('.card').querySelector('.dislike-btn .count').textContent = result.dislikes;

            // Обновляем стили
            updateReactionStyles(messageId, result.user_reaction);
        }
    } catch (error) {
        alert(`Ошибка: ${error.message}`);
    }
};


// forum.js (дополнение)
const initReactions = async () => {
    document.querySelectorAll('.card[data-message-id]').forEach(async card => {
        const messageId = card.dataset.messageId;
        try {
            const response = await fetch(`/forum/reaction/${messageId}`);
            const data = await response.json();
            updateReactionStyles(messageId, data.reaction);
        } catch (error) {
            console.error('Ошибка получения реакции:', error);
        }
    });
};

document.addEventListener('DOMContentLoaded', () => {
    initNavbarStyles();
    initMessageHandlers();
    initReactions(); // Добавляем инициализацию реакций
});
