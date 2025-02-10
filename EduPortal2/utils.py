import json
import os
import time
import random
import string
from datetime import datetime

from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash


def get_users():
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'users.json')
    try:
        with open(data_path, 'r') as f:
            return json.load(f)['users']
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_users(users):
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'users.json')
    with open(data_path, 'w') as f:
        json.dump({'users': users}, f, indent=2)


def create_user(login, email, password, full_name, birth_date, account_type, school=None):
    users = get_users()

    # Проверка уникальности логина и email
    if any(u['login'] == login for u in users):
        return None, 'Логин уже занят'
    if any(u['email'] == email for u in users):
        return None, 'Email уже зарегистрирован'

    new_user = {
        'id': max([u['id'] for u in users], default=0) + 1,
        'login': login,
        'email': email,
        'password_hash': generate_password_hash(password),
        'full_name': full_name,
        'school': school,
        'birth_date': birth_date,
        'account_type': account_type,
        'created_at': datetime.now().isoformat()
    }

    users.append(new_user)
    save_users(users)
    return new_user, None

def load_messages():
    """Загрузка сообщений из файла"""
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'forum.json')
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('messages', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_to_file(filename, data):
    data_path = os.path.join(current_app.config['DATA_FOLDER'], filename)
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_id():
    timestamp = str(int(time.time()))[-6:]
    random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{timestamp}_{random_part}"

def get_message_by_id(message_id):
    messages = load_forum_data().get('messages', [])
    print(f"Поиск сообщения {message_id} среди {len(messages)} сообщений")
    return next((msg for msg in messages if str(msg['id']) == str(message_id)), None)

def get_user_by_login(login):
    users = get_users()
    return next((u for u in users if u['login'] == login), None)

def get_user_by_email(email):
    users = get_users()
    return next((u for u in users if u['email'] == email), None)


def get_messages(sort_by='recent'):
    try:
        data = load_forum_data()
        messages = data.get('messages', [])

        if sort_by == 'recent':
            # Сортировка по дате (новые сверху)
            return sorted(messages, key=lambda x: x['timestamp'], reverse=True)

        elif sort_by == 'popular':
            # Сортировка по популярности (лайки минус дизлайки)
            return sorted(messages, key=lambda x: (x['likes'] - x['dislikes']), reverse=True)

        # По умолчанию возвращаем без сортировки
        return messages

    except Exception as e:
        print(f"Ошибка при получении сообщений: {str(e)}")
        return []


def save_message(message):
    """
    Сохраняет или обновляет сообщение в базе данных форума.
    - Если сообщение с таким ID уже существует, оно обновляется
    - Если сообщение новое - добавляется в список
    - Автоматически инициализирует списки реакций при необходимости
    - Возвращает True при успешном сохранении, False при ошибке
    """
    try:
        # Загрузка текущих данных
        data = load_forum_data()
        messages = data.get('messages', [])

        # Проверка и инициализация обязательных полей
        message.setdefault('liked_by', [])
        message.setdefault('disliked_by', [])

        # Поиск существующего сообщения
        found = False
        for i, msg in enumerate(messages):
            if msg['id'] == message['id']:
                # Сохраняем историю реакций при обновлении
                message['liked_by'] = msg.get('liked_by', [])
                message['disliked_by'] = msg.get('disliked_by', [])

                # Обновляем сообщение
                messages[i] = message
                found = True
                break

        # Добавление нового сообщения
        if not found:
            messages.append(message)

        # Сохранение обновленных данных
        save_forum_data({'messages': messages})
        return True

    except Exception as e:
        print(f"[!] Ошибка сохранения сообщения {message.get('id', 'unknown')}: {str(e)}")
        return False


def load_forum_data():
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'forum.json')
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'messages': []}


def save_forum_data(data):
    try:
        data_path = os.path.join(current_app.config['DATA_FOLDER'], 'forum.json')
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ошибка сохранения форума: {str(e)}")
        return False

