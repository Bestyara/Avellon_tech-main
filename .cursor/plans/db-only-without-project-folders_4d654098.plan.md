---
name: db-only-without-project-folders
overview: Убрать зависимость приложения от папки `projects` и от проверки существования каталогов, оставив хранение и открытие проектов только через БД в `db_storage.dat`. Обновить UI/потоки открытия проекта так, чтобы проект идентифицировался по `project_id` и `project_name`, без `project_path`.
todos:
  - id: db-api-refactor
    content: Перевести API хранения на project_id/project_name без обязательного project_path
    status: completed
  - id: main-window-flow
    content: Переключить потоки создания/открытия проекта в main_window.py на DB-only
    status: completed
  - id: dialogs-cleanup
    content: Упростить Create/Open Project диалоги, убрать выбор и проверки папок
    status: completed
  - id: config-cleanup
    content: Почистить неактуальные константы и предупреждения про папки
    status: completed
  - id: manual-smoke-check
    content: Проверить основные пользовательские сценарии без каталога projects
    status: completed
  - id: todo-1777230979053-m8ijmrilm
    content: Убрать сохранение папок с файлами, вся работа с файлами должна идти из бд, не должно создаваться несколько записей в projects для одного и того же проекта
    status: completed
isProject: false
---

# Переход на DB-only без папки projects

## Что меняем
- Переводим проектный контур с `project_path` на `project_id`/`project_name` как единственные идентификаторы.
- Убираем валидации и UX, связанные с существованием папок на диске.
- Сохраняем файл `db_storage.dat` как единственное персистентное хранилище.

## Точки изменения
- [main_window.py](/Users/anikitin/PycharmProjects/Avellon_tech-main_latest/main_window.py)
  - Упростить запуск последнего проекта: не проверять `os.path.isdir(project_path)`, открывать по `project_id`.
  - Переписать `run_borehole_menu(...)` и `BoreholeMenuWindowWidget(...)` на работу по `project_id` (+ отображение имени проекта), без `get_project_by_path(...)`.
  - Убрать сценарии «Открыть проект по папке» и связанные предупреждения про нерегистрированную папку.
  - Пересобрать `CreateProjectDialog`: создание проекта без `DirPathEdit`, без `os.mkdir`, только `db.create_project(name)`.
  - В `OpenProjectDialog` отображать/выбирать проекты без требования `project_path`.

- [db_storage.py](/Users/anikitin/PycharmProjects/Avellon_tech-main_latest/db_storage.py)
  - Ввести DB-only API:
    - `create_project(name)` (без path)
    - `get_project(project_id)`
    - `list_projects()` (без зависимости от `project_path`)
  - Для совместимости сделать мягкую миграцию схемы:
    - оставить старый столбец `project_path` технически допустимым,
    - но больше не использовать его в новой логике,
    - убрать уникальность логики по пути на уровне Python-кода.

- [config.py](/Users/anikitin/PycharmProjects/Avellon_tech-main_latest/config.py)
  - Удалить/не использовать константы и тексты, завязанные на выбор/проверку папки проекта (`DEFAULT_PROJECT_FOLDER`, сообщения про папку проекта и т.д.), где они больше не нужны.

## Последовательность работ
1. Сначала refactor слоя хранения (`db_storage.py`) и добавить методы доступа по `project_id`.
2. Затем переключить `main_window.py` и диалоги на новые DB-only методы.
3. Удалить остаточные проверки/ветки, требующие файловой папки проекта.
4. Пройтись по предупреждениям/текстам в `config.py` и оставить только релевантные DB-only сообщения.
5. Проверить, что сценарии «создать проект», «открыть последний», «открыть из списка» работают без каталога `projects`.

## Риски и как их закрываем
- Риск: в старой БД проекты могли создаваться с ожиданием `project_path`.
  - Решение: совместимый слой в `db_storage.py` (чтение старых записей, но новая запись/поиск без path-зависимости).
- Риск: UI-части графиков используют путь для отображаемого имени.
  - Решение: в виджетах использовать `project_name` из БД как имя скважины/окна.
