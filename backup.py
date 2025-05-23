import subprocess
import zipfile
import os
import datetime
import sys
from tkinter import Tk, filedialog

# === Конфигурация ===
DB_NAME = "Avellon_v7"
DB_USER = "postgres"
DB_HOST = "localhost"
DB_PASSWORD = "postgres"  # Лучше взять из переменной окружения

FOLDER_TO_ARCHIVE_NAME = "projects"  # Название папки внутри проекта
PG_DUMP_PATH = "pg_dump"  # Убедитесь, что он в PATH, или укажите полный путь

# === Пути ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Папка, где находится скрипт
BACKUP_DIR = os.path.join(BASE_DIR, "backup")
FOLDER_TO_ARCHIVE = os.path.join(BASE_DIR, FOLDER_TO_ARCHIVE_NAME)
PROJECTS_DIR = os.path.join(BASE_DIR, "dump_projects")

def CreateBackup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    # === Метка времени ===
    DATE = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    db_dump_file = os.path.join(BACKUP_DIR, f"db_backup_{DATE}.dump")
    zip_file = os.path.join(BACKUP_DIR, f"folder_backup_{DATE}.zip")

    # === Создание дампа БД ===
    try:
        subprocess.run(
            [PG_DUMP_PATH, "-U", DB_USER, "-h", DB_HOST, "-F", "c", "-f", db_dump_file, DB_NAME],
            check=True,
            env={**os.environ, "PGPASSWORD": DB_PASSWORD}
        )
        print(f"✅ Дамп БД создан: {db_dump_file}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при дампе БД: {e}")
        exit(1)

    # === Архивация папки ===
    if not os.path.isdir(FOLDER_TO_ARCHIVE):
        print(f"❌ Папка не найдена: {FOLDER_TO_ARCHIVE}")
        exit(1)

    try:
        with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(FOLDER_TO_ARCHIVE):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, FOLDER_TO_ARCHIVE)
                    zipf.write(full_path, arcname=rel_path)
        print(f"✅ Папка заархивирована: {zip_file}")
    except Exception as e:
        print(f"❌ Ошибка при создании архива: {e}")

# === Функция выбора файла из списка ===
def choose_file(files, description):
    if not files:
        print(f"❌ Нет доступных {description} файлов.")
        sys.exit(1)

    print(f"\nДоступные {description} файлы:")
    for i, filename in enumerate(files, start=1):
        print(f"{i}. {filename}")

    while True:
        try:
            choice = int(input(f"Введите номер {description} файла: "))
            if 1 <= choice <= len(files):
                return files[choice - 1]
            else:
                print("Неверный выбор.")
        except ValueError:
            print("Введите число.")

# === GUI-выбор файла ===
def select_file(filetypes, title):
    root = Tk()
    root.withdraw()  # Скрываем главное окно
    file_path = filedialog.askopenfilename(
        title=title,
        initialdir=os.path.join(BASE_DIR, "backup"),
        filetypes=filetypes
    )
    root.destroy()
    if not file_path:
        print("❌ Файл не выбран. Отмена.")
        sys.exit(1)
    return file_path

def RecoveryFromBackup():
    # === Шаг 1: выбор дампа ===
    print("🔍 Выберите файл дампа (.dump)")
    dump_path = select_file([("PostgreSQL Dump Files", "*.dump")], "Выбор файла дампа")

    # === Шаг 2: выбор архива ===
    print("🔍 Выберите архив папки (.zip)")
    zip_path = select_file([("ZIP Archives", "*.zip")], "Выбор ZIP-архива")

    # === Восстановление БД ===
    print(f"\n▶ Восстановление базы данных из: {os.path.basename(dump_path)}")
    try:
        subprocess.run(
            ["pg_restore", "-U", DB_USER, "-h", DB_HOST, "-d", DB_NAME, "-c", dump_path],
            check=True,
            env={**os.environ, "PGPASSWORD": DB_PASSWORD}
        )
        print("✅ База данных успешно восстановлена.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка восстановления БД: {e}")
        sys.exit(1)

    # === Распаковка архива ===
    print(f"\n▶ Распаковка архива: {os.path.basename(zip_path)}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(PROJECTS_DIR)
        print(f"✅ Архив успешно распакован в {PROJECTS_DIR}")
    except Exception as e:
        print(f"❌ Ошибка при распаковке архива: {e}")

# CreateBackup()
# RecoveryFromBackup()