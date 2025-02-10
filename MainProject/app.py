from functools import wraps
from os import abort
from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, get_flashed_messages
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from utils import *
from flask_wtf.csrf import CSRFProtect, generate_csrf  # Добавить в импорты
from filters import *
import re


app = Flask(__name__)
app.config.from_object('config.Config')
csrf = CSRFProtect(app)  # Инициализация CSRF-защиты

# Добавим фильтр в Jinja2
app.jinja_env.filters['format_date'] = format_date
app.jinja_env.filters['truncate'] = truncate


# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

ADMIN_PASSWORD = '52'


# Заглушка для модели пользователя
class User:
    def __init__(self, user_data):
        self.id = user_data['id']
        self.login = user_data['login']
        self.email = user_data['email']
        self.full_name = user_data['full_name']
        self.school = user_data.get('school', '')
        self.birth_date = user_data['birth_date']
        self.account_type = user_data['account_type']
        self.password_hash = user_data['password_hash']
        self.profile_image = user_data.get('profile_image', None)

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    users = get_users()
    user_data = next((u for u in users if str(u['id']) == user_id), None)
    return User(user_data) if user_data else None


# Декоратор для проверки ролей
def role_required(roles):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated or current_user.account_type not in roles:
                abort()
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


# Маршруты
@app.route('/learn')
@login_required
def learn():
    # Получаем все одобренные материалы
    materials = load_materials()
    approved_materials = [m for m in materials if m.get('approved', False)]
    for m in approved_materials:
        m['author_login'] = get_user_by_id(m['author_id'])['login']
    return render_template('learn/index.html', materials=approved_materials)


@app.route('/exams')
@login_required
def exams():
    tasks = load_tasks()
    tasks = [t for t in tasks if t.get('approved', False)]
    tasks1 = []
    for t in tasks:
        ch = 1
        if t.get('solved_by'):
            for x in t.get('solved_by'):
                if x['user_id'] == current_user.id:
                    ch = 0
        if ch:
            tasks1.append(t)
    tasks = tasks1

    # Группируем задания по типам и выбираем по одному случайному
    tasks_by_type = {}
    for task in tasks:
        if task['task_number'] not in tasks_by_type:
            tasks_by_type[task['task_number']] = []
        tasks_by_type[task['task_number']].append(task)

    exam_tasks = []
    for task_type, type_tasks in tasks_by_type.items():
        if type_tasks:
            exam_tasks.append(random.choice(type_tasks))

    return render_template('exams/exam.html', tasks=exam_tasks)


@app.route('/exams/submit', methods=['POST'])
@login_required
def submit_exam():
    tasks = load_tasks()
    user_answers = request.form.to_dict(flat=False)
    results = []
    all_cnt = 0
    corr_cnt = 0
    # Обрабатываем ответы для каждого задания
    for key, value in user_answers.items():
        if key.startswith('answer#'):
            task_id = key.split('#')[1]
            task = next((t for t in tasks if t['id'] == task_id), None)
            if task:
                user_answer = value[0].strip().lower()
                correct_answer = str(task['answer']).strip().lower()

                results.append({
                    'task_type': task['task_number'],
                    'user_answer': value[0],
                    'correct_answer': task['answer'],
                    'is_correct': user_answer == correct_answer
                })
                corr_cnt += (user_answer == correct_answer)
                num = get_task_by_id(task_id)
                if 'solved_by' not in tasks[num]:
                    tasks[num]['solved_by'] = []
                task['solved_by'] = [s for s in task['solved_by'] if s['user_id'] != current_user.id]
                tasks[num]['solved_by'].append({
                    'user_id': current_user.id,
                    'is_correct': user_answer == correct_answer,
                    'timestamp': datetime.now().isoformat()
                })

                save_tasks(tasks)
                all_cnt += 1

    return render_template('exams/results.html', results=results, correct_answers=corr_cnt, cnt_answers=all_cnt)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/tasks')
