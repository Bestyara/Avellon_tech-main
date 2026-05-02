---
name: db-last-time-opened
overview: Добавление поля last_time_opened в таблицу проектов SQLite (как в первой версии схемы) и перевод логики открытия последнего проекта с файлового кэша на это поле.
todos:
  - id: db-schema-migration
    content: Добавить поле last_time_opened в исходную schema v1 в DbStorage (без миграций)
    status: completed
  - id: db-api-last-opened
    content: Реализовать методы update_project_last_opened и get_last_opened_project в DbStorage
    status: completed
  - id: main-window-logic-update
    content: Переписать инициализацию и открытие последнего проекта в MainWindow для работы через БД и поле last_time_opened
    status: completed
  - id: remove-cache-usage
    content: Удалить использование файлового кэша последнего проекта и, при необходимости, мягко очистить старые файлы
    status: completed
  - id: manual-testing
    content: Провести ручную проверку миграции и сценариев открытия проектов
    status: pending
isProject: false
---

## Цель

Добавить в БД поле `last_time_opened` для проектов и полностью перевести логику "последнего открытого проекта" с файлового кэша на это поле, больше не используя кэш-файлы.

## Изменения в схеме БД

- **Считаем, что это первая версия схемы**:
  - Оставляем `SCHEMA_VERSION = 1` в `db_storage.py`.
- **Создание таблицы `projects`** в `_create_schema_v1`:
  - Добавить новый столбец `last_time_opened TEXT` (можно без `NOT NULL`, чтобы старые записи могли иметь `NULL`).
  - Итоговая структура `projects`: `project_id`, `project_name`, `project_path`, `created_at`, `last_time_opened`.
  - `_ensure_schema` можно оставить простым: при `user_version < SCHEMA_VERSION` просто вызывать `_create_schema_v1` и выставлять `user_version = 1` без дополнительных миграций.

## Новые методы работы с last_time_opened в DbStorage

В `[db_storage.py](db_storage.py)`:

- **Метод обновления времени последнего открытия**:
  - Добавить `update_project_last_opened(project_id: str) -> None`, который выполняет:
    - `UPDATE projects SET last_time_opened = datetime('now') WHERE project_id = ?;`.
- **Метод получения последнего открытого проекта**:
  - Добавить `get_last_opened_project() -> Optional[Dict[str, Any]]`, который:
    - Выбирает проекты с непустым путём (`project_path IS NOT NULL`),
    - Сортирует по `datetime(last_time_opened)` по убыванию, с запасной сортировкой по `datetime(created_at)` на случай `NULL` (например, через `ORDER BY COALESCE(last_time_opened, created_at) DESC`),
    - Возвращает первую запись или `None`.

## Изменения логики кэша и открытия проектов

В `[main_window.py](main_window.py)`:

- **Отвязать `MainWindow` от файлового кэша**:
  - В импортах убрать из `third_party` функции `get_last_project_id`, `save_last_project_id`.
- **Инициализация окна (`__cache_init`)**:
  - Переиспользовать текущее место вызова, но изменить реализацию:
    - Вместо `get_last_project_id()` вызывать `self.db.get_last_opened_project()`.
    - Если проект найден и `os.path.isdir(project["project_path"])` — сразу вызвать `self.run_borehole_menu(project["project_path"], project_id=project["project_id"])`.
    - Иначе перейти в `self.run_main_menu()`.
- **Сохранение информации о последнем открытом проекте**:
  - Удалить/переписать метод `__cache_save_project_id`:
    - Вместо записи в файл вызывать `self.db.update_project_last_opened(project_id_)` (без побочных эффектов, если `None`).
  - В `run_borehole_menu`:
    - После получения/определения `project_id` (из БД или параметра) вызывать `update_project_last_opened` для реального `project_id`.
- **Кнопка "Открыть последний проект"**:
  - Метод `open_last_project` переписать так, чтобы он больше не использовал кэш-файл:
    - Получать проект через `self.db.get_last_opened_project()`.
    - Если проект не найден — показывать предупреждение (можно переиспользовать существующий текст про отсутствие проекта).
    - Если папка не существует — тоже предупреждать.
    - При успешном открытии обновить `last_time_opened` (через `update_project_last_opened`) и вызвать `run_borehole_menu`.

## Отказ от файлового кэша

- **Прекратить использование кэша полностью**:
  - После удаления вызовов `get_last_project_id` и `save_last_project_id` файловый кэш больше не участвует в логике.
- **Мягкая очистка старого кэша (опционально)**:
  - В начале работы приложения (например, в инициализации `MainWindow` или в точке входа) аккуратно попытаться удалить файл `cf.CACHE_FILE_LAST_PROJECT_ID_PATH` и/или пустую директорию `cf.CACHE_DIR_PATH`, оборачивая операции в `try/except`, чтобы не ломать запуск.
  - Константы `CACHE_DIR_PATH` и `CACHE_FILE_LAST_PROJECT_ID_PATH` в `config.py` и функции `get_last_project_id` / `save_last_project_id` в `third_party.py` можно оставить для обратной совместимости, но они будут больше не использоваться.

## Проверка и регресс-тесты

- **Проверка миграции БД**:
  - При работе с текущей базой (если она уже существует) достаточно удалить/переинициализировать файл БД, чтобы он был создан заново с полем `last_time_opened`.
  - Убедиться, что таблица `projects` содержит колонку `last_time_opened`.
- **Проверка сценариев работы с проектами**:
  - Создать новый проект, открыть его, закрыть приложение, снова запустить:
    - Главный экран должен автоматически открыть последний проект (через `last_time_opened`).
  - Открыть другой проект из диалога — убедиться, что он становится "последним" и затем открывается через кнопку "Открыть последний проект".
  - Удалить папку проекта с диска и убедиться, что попытка открыть последний проект приводит к корректному предупреждению.
- **Проверка отсутствия зависимостей от кэша**:
  - Убедиться, что при удалённом/недоступном каталоге `__avellon_cache`__ приложение стартует без ошибок и все функции "последнего проекта" работают только через БД.

