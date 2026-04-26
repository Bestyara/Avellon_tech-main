---
name: file-metadata-on-add
overview: Перенести сохранение информации о файлах из момента построения графиков на момент добавления файлов в шаг скважины и нажатия «Принять» в настройках скважины.
todos:
  - id: analyze-current-file-cache-flow
    content: "Уточнить текущий поток: где создаётся XYDataFrame, как именно он вызывает _save_to_db и upsert_file_data при построении графиков."
    status: pending
  - id: implement-borehole-save-files-to-db
    content: Добавить в Borehole (borehole_logic.py) метод save_files_to_db(), проходящий по всем DataFile и создающий XYDataFrame для каждого файла.
    status: completed
  - id: hook-save-files-on-accept
    content: Вставить вызов borehole.save_files_to_db() в BoreHoleDialog.accept_action (main_window.py) после корреляции данных и перед/рядом с сохранением структуры в БД.
    status: pending
  - id: regression-check-graphs
    content: Проверить, что построение всех типов графиков по-прежнему работает и использует данные из БД, если они есть.
    status: pending
isProject: false
---

## Цель

Сделать так, чтобы данные о файлах (контент, заголовки, статистики) попадали в таблицу `files` БД сразу после добавления файлов в шаги скважины (через диалог скважины), а не только при первом построении графика.

## Ключевые места в коде

- **UI/логика добавления файлов**: `BoreHoleDialog`, `SectionWidget`, `StepWidget`, `FileWidget` в файле `[main_window.py](main_window.py)`.
- **Модель скважины и шагов**: классы `Borehole`, `Section`, `Step`, `DataFile` в файле `[borehole_logic.py](borehole_logic.py)`.
- **Кэширование файлов в БД**: класс `XYDataFrame` и его методы `_load_from_db()` и `_save_to_db()` в файле `[graph_widget.py](graph_widget.py)`, использование `DbStorage.upsert_file_data(...)`.
- **Хранилище БД**: класс `DbStorage` и таблица `files` в файле `[db_storage.py](db_storage.py)`.

## План изменений

- **1. Проанализировать текущий поток сохранения файлов**
  - Проследить, как при построении графиков вызываются методы `Borehole.get_*_dataframe_dict()`, далее `Section`/`Step`/`DataFile.get_xy_dataframe()`, и внутри создаётся `XYDataFrame`, который в конструкторе читает CSV и вызывает `_save_to_db()`.
  - Убедиться, что `XYDataFrame._save_to_db()` уже формирует корректный payload и привязку к проекту/скважине по структуре путей (`<project>/<section>/<step>/<file>`), так что можно переиспользовать эту логику без дублирования.
- **2. Добавить метод сохранения файлов скважины в БД**
  - В классе `Borehole` в `[borehole_logic.py](borehole_logic.py)` добавить публичный метод, например `save_files_to_db(self)`, который:
    - Итерируется по всем `section` в `self.section_list`, всем `step` в `section.step_list` и всем `data_file` в `step.data_list`.
    - Для каждого существующего файла вызывает `XYDataFrame(data_file.path())`, полагаясь на уже существующий конструктор, который:
      - Либо загружает данные из БД (если уже есть),
      - Либо читает CSV и вызывает `_save_to_db()` с использованием `DbStorage.upsert_file_data(...)`.
    - Оборачивает создание `XYDataFrame` в `try/except`, чтобы любые проблемы с отдельными файлами не ломали общий сценарий сохранения (предупреждения об ошибочных файлах останутся на совести существующей логики `MessageBox`).
- **3. Вызывать сохранение файлов при принятии настроек скважины**
  - В методе `BoreHoleDialog.accept_action` в `[main_window.py](main_window.py)`, после:
    - `self.save_all_sections(self.borehole.up_path)` (копирование файлов в структуру каталогов),
    - `self.borehole.correlate_data()` (синхронизация файловой системы с объектной моделью `Borehole`/`Section`/`Step`/`DataFile`),
    - и до/вместе с существующим вызовом `self.borehole.save_to_db(db, borehole_id)` (сохранение структуры секций/шагов)
  - Вставить вызов `self.borehole.save_files_to_db()`, обёрнутый в `try/except`, чтобы ошибки при сохранении в таблицу `files` не мешали пользователю завершить диалог.
  - Сохранить семантику: структура секций/шагов продолжает храниться через `replace_borehole_structure`, а содержимое файлов — через `XYDataFrame`/`DbStorage`.
- **4. Оставить совместимость с текущей логикой построения графиков**
  - Не удалять и не менять текущий вызов `_save_to_db()` внутри конструктора `XYDataFrame` в `[graph_widget.py](graph_widget.py)`, так как:
    - Повторный вызов `upsert_file_data(...)` идемпотентен (обновление той же записи по `file_path`).
    - Это обеспечивает совместимость со старыми файлами/проектами, которые могли быть добавлены до внедрения новой логики.
  - Убедиться, что при построении графика данные теперь, как правило, будут загружаться из БД через `_load_from_db()`, а не перечитываться с диска.
- **5. Минимальное тестирование**
  - Создать/открыть проект, добавить секции, шаги и новые файлы через диалог скважины, затем нажать «Принять».
  - Построить любой график (например, осциллограмму), убедиться, что он строится как и прежде.
  - Опционально (для отладки) с помощью временного кода или стороннего инструмента проверить, что таблица `files` в `db_storage.dat` содержит записи для добавленных файлов уже сразу после «Принять», даже если графики ещё не строились.

## Краткая схема потока данных

```mermaid
flowchart LR
  uiAddFiles[UI: StepWidget.add_files_action] --> fsCopy[FS: FileWidget.copy_to / save_all]
  fsCopy --> boreholeCorrelate[Borehole.correlate_data]
  boreholeCorrelate --> boreholeSaveFiles[Borehole.save_files_to_db]
  boreholeSaveFiles --> xyDF[XYDataFrame(file)]
  xyDF --> dbFiles[DbStorage.upsert_file_data]
  dbFiles --> graphLoad[Построение графика (XYDataFrame._load_from_db)]
```