@login_required
def tasks():
    tasks = load_tasks()
    approved_tasks = [t for t in tasks if t.get('approved', False)]
    for task in approved_tasks:
        task['author_login'] = get_user_by_id(task['author_id'])['login']

    # Получаем выбранные номера
    selected_tasks = [int(i) for i in list(request.args.getlist('task_numbers'))]
    # print(selected_tasks)
    difficulty = request.args.get('difficulty', '')

    # Фильтрация по номерам
    if selected_tasks:
        selected_numbers = [int(n) for n in selected_tasks]
        approved_tasks = [t for t in approved_tasks if t['task_number'] in selected_numbers]

    # Остальная фильтрация
    if difficulty:
        approved_tasks = [t for t in approved_tasks if t['difficulty'] == difficulty]

    # Загрузка решенных заданий
    solved_tasks = get_solved_tasks(current_user.id)
    # print(solved_tasks)

    return render_template('tasks/index.html',
                           tasks=approved_tasks,
                           selected_tasks=selected_tasks,
                           solved_tasks=solved_tasks,
                           difficulty=difficulty)


@app.route('/add-task', methods=['GET', 'POST'])
@login_required
@role_required(['teacher', 'admin'])
def add_task():
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            task_number = int(request.form.get('task_number'))
            question = request.form.get('question').strip()
            answer = request.form.get('answer').strip()
            source = request.form.get('source', '').strip()
            explanation = request.form.get('explanation', '').strip()
            difficulty = request.form.get('difficulty')  # Новое поле

            # Валидация данных
            if not (1 <= task_number <= 27):
                raise ValueError("Номер задания должен быть от 1 до 27")
            if not question or not answer or not difficulty:
                raise ValueError("Заполните обязательные поля")

            # Сохраняем задание
            new_task = {
                'id': generate_id(),
                'task_number': task_number,
                'question': question,
                'answer': answer,
                'source': source,
                'explanation': explanation,
                'difficulty': difficulty,  # Новое поле
                'author_id': current_user.id,
                'created_at': datetime.now().isoformat(),
                'approved': False
            }

            tasks = load_tasks()
            tasks.append(new_task)
            save_tasks(tasks)

            flash('Задание успешно добавлено!', 'success')
            return redirect(url_for('index'))

        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('add_task'))

    return render_template('add-task.html')


# Модерация заданий
@app.route('/moderation/tasks')
@login_required
@role_required(['admin'])
def moderation_tasks():
    tasks = load_tasks()
    unapproved_tasks = [t for t in tasks if not t.get('approved', False)]
    return render_template('moderation/tasks.html', tasks=unapproved_tasks)