def delete_message_from_db(message_id):
    try:
        print(f"\nAttempting to delete message {message_id}")
        data = load_forum_data()
        initial_count = len(data['messages'])
        print(f"Initial messages count: {initial_count}")

        # Фильтрация сообщений
        data['messages'] = [msg for msg in data['messages'] if str(msg['id']) != str(message_id)]
        new_count = len(data['messages'])
        print(f"New messages count: {new_count}")

        if new_count == initial_count:
            print("Message not found in database")
            return False

        # Сохранение
        save_forum_data(data)
        print("Message successfully deleted")
        return True

    except Exception as e:
        print(f"Deletion error: {str(e)}")
        return False


def load_materials():
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'materials.json')
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('materials', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_materials(materials):
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'materials.json')
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump({'materials': materials}, f, indent=2, ensure_ascii=False)


def load_tasks():
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'tasks.json')
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('tasks', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_tasks(tasks):
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'tasks.json')
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump({'tasks': tasks}, f, indent=2, ensure_ascii=False)


# В функции create_task добавить поле approved
def create_task(task_data):
    tasks = load_tasks()
    new_task = {
        'id': generate_id(),
        'approved': False,
        **task_data
    }
    tasks.append(new_task)
    save_tasks(tasks)
    return new_task


def get_solved_tasks(user_id):
    """Возвращает словарь {task_id: is_correct} для конкретного пользователя."""
    tasks = load_tasks()
    solved_tasks = {}
    for task in tasks:
        if 'solved_by' in task:
            for solver in task['solved_by']:
                if solver['user_id'] == user_id:
                    solved_tasks[task['id']] = solver['is_correct']
    return solved_tasks


def save_solved_task(user_id, task_id, is_correct):
    """Сохраняет результат решения задачи."""
    tasks = load_tasks()
    for task in tasks:
        if task['id'] == task_id:
            if 'solved_by' not in task:
                task['solved_by'] = []

            # Удаляем старый результат, если он есть
            task['solved_by'] = [s for s in task['solved_by'] if s['user_id'] != user_id]

            # Добавляем новый результат
            task['solved_by'].append({
                'user_id': user_id,
                'is_correct': is_correct,
                'timestamp': datetime.now().isoformat()
            })
            break

    save_tasks(tasks)


def load_groups():
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'groups.json')
    try:
        if not os.path.exists(data_path):
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump({'groups': []}, f)

        with open(data_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'groups' not in data:
                data['groups'] = []
            # Инициализируем поле materials, если его нет
            for group in data['groups']:
                if 'materials' not in group:
                    group['materials'] = []
            return data['groups']
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Ошибка загрузки групп: {str(e)}")
        return []

def save_groups(groups):
    data_path = os.path.join(current_app.config['DATA_FOLDER'], 'groups.json')
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump({'groups': groups}, f, indent=2, ensure_ascii=False)

def get_user_by_id(user_id):
    users = get_users()
    return next((u for u in users if u['id'] == user_id), None)


def get_task_stats_by_number(user_id):
    """Возвращает статистику по номерам заданий в процентах"""
    tasks = load_tasks()
    stats = {
        'total': [0] * 27,  # Общее количество попыток
        'correct': [0] * 27  # Количество правильных решений
    }

    for task in tasks:
        if 'solved_by' in task:
            for solver in task['solved_by']:
                if solver['user_id'] == user_id:
                    idx = task['task_number'] - 1
                    if 0 <= idx < 27:
                        stats['total'][idx] += 1
                        if solver['is_correct']:
                            stats['correct'][idx] += 1

    # Рассчитываем проценты
    percentages = []
    for i in range(27):
        total = stats['total'][i]
        correct = stats['correct'][i]
        if total > 0:
            percentages.append(round((correct / total) * 100))
        else:
            percentages.append(0)

    return percentages


def get_task_by_id(id):
    tasks = load_tasks()
    i = 0
    for task in tasks:
        if task['id'] == id:
            return i
        i += 1
    return -1


