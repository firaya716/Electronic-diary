from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from datetime import date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

DB_NAME = 'electronic_diary.db'

# Декоратор для проверки ролей
def role_required(required_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                flash('Пожалуйста, войдите в систему')
                return redirect(url_for('login'))
            if session['role'] not in required_roles:
                flash('Недостаточно прав для выполнения этой операции')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Создаем таблицу пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student', 'staff', 'admin')),
            student_id INTEGER,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            class TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            grade INTEGER NOT NULL CHECK(grade BETWEEN 1 AND 5),
            date TEXT NOT NULL,
            quarter INTEGER NOT NULL CHECK(quarter BETWEEN 1 AND 4),
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (subject_id) REFERENCES subjects(id)
        )
    ''')

    # Добавляем тестовые данные
    cursor.execute('SELECT COUNT(*) FROM subjects')
    if cursor.fetchone()[0] == 0:
        subjects = [
            ('Математика',), ('Русский язык',), ('Физика',), 
            ('История',), ('Английский язык',), ('Химия',), ('Биология',)
        ]
        cursor.executemany('INSERT INTO subjects (name) VALUES (?)', subjects)

    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        # Добавляем тестового администратора
        cursor.execute(
            'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
            ('admin', 'admin123', 'admin')
        )

    conn.commit()
    conn.close()

# Главная страница
@app.route('/')
def index():
    return render_template('index.html', user_role=session.get('role'))

# Авторизация
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, username, role FROM users WHERE username = ? AND password = ?',
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[2]
            flash(f'Добро пожаловать, {username}!')
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль')
    
    return render_template('login.html')

# Выход из системы
@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы')
    return redirect(url_for('index'))

# Добавление ученика
@app.route('/add_student', methods=['GET', 'POST'])
@role_required(['staff', 'admin'])
def add_student():
    if request.method == 'POST':
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        class_name = request.form['class_name'].strip()

        if not (first_name and last_name and class_name):
            flash('Пожалуйста, заполните все поля')
            return redirect(url_for('add_student'))

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO students (first_name, last_name, class) VALUES (?, ?, ?)',
            (first_name, last_name, class_name)
        )
        conn.commit()
        conn.close()
        flash('Ученик успешно добавлен!')
        return redirect(url_for('students_list'))
    
    return render_template('add_student.html')

# Список учеников
@app.route('/students')
@role_required(['student', 'staff', 'admin'])
def students_list():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, first_name, last_name, class FROM students ORDER BY class, last_name')
    students = cursor.fetchall()
    conn.close()
    
    return render_template('students_list.html', students=students)

# Добавление оценки
@app.route('/add_grade', methods=['GET', 'POST'])
@role_required(['staff', 'admin'])
def add_grade():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT id, first_name, last_name, class FROM students ORDER BY class, last_name')
    students = cursor.fetchall()

    cursor.execute('SELECT id, name FROM subjects ORDER BY name')
    subjects = cursor.fetchall()
    conn.close()

    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject_id = request.form.get('subject_id')
        grade = request.form.get('grade')
        quarter = request.form.get('quarter')

        if not (student_id and subject_id and grade and quarter):
            flash('Пожалуйста, заполните все поля')
            return redirect(url_for('add_grade'))

        if not grade.isdigit() or int(grade) not in range(1, 6):
            flash('Оценка должна быть числом от 1 до 5')
            return redirect(url_for('add_grade'))
        if not quarter.isdigit() or int(quarter) not in range(1, 5):
            flash('Четверть должна быть числом от 1 до 4')
            return redirect(url_for('add_grade'))

        today = date.today().strftime('%Y-%m-%d')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO grades (student_id, subject_id, grade, date, quarter)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_id, subject_id, int(grade), today, int(quarter)))
        conn.commit()
        conn.close()
        flash('Оценка успешно добавлена!')
        return redirect(url_for('view_grades'))

    return render_template('add_grade.html', students=students, subjects=subjects)

# Просмотр всех оценок
@app.route('/grades')
@role_required(['student', 'staff', 'admin'])
def view_grades():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Если пользователь - студент, показываем только его оценки
    if session.get('role') == 'student':
        # Здесь нужно добавить логику для определения student_id пользователя
        cursor.execute('''
            SELECT s.first_name, s.last_name, s.class, sub.name, g.grade, g.date, g.quarter
            FROM grades g
            JOIN students s ON g.student_id = s.id
            JOIN subjects sub ON g.subject_id = sub.id
            ORDER BY s.class, s.last_name, sub.name, g.date
        ''')
    else:
        cursor.execute('''
            SELECT s.first_name, s.last_name, s.class, sub.name, g.grade, g.date, g.quarter
            FROM grades g
            JOIN students s ON g.student_id = s.id
            JOIN subjects sub ON g.subject_id = sub.id
            ORDER BY s.class, s.last_name, sub.name, g.date
        ''')
    
    grades = cursor.fetchall()
    conn.close()

    # Группируем оценки по ученикам
    grouped = {}
    for first_name, last_name, class_name, subject, grade, date_, quarter in grades:
        student = f"{first_name} {last_name} ({class_name})"
        if student not in grouped:
            grouped[student] = []
        grouped[student].append((subject, grade, date_, quarter))

    return render_template('view_grades.html', grades=grouped)

# Расчет среднего балла
@app.route('/average_grade', methods=['GET', 'POST'])
@role_required(['student', 'staff', 'admin'])
def average_grade():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, first_name, last_name, class FROM students ORDER BY class, last_name')
    students = cursor.fetchall()
    
    cursor.execute('SELECT id, name FROM subjects ORDER BY name')
    subjects = cursor.fetchall()
    conn.close()

    result = None
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject_id = request.form.get('subject_id')
        quarter = request.form.get('quarter')

        if not (student_id and subject_id and quarter):
            flash('Пожалуйста, заполните все поля')
            return redirect(url_for('average_grade'))

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT AVG(grade) 
            FROM grades 
            WHERE student_id = ? AND subject_id = ? AND quarter = ?
        ''', (student_id, subject_id, quarter))
        
        avg_grade = cursor.fetchone()[0]
        conn.close()

        if avg_grade:
            # Получаем информацию об ученике и предмете для отображения
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute('SELECT first_name, last_name FROM students WHERE id = ?', (student_id,))
            student = cursor.fetchone()
            cursor.execute('SELECT name FROM subjects WHERE id = ?', (subject_id,))
            subject = cursor.fetchone()
            conn.close()
            
            result = {
                'student_name': f"{student[0]} {student[1]}",
                'subject': subject[0],
                'quarter': quarter,
                'average': round(avg_grade, 2)
            }
        else:
            flash('Оценки не найдены для указанных параметров')

    return render_template('average_grade.html', students=students, subjects=subjects, result=result)

# Подсчет двоек в четверти
@app.route('/count_twos', methods=['GET', 'POST'])
@role_required(['staff', 'admin'])
def count_twos():
    if request.method == 'POST':
        quarter = request.form.get('quarter')
        if not quarter or not quarter.isdigit() or int(quarter) not in range(1, 5):
            flash('Введите корректный номер четверти от 1 до 4')
            return redirect(url_for('count_twos'))

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.class, COUNT(*) as twos_count
            FROM grades g
            JOIN students s ON g.student_id = s.id
            WHERE g.grade = 2 AND g.quarter = ?
            GROUP BY s.class
            ORDER BY s.class
        ''', (quarter,))
        results = cursor.fetchall()
        conn.close()

        total = sum(count for _, count in results)
        return render_template('count_twos_result.html', quarter=quarter, results=results, total=total)

    return render_template('count_twos.html')

# Запуск приложения
if __name__ == '__main__':
    init_db()
    app.run(debug=True)