@app.route('/moderation/approve-task/<task_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def approve_task(task_id):
    tasks = load_tasks()
    for task in tasks:
        if task['id'] == task_id:
            task['approved'] = True
            task['approved_by'] = current_user.id
            task['approved_at'] = datetime.now().isoformat()
            break
    save_tasks(tasks)
    flash('Задание одобрено!', 'success')
    return redirect(url_for('moderation_tasks'))


@app.route('/moderation/reject-task/<task_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def reject_task(task_id):
    tasks = load_tasks()
    tasks = [t for t in tasks if t['id'] != task_id]
    save_tasks(tasks)
    flash('Задание отклонено и удалено!', 'success')
    return redirect(url_for('moderation_tasks'))


@app.route('/check-answer', methods=['POST'])
@login_required
def check_answer():
    task_id = request.form.get('task_id')
    user_answer = request.form.get('answer', '').strip()

    tasks = load_tasks()
    task = next((t for t in tasks if t['id'] == task_id), None)

    if not task:
        return jsonify({'error': 'Задание не найдено'}), 404

    existing_solution = next(
        (s for s in task.get('solved_by', []) if s['user_id'] == current_user.id),
        None
    )

    is_correct = (user_answer.lower() == task['answer'].lower())

    task.setdefault('solved_by', []).append({
        'user_id': current_user.id,
        'is_correct': is_correct,
        'timestamp': datetime.now().isoformat()
    })

    if not existing_solution:
        save_tasks(tasks)

    return jsonify({
        'is_correct': is_correct,
        'correct_answer': task['answer'],
        'explanation': task.get('explanation', ''),
        'already_solved': False
    })


@app.route('/task/edit/<task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    tasks = load_tasks()
    task = next((t for t in tasks if t['id'] == task_id), None)

    if task['author_id'] != current_user.id and current_user.account_type != 'admin':
        flash('У вас нет прав для редактирования этого задания', 'error')
        return redirect(url_for('tasks'))

    # Проверка прав
    if not task or (current_user.id != task['author_id'] and current_user.account_type != 'admin'):
        abort()

    if request.method == 'POST':
        try:
            # Обновляем данные
            task['task_number'] = int(request.form.get('task_number'))
            task['question'] = request.form.get('question').strip()
            task['answer'] = request.form.get('answer').strip()
            task['source'] = request.form.get('source', '').strip()
            task['explanation'] = request.form.get('explanation', '').strip()
            task['difficulty'] = request.form.get('difficulty')
            task['approved'] = False
            task['solved_by'].clear()

            # Валидация
            if not (1 <= task['task_number'] <= 27):
                raise ValueError("Номер задания должен быть от 1 до 27")

            save_tasks(tasks)
            flash('Задание успешно обновлено!', 'success')
            return redirect(url_for('tasks'))

        except ValueError as e:
            flash(str(e), 'error')

    return render_template('edit_task.html', task=task)


@app.route('/add-material', methods=['GET', 'POST'])
@login_required
@role_required(['teacher', 'admin'])
def add_material():
    if request.method == 'POST':
        # Получаем данные из формы
        title = request.form.get('title')
        content = request.form.get('content')
        image = request.files.get('image')

        # Проверяем, заполнено ли поле "Название"
        if not title:
            flash('Поле "Название" обязательно для заполнения!', 'error')
            return redirect(url_for('add_material'))

        # Сохраняем материал в JSON-файл
        materials = load_materials()
        new_material = {
            'id': generate_id(),
            'title': title,
            'content': content,
            'image': image.filename if image else None,
            'author_id': current_user.id,
            'author_login': current_user.login,
            'created_at': datetime.now().isoformat(),
            'approved': False  # По умолчанию материал не одобрен
        }
        materials.append(new_material)
        save_materials(materials)

        # Сохраняем изображение, если оно было загружено
        if image:
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image.filename)
            image.save(image_path)

        flash('Материал успешно добавлен и ожидает модерации!', 'success')
        return redirect(url_for('index'))

    return render_template('add-material.html')


@app.route('/moderation')
@login_required
@role_required(['admin'])
def moderation():
    return render_template('moderation.html')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif'})


@app.route('/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile'))

    file = request.files['avatar']
    if file.filename == '':
        flash('Файл не выбран', 'error')
        return redirect(url_for('profile'))

    if file and allowed_file(file.filename):
        try:
            # Генерируем уникальное имя файла
            filename = f"{current_user.id}_{int(time.time())}.{file.filename.rsplit('.', 1)[1].lower()}"
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

            # Сохраняем файл
            file.save(filepath)

            # Обновляем запись пользователя
            users = get_users()
            for user in users:
                if user['id'] == current_user.id:
                    # Удаляем старый аватар
                    if user.get('profile_image'):
                        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], user['profile_image'])
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except Exception as e:
                                app.logger.error(f"Error deleting old avatar: {str(e)}")

                    user['profile_image'] = filename
                    break

            save_users(users)
            flash('Аватар успешно обновлен!', 'success')
        except Exception as e:
            app.logger.error(f"Avatar upload error: {str(e)}")
            flash('Ошибка при сохранении файла', 'error')
    else:
        flash('Разрешены только файлы: PNG, JPG, JPEG, GIF', 'error')

    return redirect(url_for('profile'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            new_data = {
                'login': request.form.get('login').strip(),
                'email': request.form.get('email').strip(),
                'full_name': request.form.get('full_name').strip(),
                'school': request.form.get('school', '').strip(),
                'birth_date': request.form.get('birth_date')
            }

            # Валидация данных
            if len(new_data['login']) < 3 or len(new_data['login']) > 20:
                raise ValueError('Логин должен быть от 3 до 20 символов')

            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', new_data['email']):
                raise ValueError('Введите корректный email')

            try:
                datetime.strptime(new_data['birth_date'], '%Y-%m-%d')
            except ValueError:
                raise ValueError('Некорректная дата рождения')

            # Проверка уникальности логина и email
            users = get_users()
            for user in users:
                if user['id'] != current_user.id:
                    if user['login'] == new_data['login']:
                        raise ValueError('Этот логин уже занят')
                    if user['email'] == new_data['email']:
                        raise ValueError('Этот email уже зарегистрирован')

            # Обновляем данные пользователя
            for user in users:
                if user['id'] == current_user.id:
                    user.update(new_data)
                    break

            save_users(users)
            flash('Данные успешно обновлены!', 'success')
            return redirect(url_for('profile'))

        except ValueError as e:
            flash(str(e), 'error')

    stats = get_task_stats_by_number(current_user.id)

    return render_template('profile.html',
                           stats=stats)


# Обновляем маршруты
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))




