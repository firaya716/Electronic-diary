import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-12345'

DATABASE = 'university.db'


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()

        # Создание таблицы subjects с правильной структурой
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        # Создание таблицы users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT NOT NULL
            )
        ''')

        # Создание таблицы grades с обновленной структурой
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                grade INTEGER NOT NULL,
                date TEXT NOT NULL,
                quarter INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (student_id) REFERENCES users (id),
                FOREIGN KEY (subject_id) REFERENCES subjects (id)
            )
        ''')

        # Проверяем, существует ли столбец quarter, если нет - добавляем
        cursor.execute("PRAGMA table_info(grades)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'quarter' not in columns:
            cursor.execute('ALTER TABLE grades ADD COLUMN quarter INTEGER DEFAULT 1')

        # Добавляем предметы только если таблица пустая
        cursor.execute('SELECT COUNT(*) FROM subjects')
        if cursor.fetchone()[0] == 0:
            subjects = [
                ('Математика',),
                ('Физика',),
                ('Химия',),
                ('Информатика',),
                ('Русский язык',),
                ('Литература',),
                ('История',),
                ('Биология',)
            ]
            cursor.executemany('INSERT INTO subjects (name) VALUES (?)', subjects)

        # Добавляем администратора только если его нет
        cursor.execute('SELECT COUNT(*) FROM users WHERE username = "admin"')
        if cursor.fetchone()[0] == 0:
            admin_password = generate_password_hash('admin123')
            cursor.execute('''
                INSERT INTO users (username, password, role, full_name) 
                VALUES (?, ?, ?, ?)
            ''', ('admin', admin_password, 'admin', 'Администратор Системы'))

        # Добавляем преподавателя только если его нет
        cursor.execute('SELECT COUNT(*) FROM users WHERE username = "teacher"')
        if cursor.fetchone()[0] == 0:
            teacher_password = generate_password_hash('teacher123')
            cursor.execute('''
                INSERT INTO users (username, password, role, full_name) 
                VALUES (?, ?, ?, ?)
            ''', ('teacher', teacher_password, 'teacher', 'Иванов Иван'))

        # Добавляем тестовых студентов только если их нет
        cursor.execute('SELECT COUNT(*) FROM users WHERE role = "student"')
        if cursor.fetchone()[0] == 0:
            students_data = [
                ('student1', 'student123', 'student', 'Иванов Иван'),
                ('student2', 'student123', 'student', 'Петров Петр'),
                ('student3', 'student123', 'student', 'Сидорова Анна'),
            ]

            for username, password, role, full_name in students_data:
                hashed_password = generate_password_hash(password)
                cursor.execute('''
                    INSERT INTO users (username, password, role, full_name) 
                    VALUES (?, ?, ?, ?)
                ''', (username, hashed_password, role, full_name))

        # Добавляем тестовые оценки только если их нет
        cursor.execute('SELECT COUNT(*) FROM grades')
        if cursor.fetchone()[0] == 0:
            grades_data = [
                (4, 1, 5, '2025-11-20', 1),  # student1, Математика, 5, 1 четверть
                (4, 2, 4, '2025-11-21', 1),  # student1, Физика, 4, 1 четверть
                (4, 1, 2, '2025-11-25', 1),  # student1, Математика, 2, 1 четверть
                (5, 3, 3, '2025-11-22', 1),  # student2, Химия, 3, 1 четверть
                (5, 4, 2, '2025-11-23', 1),  # student2, Информатика, 2, 1 четверть
                (6, 4, 5, '2025-11-23', 1),  # student3, Информатика, 5, 1 четверть
                (6, 1, 2, '2025-11-24', 1),  # student3, Математика, 2, 1 четверть
                (6, 2, 2, '2025-11-25', 1),  # student3, Физика, 2, 1 четверть
            ]

            cursor.executemany('''
                INSERT INTO grades (student_id, subject_id, grade, date, quarter)
                VALUES (?, ?, ?, ?, ?)
            ''', grades_data)

        conn.commit()


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            flash('Вход выполнен успешно!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template('dashboard.html')


@app.route('/students')
def students():
    if 'user_id' not in session or session['role'] not in ['admin', 'teacher']:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    students = conn.execute('''
        SELECT * FROM users WHERE role = 'student' ORDER BY full_name
    ''').fetchall()
    conn.close()

    return render_template('students.html', students=students)


@app.route('/grades')
def grades():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()

    if session['role'] == 'student':
        # Студент видит только свои оценки
        grades = conn.execute('''
            SELECT g.*, s.name as subject_name, u.full_name as student_name
            FROM grades g
            JOIN subjects s ON g.subject_id = s.id
            JOIN users u ON g.student_id = u.id
            WHERE g.student_id = ?
            ORDER BY g.date DESC
        ''', (session['user_id'],)).fetchall()
    else:
        # Преподаватель и администратор видят все оценки
        grades = conn.execute('''
            SELECT g.*, s.name as subject_name, u.full_name as student_name
            FROM grades g
            JOIN subjects s ON g.subject_id = s.id
            JOIN users u ON g.student_id = u.id
            ORDER BY g.date DESC
        ''').fetchall()

    conn.close()
    return render_template('grades.html', grades=grades)


@app.route('/add_grade', methods=['GET', 'POST'])
def add_grade():
    if 'user_id' not in session or session['role'] not in ['admin', 'teacher']:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        student_id = request.form['student_id']
        subject_id = request.form['subject_id']
        grade = request.form['grade']
        date = request.form['date']
        quarter = request.form['quarter']

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO grades (student_id, subject_id, grade, date, quarter)
            VALUES (?, ?, ?, ?, ?)
        ''', (student_id, subject_id, grade, date, quarter))
        conn.commit()
        conn.close()

        flash('Оценка добавлена успешно!', 'success')
        return redirect(url_for('grades'))

    conn = get_db_connection()
    students = conn.execute('''
        SELECT * FROM users WHERE role = 'student' ORDER BY full_name
    ''').fetchall()
    subjects = conn.execute('SELECT * FROM subjects ORDER BY name').fetchall()
    conn.close()

    return render_template('add_grade.html', students=students, subjects=subjects)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Доступ запрещен', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        last_name = request.form['last_name']
        first_name = request.form['first_name']

        # Собираем ФИО из фамилии и имени
        full_name = f"{last_name} {first_name}"

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO users (username, password, role, full_name)
                VALUES (?, ?, ?, ?)
            ''', (username, hashed_password, role, full_name))
            conn.commit()
            flash('Пользователь зарегистрирован успешно!', 'success')
        except sqlite3.IntegrityError:
            flash('Имя пользователя уже существует', 'error')
        finally:
            conn.close()

        return redirect(url_for('register'))

    return render_template('register.html')


@app.route('/subjects')
def subjects():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    subjects_list = conn.execute('SELECT * FROM subjects ORDER BY name').fetchall()
    conn.close()

    return render_template('subjects.html', subjects=subjects_list)


@app.route('/failing_students')
def failing_students():
    if 'user_id' not in session or session['role'] not in ['admin', 'teacher']:
        flash('Доступ запрещен', 'error')
        return redirect(url_for('dashboard'))

    quarter = request.args.get('quarter', 1, type=int)

    conn = get_db_connection()

    # Получаем студентов с количеством двоек по четвертям
    failing_students = conn.execute('''
        SELECT 
            u.id,
            u.full_name,
            COUNT(CASE WHEN g.grade = 2 THEN 1 END) as fail_count,
            GROUP_CONCAT(DISTINCT s.name) as failing_subjects
        FROM users u
        JOIN grades g ON u.id = g.student_id
        JOIN subjects s ON g.subject_id = s.id
        WHERE u.role = 'student' 
        AND g.quarter = ?
        AND g.grade = 2
        GROUP BY u.id, u.full_name
        HAVING fail_count > 0
        ORDER BY fail_count DESC
    ''', (quarter,)).fetchall()

    # Общая статистика по четверти
    stats = conn.execute('''
        SELECT 
            COUNT(DISTINCT u.id) as total_students,
            COUNT(CASE WHEN g.grade = 2 THEN 1 END) as total_fails,
            COUNT(DISTINCT CASE WHEN g.grade = 2 THEN u.id END) as failing_students_count
        FROM users u
        LEFT JOIN grades g ON u.id = g.student_id AND g.quarter = ? AND g.grade = 2
        WHERE u.role = 'student'
    ''', (quarter,)).fetchone()

    conn.close()

    return render_template('failing_students.html',
                           failing_students=failing_students,
                           quarter=quarter,
                           stats=stats)


@app.route('/student_fails')
def student_fails():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    quarter = request.args.get('quarter', 1, type=int)

    conn = get_db_connection()

    if session['role'] == 'student':
        # Студент видит только свои двойки
        student_fails = conn.execute('''
            SELECT 
                s.name as subject_name,
                g.grade,
                g.date,
                g.quarter
            FROM grades g
            JOIN subjects s ON g.subject_id = s.id
            WHERE g.student_id = ? 
            AND g.quarter = ?
            AND g.grade = 2
            ORDER BY g.date DESC
        ''', (session['user_id'], quarter)).fetchall()

        student_info = conn.execute('''
            SELECT full_name FROM users WHERE id = ?
        ''', (session['user_id'],)).fetchone()

        conn.close()

        return render_template('student_fails.html',
                               student_fails=student_fails,
                               quarter=quarter,
                               student_info=student_info)
    else:
        # Преподаватель и администратор видят все двойки
        all_fails = conn.execute('''
            SELECT 
                u.full_name as student_name,
                s.name as subject_name,
                g.grade,
                g.date,
                g.quarter
            FROM grades g
            JOIN subjects s ON g.subject_id = s.id
            JOIN users u ON g.student_id = u.id
            WHERE g.quarter = ?
            AND g.grade = 2
            ORDER BY u.full_name, g.date DESC
        ''', (quarter,)).fetchall()

        conn.close()

        return render_template('student_fails.html',
                               student_fails=all_fails,
                               quarter=quarter)


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)