# Smoke и регрессионные критерии

## Smoke-набор

- `tests/regression/test_smoke_regression.py::test_smoke_create_save_load_roundtrip`
  проверяет критичный DB-first флоу: создание проекта, сохранение структуры и повторную загрузку.
- `tests/regression/test_smoke_regression.py::test_smoke_graph_links_replace_old_values`
  подтверждает, что связи графов в БД перезаписываются корректно и не копят устаревшие записи.

## Критерии регресса

- Все `@pytest.mark.smoke` проходят стабильно на чистой временной БД.
- Интеграционные тесты `tests/integration/` не используют `storage.dat` и не зависят от локальных папок проекта.
- Проверяется целостность DB-first связей: `sections/steps/files` и `frequency_characteristics/wind_roses`.
- Для UI-флоу используются моки GUI-взаимодействий без запуска полного event loop.