@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        login_cred = request.form.get('login').strip()
        password = request.form.get('password').strip()

        # Ищем пользователя по логину или email
        user_data = get_user_by_login(login_cred) or get_user_by_email(login_cred)

        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data)
            login_user(user)
            return redirect(url_for('index'))

        return render_template('auth/login.html', error='Неверные учетные данные')

    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        account_type = request.form.get('account_type')
        admin_password = request.form.get('admin_password', '')

        if account_type == 'admin' and admin_password != ADMIN_PASSWORD:
            return render_template('auth/register.html',
                                   error='Неверный админ-пароль',
                                   form_data=request.form)

        try:
            login = request.form.get('login').strip()
            email = request.form.get('email').strip()
            password = request.form.get('password').strip()
            full_name = request.form.get('full_name').strip()
            school = request.form.get('school', '').strip()
            birth_date = request.form.get('birth_date')
            account_type = request.form.get('account_type')

            # Валидация даты рождения
            try:
                datetime.strptime(birth_date, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Некорректная дата рождения')

            user, error = create_user(
                login=login,
                email=email,
                password=password,
                full_name=full_name,
                school=school,
                birth_date=birth_date,
                account_type=account_type
            )

            if error:
                raise ValueError(error)

            login_user(User(user))
            return redirect(url_for('index'))

        except ValueError as e:
            return render_template('auth/register.html',
                                   error=str(e),
                                   form_data=request.form)

    return render_template('auth/register.html')


@app.route('/forum', methods=['GET', 'POST'])
@login_required
def forum():
    if request.method == 'POST':
        # Обработка нового сообщения
        new_message = {
            'id': generate_id(),
            'user_id': current_user.id,
            'author': current_user.login,
            'text': request.form.get('text'),
            'timestamp': datetime.now().isoformat(),
            'likes': 0,
            'dislikes': 0,
            'liked_by': [],
            'disliked_by': []
        }

        if save_message(new_message):
            flash('Сообщение успешно опубликовано!', 'success')
        else:
            flash('Ошибка при публикации сообщения', 'error')

        sort_param = request.args.get('sort', 'recent')  # Получаем текущую сортировку
        return redirect(url_for('forum', sort=sort_param))  # Сохраняем параметр

    # Получаем параметр сортировки из запроса
    sort_by = request.args.get('sort', 'recent')
    messages = get_messages(sort_by)
    for i in messages:
        i['author'] = get_user_by_id(i['user_id'])['login']

    return render_template(
        'forum/index.html',
        messages=messages,
        current_user_id=current_user.id,
        csrf_token=generate_csrf(),
        sort_by=sort_by
    )


def update_reaction(message_id, reaction_type):
    messages = load_messages()
    for message in messages:
        if message['id'] == message_id:
            message[reaction_type] += 1
            break
    save_to_file('forum.json', {'messages': messages})


@app.route('/forum/like/<message_id>', methods=['POST'])
@login_required
def like_message(message_id):
    try:
        data = load_forum_data()
        message = next((msg for msg in data['messages'] if msg['id'] == message_id), None)

        if not message:
            return jsonify(success=False, error="Сообщение не найдено"), 404

        user_id = str(current_user.id)

        if user_id in message['liked_by']:
            message['likes'] -= 1
            message['liked_by'].remove(user_id)
        else:
            if user_id in message['disliked_by']:
                message['dislikes'] -= 1
                message['disliked_by'].remove(user_id)
            message['likes'] += 1
            message['liked_by'].append(user_id)

        save_forum_data(data)  # Убедитесь, что эта функция не вызывает ошибок
        return jsonify(
            success=True,
            likes=message['likes'],
            dislikes=message['dislikes'],
            user_reaction='like' if user_id in message['liked_by'] else 'none'
        )

    except Exception as e:
        # Логируем ошибку и возвращаем JSON
        print(f"Ошибка при обработке лайка: {str(e)}")
        return jsonify(success=False, error="Внутренняя ошибка сервера"), 500


@app.route('/forum/dislike/<message_id>', methods=['POST'])
@login_required
def dislike_message(message_id):
    try:
        data = load_forum_data()
        message = next((msg for msg in data['messages'] if msg['id'] == message_id), None)

        if not message:
            return jsonify(success=False, error="Сообщение не найдено"), 404

        user_id = str(current_user.id)

        if user_id in message['disliked_by']:
            message['dislikes'] -= 1
            message['disliked_by'].remove(user_id)
        else:
            if user_id in message['liked_by']:
                message['likes'] -= 1
                message['liked_by'].remove(user_id)
            message['dislikes'] += 1
            message['disliked_by'].append(user_id)

        save_forum_data(data)  # Убедитесь, что эта функция не вызывает ошибок
        return jsonify(
            success=True,
            likes=message['likes'],
            dislikes=message['dislikes'],
            user_reaction='dislike' if user_id in message['disliked_by'] else 'none'
        )

    except Exception as e:
        # Логируем ошибку и возвращаем JSON
        print(f"Ошибка при обработке лайка: {str(e)}")
        return jsonify(success=False, error="Внутренняя ошибка сервера"), 500


@app.route('/forum/delete/<message_id>', methods=['DELETE'])
@login_required
def delete_message(message_id):
    try:
        # print(f"\n=== DELETE REQUEST ===")
        # print(f"User ID: {current_user.id}, Account Type: {current_user.account_type}")
        # print(f"Target Message ID: {message_id}")

        # Получаем сообщение
        message = get_message_by_id(message_id)
        if not message:
            # print("Message not found")
            return jsonify(success=False, error="Сообщение не найдено"), 404

        # print(f"Message found: {message}")

        # Проверка прав
        if current_user.account_type != 'admin' and current_user.id != message['user_id']:
            # print("Permission denied")
            return jsonify(success=False, error="Нет прав на удаление"), 

        # Удаление
        if delete_message_from_db(message_id):
            # print("Deletion successful")
            return jsonify(success=True)

        # print("Deletion failed")
        return jsonify(success=False, error="Ошибка при удалении"), 500

    except Exception as e:
        # print(f"Error: {str(e)}")
        return jsonify(success=False, error=str(e)), 500


@app.route('/forum/reaction/<message_id>')
@login_required
def check_reaction(message_id):
    data = load_forum_data()
    message = next((msg for msg in data['messages'] if str(msg['id']) == str(message_id)), None)
    if not message:
        return jsonify(reaction='none')

    user_id = str(current_user.id)
    reaction = 'none'

    if user_id in message.get('liked_by', []):
        reaction = 'like'
    elif user_id in message.get('disliked_by', []):
        reaction = 'dislike'

    return jsonify(reaction=reaction)


@app.route('/moderation/materials')
@login_required
@role_required(['admin'])
def moderation_materials():
    # Получаем все непроверенные материалы
    materials = load_materials()
    unapproved_materials = [m for m in materials if not m.get('approved', False)]
    return render_template('moderation/materials.html', materials=unapproved_materials)


@app.route('/moderation/approve/<material_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def approve_material(material_id):
    materials = load_materials()
    for material in materials:
        if material['id'] == material_id:
            material['approved'] = True
            material['approved_by'] = current_user.id
            material['approved_at'] = datetime.now().isoformat()
            break
    save_materials(materials)
    flash('Материал одобрен!', 'success')
    return redirect(url_for('moderation_materials'))


@app.route('/moderation/reject/<material_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def reject_material(material_id):
    materials = load_materials()
    materials = [m for m in materials if m['id'] != material_id]
    save_materials(materials)
    flash('Материал отклонен и удален!', 'success')
    return redirect(url_for('moderation_materials'))


@app.route('/material/delete/<material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    materials = load_materials()
    material = next((m for m in materials if m['id'] == material_id), None)

    # Проверка прав: удалять может только автор или администратор
    if not material or (current_user.id != material['author_id'] and current_user.account_type != 'admin'):
        flash('У вас нет прав на удаление этого материала!', 'error')
        return redirect(url_for('learn'))

    # Удаляем материал
    materials = [m for m in materials if m['id'] != material_id]
    save_materials(materials)

    # Удаляем изображение, если оно есть
    if material.get('image'):
        try:
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], material['image'])
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            print(f"Ошибка при удалении изображения: {e}")

    flash('Материал успешно удален!', 'success')
    return redirect(url_for('learn'))


@app.route('/material/edit/<material_id>', methods=['GET', 'POST'])
@login_required
def edit_material(material_id):
    materials = load_materials()
    material = next((m for m in materials if m['id'] == material_id), None)

    # Проверка прав: редактировать может только автор или администратор
    if not material or (current_user.id != material['author_id'] and current_user.account_type != 'admin'):
        flash('У вас нет прав на редактирование этого материала!', 'error')
        return redirect(url_for('learn'))

    if request.method == 'POST':
        # Обновляем данные материала
        material['title'] = request.form.get('title')
        material['content'] = request.form.get('content')
        image = request.files.get('image')
        material['approved'] = False

        # Обновляем изображение, если оно было загружено
        if image:
            # Удаляем старое изображение, если оно есть
            if material.get('image'):
                try:
                    old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], material['image'])
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                except Exception as e:
                    print(f"Ошибка при удалении старого изображения: {e}")

            # Сохраняем новое изображение
            material['image'] = image.filename
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image.filename)
            image.save(image_path)

        save_materials(materials)
        flash('Материал успешно обновлен!', 'success')
        return redirect(url_for('learn'))

    return render_template('learn/edit_material.html', material=material)



@app.route('/groups/create', methods=['GET', 'POST'])
@login_required
@role_required(['teacher', 'admin'])
def create_group():
    if request.method == 'POST':
        groups = load_groups()
        new_group = {
            'id': generate_id(),
            'name': request.form.get('group_name'),
            'description': request.form.get('description'),
            'token': generate_id(),  # Генерируем уникальный токен
            'created_by': current_user.id,
            'members': [ current_user.id ],
            'created_at': datetime.now().isoformat()
        }
        groups.append(new_group)
        save_groups(groups)
        return render_template('groups/create_group.html', token=new_group['token'])
    return render_template('groups/create_group.html')


@app.route('/groups/join', methods=['GET', 'POST'])
@login_required
def join_group():
    if request.method == 'POST':
        token = request.form.get('token').strip()
        groups = load_groups()
        group = next((g for g in groups if g['token'] == token), None)

        if group:
            if current_user.id not in group['members']:
                group['members'].append(current_user.id)
                save_groups(groups)
                flash('Вы успешно присоединились к группе!', 'success')
            else:
                flash('Вы уже состоите в этой группе', 'warning')
            return redirect(url_for('join_group'))

        flash('Неверный токен группы', 'error')
        return redirect(url_for('join_group'))  # Перенаправляем обратно на страницу ввода токена

    # Отображаем все flash-сообщения
    _messages = get_flashed_messages(with_categories=True)
    messages = []
    for s in _messages:
        if s[1] == "Вы успешно присоединились к группе!" or s[1] == "Вы уже состоите в этой группе" or s[1] == "Неверный токен группы":
            messages.append(s)
    return render_template('groups/join_group.html', messages=messages)


@app.route('/groups')
@login_required
def my_groups():
    # Получаем все группы
    all_groups = load_groups()

    # Фильтруем группы, где пользователь является участником
    user_groups = []
    for group in all_groups:
        if current_user.id in group['members']:
            # Находим создателя группы
            creator = get_user_by_id(group['created_by'])
            # Добавляем информацию о создателе в объект группы
            group['creator'] = creator
            user_groups.append(group)

    return render_template('groups/list.html', groups=user_groups)


@app.route('/groups/<token>')
@login_required
def group_detail(token):
    all_groups = load_groups()
    group = next((g for g in all_groups if g['token'] == token), None)

    if not group:
        flash('Группа не найдена', 'error')
        return redirect(url_for('my_groups'))

    all_tasks = load_tasks()
    all_materials = load_materials()

    enriched_materials = []
    for material in group.get('materials', []):
        item = None
        if material['type'] == 'task':
            item = next((t for t in all_tasks if t['id'] == material['id']), None)
            item_type = 'Задание'
        elif material['type'] == 'material':
            item = next((m for m in all_materials if m['id'] == material['id']), None)
            item_type = 'Материал'
        elif material['type'] == 'course':
            item = {'title': f"Курс {material['id']}", 'type': 'course'}
            item_type = 'Курс'

        if item:
            enriched = {
                'id': material['id'],
                'type': material['type'],
                'added_at': material['added_at'],
                'data': item,
                'item_type': item_type
            }
            enriched_materials.append(enriched)

    # Сортировка по дате добавления
    enriched_materials.sort(key=lambda x: x['added_at'], reverse=True)

    return render_template('groups/group.html',
                           group=group,
                           materials=enriched_materials,
                           get_user_by_id=get_user_by_id)


@app.route('/groups/delete/<token>', methods=['POST'])
@login_required
@role_required(['teacher', 'admin'])
def delete_group(token):
    groups = load_groups()

    # Ищем группу для удаления
    group_to_delete = next((g for g in groups if g['token'] == token), None)

    if not group_to_delete:
        flash('Группа не найдена', 'error')
        return redirect(url_for('my_groups'))

    # Проверяем права на удаление
    if current_user.id != group_to_delete['created_by'] and current_user.account_type != 'admin':
        flash('У вас нет прав на удаление этой группы', 'error')
        return redirect(url_for('group_detail', token=token))

    # Удаляем группу
    groups = [g for g in groups if g['token'] != token]
    save_groups(groups)

    flash('Группа успешно удалена', 'success')
    return redirect(url_for('my_groups'))


@app.route('/groups/<token>/remove-member/<int:user_id>', methods=['POST'])
@login_required
def remove_member(token, user_id):
    groups = load_groups()
    group = next((g for g in groups if g['token'] == token), None)

    if not group:
        flash('Группа не найдена', 'error')
        return redirect(url_for('my_groups'))

    # Проверка прав
    if current_user.id != group['created_by'] and current_user.account_type != 'admin':
        flash('У вас нет прав для этого действия', 'error')
        return redirect(url_for('group_detail', token=token))

    # Удаляем участника
    if user_id in group['members']:
        group['members'].remove(user_id)
        save_groups(groups)
        flash('Участник успешно удален', 'success')
    else:
        flash('Участник не найден в группе', 'warning')

    return redirect(url_for('group_detail', token=token))


@app.route('/groups/<token>/add-material', methods=['POST'])
@login_required
@role_required(['teacher', 'admin'])
def add_material_to_group(token):
    groups = load_groups()
    group = next((g for g in groups if g['token'] == token), None)

    if not group:
        flash('Группа не найдена', 'error')
        return redirect(url_for('my_groups'))

    material_type = request.form.get('material_type')
    material_id = request.form.get('material_id')

    # Проверка существования материала
    if not validate_material_exists(material_type, material_id):
        flash('Материал с указанным ID не найден', 'error')
        return redirect(url_for('group_detail', token=token))

    # Добавление материала
    new_material = {
        'id': material_id,
        'type': material_type,
        'added_by': current_user.id,
        'added_at': datetime.now().isoformat()
    }

    if 'materials' not in group:
        group['materials'] = []

    group['materials'].append(new_material)
    save_groups(groups)

    flash('Материал успешно добавлен', 'success')
    return redirect(url_for('group_detail', token=token))


def validate_material_exists(material_type, material_id):
    """Проверяет существование материала в системе"""
    if material_type == 'material':
        materials = load_materials()
        return any(m['id'] == material_id for m in materials)
    elif material_type == 'task':
        tasks = load_tasks()
        return any(t['id'] == material_id for t in tasks)
    elif material_type == 'course':
        # Заглушка для будущей реализации курсов
        return True
    return False


@app.route('/groups/<token>/remove-material/<material_id>', methods=['POST'])
@login_required
@role_required(['teacher', 'admin'])
def remove_material_from_group(token, material_id):
    groups = load_groups()
    group = next((g for g in groups if g['token'] == token), None)

    if not group:
        flash('Группа не найдена', 'error')
        return redirect(url_for('my_groups'))

    # Удаляем материал
    if 'materials' in group:
        initial_count = len(group['materials'])
        group['materials'] = [m for m in group['materials'] if m['id'] != material_id]

        if initial_count == len(group['materials']):
            flash('Материал не найден в группе', 'warning')
        else:
            save_groups(groups)
            flash('Материал успешно удален', 'success')

    return redirect(url_for('group_detail', token=token))

if __name__ == '__main__':
    app.run(port=8080, host="127.0.0.1")
