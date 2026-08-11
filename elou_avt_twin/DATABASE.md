# База данных ЭЛОУ-АВТ Digital Twin

## 1. Обзор

Хранение данных реализовано на **SQLite** в одном файле:

```
elou_avt_twin/sessions.db
```

Все четыре хранилища приложения открывают собственные соединения к этому
файлу (WAL позволяет одновременные чтения и запись из нескольких
соединений):

| Модуль | Файл | Назначение |
|---|---|---|
| Авторизация (RBAC) | `auth/store.py` | роли, права, пользователи |
| Тренировки и симуляция | `persistence/session_store.py` | сессии, действия, снапшоты, аварии, ошибки, ИИ-классификация |
| LMS (обучение, кабинеты) | `lms/store.py` | курсы, модули, группы, компетенции, прогресс, уведомления |
| LMS (авторство и контроль) | `lms/content_store.py` | уроки, тесты, задания, сценарии, оценки, журналы |

Режимы SQLite, общие для всех хранилищ:

- `PRAGMA journal_mode=WAL` — журнал с записью-аппендом (лучше конкурентность);
- `PRAGMA busy_timeout=5000` — ожидание блокировки до 5 с;
- `PRAGMA foreign_keys=ON` — проверка внешних ключей.

Схемы P&ID хранятся **не в БД**, а в JSON-файлах `schemes/*.json`
(см. раздел 8).

Всего пользовательских таблиц: **30** (+ служебная `sqlite_sequence`).

---

## 2. Авторизация (RBAC) — `auth/store.py`

Авторизация всегда выводится из прав: эффективный набор прав пользователя —
объединение прав всех его ролей.

### `roles` — роли
| Колонка | Тип | Описание |
|---|---|---|
| `code` | TEXT PK | Код роли (`administrator`, `instructor`, `operator`) |
| `name` | TEXT NOT NULL | Название |
| `description` | TEXT DEFAULT '' | Описание |

### `permissions` — справочник прав
| Колонка | Тип | Описание |
|---|---|---|
| `code` | TEXT PK | Код права (`view_scheme`, `send_commands`, …) |
| `description` | TEXT DEFAULT '' | Описание |

### `role_permissions` — связь «роль → право» (M:N)
| Колонка | Тип | Описание |
|---|---|---|
| `role_code` | TEXT, FK → `roles.code` ON DELETE CASCADE | Роль |
| `permission_code` | TEXT, FK → `permissions.code` ON DELETE CASCADE | Право |
| — | PK (`role_code`, `permission_code`) | — |

### `users` — пользователи
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | Идентификатор |
| `username` | TEXT NOT NULL UNIQUE | Логин |
| `password_hash` | TEXT NOT NULL | Хэш пароля |
| `full_name` | TEXT DEFAULT '' | ФИО |
| `is_active` | INTEGER DEFAULT 1 | Активен (0/1) |
| `created_at` | REAL NOT NULL | Время создания (unix) |

### `user_roles` — связь «пользователь → роль» (M:N)
| Колонка | Тип | Описание |
|---|---|---|
| `user_id` | INTEGER, FK → `users.id` ON DELETE CASCADE | Пользователь |
| `role_code` | TEXT, FK → `roles.code` ON DELETE CASCADE | Роль |
| — | PK (`user_id`, `role_code`) | — |

Демо-учётные записи (пароль = логин): `admin`, `instructor`, `operator`.

---

## 3. Тренировки и симуляция — `persistence/session_store.py`

Хранилище — **event-sourced**: события только добавляются (append-only), по
ним можно полностью восстановить сессию и выгрузить корпус для офлайн-анализа
ИИ.

### `sessions` — сессии оператора
| Колонка | Тип | Описание |
|---|---|---|
| `id` | TEXT PK | UUID сессии |
| `scenario_id` | TEXT NOT NULL | Идентификатор сценария |
| `operator_id` | TEXT NOT NULL | Оператор (username) |
| `status` | TEXT DEFAULT 'CREATED' | Статус (CREATED → RUNNING → … → COMPLETED) |
| `sim_start` | REAL DEFAULT 0.0 | Старт симуляционного времени, с |
| `sim_end` | REAL | Конец симуляционного времени, с |
| `wall_start` | REAL NOT NULL | Старт реального времени (unix) |
| `wall_end` | REAL | Конец реального времени |
| `scheme_version` | TEXT | Версия P&ID-схемы |
| `performance_score` | REAL | Итоговый балл |
| `qualification` | TEXT | Присвоенная квалификация |
| `ai_verdict` | TEXT | Вердикт ИИ (JSON) |
| `created_at` | REAL NOT NULL | Время создания |

### `actions` — журнал действий (append-only)
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `session_id` | TEXT, FK → `sessions.id` | Сессия |
| `seq` | INTEGER NOT NULL | Порядковый номер (в сессии) |
| `sim_time` | REAL NOT NULL | Момент симуляции, с |
| `wall_time` | REAL | Реальное время |
| `operator_id` | TEXT NOT NULL | Кто действовал |
| `equipment_id` | TEXT NOT NULL | Объект |
| `node_type` | TEXT | Тип узла (pump, valve, …) |
| `action_type` | TEXT NOT NULL | Тип действия (TURN_ON, SET_PARAM, …) |
| `old_value` | TEXT | Прежнее значение (JSON) |
| `new_value` | TEXT | Новое значение (JSON) |
| `source` | TEXT DEFAULT 'operator_panel' | Источник действия |
| `accepted` | INTEGER DEFAULT 1 | Принято системой (0/1) |
| `reject_reason` | TEXT | Причина отклонения |
| — | UNIQUE (`session_id`, `seq`) | — |

### `state_snapshots` — срезы состояния процесса
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `session_id` | TEXT, FK → `sessions.id` | Сессия |
| `seq` | INTEGER NOT NULL | Порядковый номер |
| `sim_time` | REAL NOT NULL | Момент симуляции |
| `wall_time` | REAL | Реальное время |
| `reason` | TEXT DEFAULT 'step' | Причина снимка (step/action/…) |
| `action_id` | INTEGER, FK → `actions.id` | Связанное действие (если есть) |
| `pressure` | TEXT | Давления (JSON) |
| `temperature` | TEXT | Температуры (JSON) |
| `levels` | TEXT | Уровни (JSON) |
| `flows` | TEXT | Расходы (JSON) |
| `pump_states` | TEXT | Состояния насосов (JSON) |
| `valve_positions` | TEXT | Положения клапанов (JSON) |
| `equipment_states` | TEXT | Состояния оборудования (JSON) |
| `controller_states` | TEXT | Состояния регуляторов (JSON) |
| `active_alarms` | TEXT | Активные аварии (JSON) |
| `active_failures` | TEXT | Активные отказы (JSON) |
| — | UNIQUE (`session_id`, `seq`) | — |

### `alarms` — жизненный цикл аварии (raise/ack/clear)
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `session_id` | TEXT, FK → `sessions.id` | Сессия |
| `alarm_id` | TEXT NOT NULL | Идентификатор аварии |
| `parameter` | TEXT | Параметр (тег) |
| `severity` | TEXT | Приоритет (CRITICAL/WARNING/…) |
| `actual_value` | REAL | Значение при срабатывании |
| `threshold` | REAL | Порог |
| `description` | TEXT | Описание |
| `raised_at` | REAL NOT NULL | Время срабатывания |
| `acked_at` | REAL | Время квитирования |
| `acked_by` | TEXT | Кто квитировал |
| `cleared_at` | REAL | Время снятия |
| — | UNIQUE (`session_id`, `alarm_id`, `raised_at`) | — |

### `error_events` — выявленные ошибки + слоты ИИ-классификации
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `session_id` | TEXT, FK → `sessions.id` | Сессия |
| `sim_time` | REAL NOT NULL | Момент симуляции |
| `action_id` | INTEGER, FK → `actions.id` | Связанное действие |
| `rule_error_type` | TEXT NOT NULL | Тип ошибки по правилам |
| `severity` | TEXT | Серьёзность |
| `expected_action` | TEXT | Ожидавшееся действие |
| `cause` | TEXT | Причина |
| `consequence` | TEXT | Последствие |
| `context_snapshot_id` | INTEGER, FK → `state_snapshots.id` | Снимок-контекст |
| `ai_class` | TEXT | Класс по ИИ |
| `ai_confidence` | REAL | Уверенность ИИ |
| `ai_reasoning` | TEXT | Обоснование ИИ |
| `ai_status` | TEXT DEFAULT 'pending' | Статус классификации |

### `expected_actions` — эталонные действия сценария (ground truth)
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `scenario_id` | TEXT NOT NULL | Сценарий |
| `equipment_id` | TEXT NOT NULL | Объект |
| `action_type` | TEXT NOT NULL | Тип действия |
| `value` | TEXT | Значение |
| `deadline_t` | REAL | Срок выполнения, с |
| `description` | TEXT | Описание |
| `consequence` | TEXT | Последствие |
| `weight` | REAL DEFAULT 1.0 | Вес в оценке |
| — | UNIQUE (`scenario_id`, `equipment_id`, `action_type`) | — |

### `ai_classifications` — аудит каждого вызова ИИ
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `session_id` | TEXT, FK → `sessions.id` | Сессия |
| `error_event_id` | INTEGER, FK → `error_events.id` | Событие ошибки |
| `model` | TEXT NOT NULL | Модель ИИ |
| `prompt_version` | TEXT | Версия промпта |
| `input_payload` | TEXT NOT NULL | Входные данные (JSON) |
| `predicted_class` | TEXT NOT NULL | Предсказанный класс |
| `confidence` | REAL | Уверенность |
| `reasoning` | TEXT | Рассуждение |
| `human_correction` | TEXT | Исправление экспертом |
| `human_corrected` | INTEGER DEFAULT 0 | Исправлено человеком (0/1) |
| `latency_ms` | REAL | Задержка вызова |
| `created_at` | REAL NOT NULL | Время вызова |

---

## 4. LMS (кабинеты и обучение) — `lms/store.py`

### `lms_groups` — учебные группы
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `name` | TEXT NOT NULL | Название |
| `description` | TEXT DEFAULT '' | Описание |
| `course_id` | INTEGER | Привязанный курс |
| `instructor_id` | INTEGER | Инструктор |
| `created_at` | REAL NOT NULL | — |

### `lms_group_members` — участники группы (M:N)
| Колонка | Тип | Описание |
|---|---|---|
| `group_id` | INTEGER, FK → `lms_groups.id` ON DELETE CASCADE | Группа |
| `user_id` | INTEGER, FK → `users.id` ON DELETE CASCADE | Пользователь |
| — | PK (`group_id`, `user_id`) | — |

### `lms_courses` — курсы
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `title` | TEXT NOT NULL | Название |
| `description` | TEXT DEFAULT '' | Описание |
| `status` | TEXT DEFAULT 'DRAFT' | Статус (см. §7) |
| `created_at` | REAL NOT NULL | — |

### `lms_course_modules` — модули курса
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `course_id` | INTEGER, FK → `lms_courses.id` ON DELETE CASCADE | Курс |
| `kind` | TEXT NOT NULL | Тип модуля (theory/practice/exam) |
| `title` | TEXT NOT NULL | Название |
| `description` | TEXT DEFAULT '' | Описание |
| `seq` | INTEGER DEFAULT 0 | Порядок в курсе |
| `content` | TEXT DEFAULT '' | Текст теории |
| `scenario_id` | TEXT | Сценарий (для practice/exam) |
| `practice_task_id` | INTEGER | Задание из библиотеки |
| `published` | INTEGER | Флаг «опубликован» (добавлен content_store) |

### `lms_competencies` — справочник компетенций
| Колонка | Тип | Описание |
|---|---|---|
| `code` | TEXT PK | Код компетенции |
| `title` | TEXT NOT NULL | Название |
| `description` | TEXT DEFAULT '' | Описание |

### `lms_user_competencies` — уровни компетенций пользователя (M:N)
| Колонка | Тип | Описание |
|---|---|---|
| `user_id` | INTEGER, FK → `users.id` ON DELETE CASCADE | Пользователь |
| `competency_code` | TEXT, FK → `lms_competencies.code` ON DELETE CASCADE | Компетенция |
| `level_percent` | REAL DEFAULT 0 | Уровень, % |
| `updated_at` | REAL NOT NULL | — |
| — | PK (`user_id`, `competency_code`) | — |

### `lms_practice_tasks` — библиотека практических заданий
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `title` | TEXT NOT NULL | Название |
| `description` | TEXT DEFAULT '' | Описание |
| `scenario_id` | TEXT NOT NULL | Сценарий |
| `category` | TEXT DEFAULT 'practice' | Категория (practice/exam/random) |
| `difficulty` | TEXT DEFAULT 'MIDDLE' | Сложность (EASY/MIDDLE/HARD) |
| `duration_min` | INTEGER DEFAULT 10 | Длительность, мин |
| `required_competencies` | TEXT DEFAULT '[]' | Компетенции (JSON-список) |
| `is_random` | INTEGER DEFAULT 0 | Случайный выбор (0/1) |
| `enabled` | INTEGER DEFAULT 1 | Включено (0/1) |

### `lms_user_progress` — прогресс по модулям
| Колонка | Тип | Описание |
|---|---|---|
| `user_id` | INTEGER, FK → `users.id` ON DELETE CASCADE | Пользователь |
| `module_id` | INTEGER, FK → `lms_course_modules.id` ON DELETE CASCADE | Модуль |
| `status` | TEXT DEFAULT 'NOT_STARTED' | Статус (см. §7) |
| `score` | REAL | Оценка |
| `attempts` | INTEGER DEFAULT 0 | Попыток |
| `completed_at` | REAL | Время завершения |
| `last_practice_session_id` | TEXT | Последняя практическая сессия |
| — | PK (`user_id`, `module_id`) | — |

### `lms_notifications` — уведомления
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `user_id` | INTEGER, FK → `users.id` ON DELETE CASCADE | Получатель |
| `text` | TEXT NOT NULL | Текст |
| `kind` | TEXT DEFAULT 'info' | Тип (info/warning/…) |
| `is_read` | INTEGER DEFAULT 0 | Прочитано (0/1) |
| `created_at` | REAL NOT NULL | — |

### `lms_settings` — системные настройки (ключ/значение)
| Колонка | Тип | Описание |
|---|---|---|
| `key` | TEXT PK | Ключ |
| `value` | TEXT DEFAULT '' | Значение |

### `lms_system_log` — системный журнал администратора
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `timestamp` | REAL NOT NULL | Время |
| `level` | TEXT DEFAULT 'INFO' | Уровень (INFO/WARNING/ERROR) |
| `username` | TEXT DEFAULT '' | Пользователь |
| `message` | TEXT NOT NULL | Сообщение |
| `category` | TEXT DEFAULT 'system' | Категория |

---

## 5. LMS (авторство и контроль) — `lms/content_store.py`

Все «JSON-колонки» (списки и словари) хранятся как текст и десериализуются
на уровне приложения (см. §7).

### `lms_lessons` — теоретические уроки
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `module_id` | INTEGER, FK → `lms_course_modules.id` ON DELETE CASCADE | Модуль |
| `title` | TEXT NOT NULL | Заголовок |
| `seq` | INTEGER DEFAULT 0 | Порядок |
| `blocks` | TEXT DEFAULT '[]' | Блоки контента (JSON, см. §7) |
| `equipment_ids` | TEXT DEFAULT '[]' | Объекты схемы (JSON-список) |
| `competency_codes` | TEXT DEFAULT '[]' | Компетенции (JSON-список) |
| `created_at` | REAL NOT NULL | — |

### `lms_tests` — конфигурация теста
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `module_id` | INTEGER, FK → `lms_course_modules.id` ON DELETE CASCADE | Модуль |
| `title` | TEXT DEFAULT 'Контроль знаний' | Название |
| `passing_score` | REAL DEFAULT 70 | Проходной балл |
| `attempts` | INTEGER DEFAULT 0 | Лимит попыток (0 — без лимита) |
| `retry_required` | INTEGER DEFAULT 0 | Обязательный повтор (0/1) |
| `shuffle` | INTEGER DEFAULT 0 | Перемешивать вопросы (0/1) |
| `competency_codes` | TEXT DEFAULT '[]' | Компетенции (JSON) |
| `created_at` | REAL NOT NULL | — |

### `lms_questions` — вопросы теста
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `test_id` | INTEGER, FK → `lms_tests.id` ON DELETE CASCADE | Тест |
| `kind` | TEXT NOT NULL | Тип (single/multi/match/sequence/object) |
| `title` | TEXT NOT NULL | Формулировка |
| `text` | TEXT DEFAULT '' | Текст |
| `seq` | INTEGER DEFAULT 0 | Порядок |
| `options` | TEXT DEFAULT '[]' | Варианты (JSON, см. §7) |
| `answer` | TEXT | Правильный ответ (JSON) |
| `max_score` | REAL DEFAULT 1 | Макс. балл |
| `penalty` | REAL DEFAULT 0 | Штраф |
| `required` | INTEGER DEFAULT 1 | Обязательный (0/1) |
| `hint` | TEXT DEFAULT '' | Подсказка |

### `lms_training_tasks` — спецификация практического задания
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `module_id` | INTEGER, FK → `lms_course_modules.id` ON DELETE CASCADE | Модуль |
| `title` | TEXT NOT NULL | Название |
| `goal` | TEXT DEFAULT '' | Цель |
| `scenario_id` | TEXT DEFAULT '' | Сценарий |
| `duration_min` | INTEGER DEFAULT 10 | Длительность, мин |
| `initial_state` | TEXT DEFAULT '{}' | Начальное состояние (JSON-объект) |
| `target_state` | TEXT DEFAULT '[]' | Целевое состояние (JSON, TaskCondition[]) |
| `restrictions` | TEXT DEFAULT '[]' | Ограничения (JSON, RestrictionRule[]) |
| `criteria` | TEXT DEFAULT '[]' | Критерии оценки (JSON, Criterion[]) |
| `expected_actions` | TEXT DEFAULT '[]' | Ожидаемые действия (JSON, ExpectedAction[]) |
| `critical_errors` | TEXT DEFAULT '[]' | Критические ошибки (JSON) |
| `competency_codes` | TEXT DEFAULT '[]' | Компетенции (JSON) |
| `equipment_ids` | TEXT DEFAULT '[]' | Объекты (JSON) |
| `enabled` | INTEGER DEFAULT 1 | Включено (0/1) |
| `created_at` | REAL NOT NULL | — |

### `lms_scenarios` — динамический сценарий и его статус
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `module_id` | INTEGER, FK → `lms_course_modules.id` ON DELETE CASCADE | Модуль |
| `title` | TEXT NOT NULL | Название |
| `description` | TEXT DEFAULT '' | Описание |
| `goal` | TEXT DEFAULT '' | Цель |
| `status` | TEXT DEFAULT 'DRAFT' | Статус (см. §7) |
| `initial_state` | TEXT DEFAULT '{}' | Начальное состояние (JSON-объект) |
| `events` | TEXT DEFAULT '[]' | Таймлайн событий (JSON, ScenarioEventDef[]) |
| `expected_actions` | TEXT DEFAULT '[]' | Ожидаемые действия (JSON) |
| `success_criteria` | TEXT DEFAULT '[]' | Критерии успеха (JSON) |
| `critical_errors` | TEXT DEFAULT '[]' | Критические ошибки (JSON) |
| `target_state` | TEXT DEFAULT '[]' | Цель как результат (JSON, TaskCondition[]) |
| `final_state` | TEXT DEFAULT '{}' | Финальное состояние (JSON-объект) |
| `competency_codes` | TEXT DEFAULT '[]' | Компетенции (JSON) |
| `equipment_ids` | TEXT DEFAULT '[]' | Объекты (JSON) |
| `duration_min` | INTEGER DEFAULT 10 | Длительность, мин |
| `is_exam` | INTEGER DEFAULT 0 | Экзаменационный (0/1) |
| `created_at` | REAL NOT NULL | — |

### `lms_assessments` — результаты оценок
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `user_id` | INTEGER, FK → `users.id` ON DELETE CASCADE | Пользователь |
| `module_id` | INTEGER, FK → `lms_course_modules.id` ON DELETE CASCADE | Модуль |
| `kind` | TEXT NOT NULL | Тип (test/practice/exam) |
| `test_id` | INTEGER | Тест |
| `task_id` | INTEGER | Задание |
| `scenario_id` | TEXT | Сценарий |
| `score` | REAL DEFAULT 0 | Набрано баллов |
| `max_score` | REAL DEFAULT 100 | Макс. баллов |
| `passed` | INTEGER DEFAULT 0 | Сдано (0/1) |
| `criteria_scores` | TEXT DEFAULT '{}' | Баллы по критериям (JSON-объект) |
| `errors_count` | INTEGER DEFAULT 0 | Кол-во ошибок |
| `critical_errors_count` | INTEGER DEFAULT 0 | Кол-во критических ошибок |
| `duration_s` | REAL DEFAULT 0 | Длительность, с |
| `answers` | TEXT | Ответы (JSON) |
| `feedback_good` | TEXT DEFAULT '[]' | Позитивная обратная связь (JSON) |
| `feedback_bad` | TEXT DEFAULT '[]' | Замечания (JSON) |
| `session_id` | TEXT | Сессия симуляции |
| `started_at` | REAL NOT NULL | Начало |
| `finished_at` | REAL NOT NULL | Завершение |
| `created_at` | REAL NOT NULL | — |

### `lms_action_log` — журнал действий оператора
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `timestamp` | REAL NOT NULL | Время |
| `user_id` | INTEGER | Пользователь |
| `username` | TEXT DEFAULT '' | Логин |
| `object_id` | TEXT DEFAULT '' | Объект |
| `object_name` | TEXT DEFAULT '' | Название объекта |
| `action` | TEXT DEFAULT '' | Действие |
| `old_state` | TEXT DEFAULT '{}' | Прежнее состояние (JSON) |
| `new_state` | TEXT DEFAULT '{}' | Новое состояние (JSON) |
| `source` | TEXT DEFAULT 'operator_panel' | Источник |
| `session_id` | TEXT | Сессия |
| `module_id` | INTEGER | Модуль |

### `lms_scada_log` — журнал взаимодействия с мнемосхемой (SCADA)
| Колонка | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | — |
| `timestamp` | REAL NOT NULL | Время |
| `user_id` | INTEGER | Пользователь |
| `username` | TEXT DEFAULT '' | Логин |
| `event_type` | TEXT DEFAULT 'click' | Тип события (см. §7) |
| `object_id` | TEXT DEFAULT '' | Объект |
| `object_name` | TEXT DEFAULT '' | Название объекта |
| `duration_s` | REAL | Длительность (для open/close, входа/выхода) |
| `session_id` | TEXT | Сессия |
| `module_id` | INTEGER | Модуль |

---

## 6. Связи между таблицами (краткая ER-схема)

```
roles ──< role_permissions >── permissions
users ──< user_roles >── roles

users ──< lms_user_roles ── (в user_roles)
users ──< lms_group_members >── lms_groups
users ──< lms_user_competencies >── lms_competencies
users ──< lms_notifications
users ──< lms_user_progress >── lms_course_modules
users ──< lms_assessments >── lms_course_modules
users ──< lms_assessments ──> lms_tests / lms_training_tasks

lms_courses ──< lms_course_modules
lms_course_modules ──< lms_lessons
lms_course_modules ──< lms_tests ──< lms_questions
lms_course_modules ──< lms_training_tasks
lms_course_modules ──< lms_scenarios

sessions ──< actions
sessions ──< state_snapshots
sessions ──< alarms
sessions ──< error_events
sessions ──< ai_classifications
error_events ──< ai_classifications
actions ──< state_snapshots.action_id
```

Примечание: `lms_action_log` и `lms_scada_log` — append-only журналы; их
`user_id`/`session_id`/`module_id` не имеют внешне-ключевых ограничений
(значения могут ссылаться на уже удалённые записи).

---

## 7. Перечисления и форматы JSON-полей

### Перечисления

**Роли** — `roles.code`: `administrator`, `instructor`, `operator`, `field_operator`

**Статус курса** — `lms_courses.status`: `DRAFT`, `ACTIVE`, `ARCHIVED`

**Тип модуля** — `lms_course_modules.kind`: `theory`, `practice`, `exam`

**Статус модуля (прогресс)** — `lms_user_progress.status`:
`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`

**Сложность** — `lms_practice_tasks.difficulty`: `EASY`, `MIDDLE`, `HARD`

**Категория задания** — `lms_practice_tasks.category`: `practice`, `exam`, `random`

**Статус сценария** — `lms_scenarios.status`:
`DRAFT`, `REVIEW`, `PUBLISHED`, `ARCHIVED`

**Тип оценки** — `lms_assessments.kind`: `test`, `practice`, `exam`

**Тип блока урока** — `lms_lessons.blocks[].kind`:
`text`, `image`, `scheme`, `video`, `equipment_card`, `scheme_highlight`, `interactive_scheme`

**Тип вопроса** — `lms_questions.kind`: `single`, `multi`, `match`, `sequence`, `object`

**Тип события SCADA** — `lms_scada_log.event_type`:
`click`, `inspector_open`, `inspector_close`, `page_enter`, `page_exit`

**Тип события сценария** — `lms_scenarios.events[].event_type`:
`fault`, `param`, `state`, `alarm`, `mode`
(маппинг на движок: `fault → INJECT_FAILURE`, `param → SET_PARAM`,
`state → SET_STATE`, `alarm → RAISE_ALARM`, `mode → SET_PARAM`)

**Статус сессии** — `sessions.status`: `CREATED`, далее зависит от сценария
(обычно `RUNNING`/`COMPLETED`/`ABORTED`).

**Статус ИИ-классификации** — `error_events.ai_status`: `pending` и далее
(напр. `classified`, `skipped`).

### JSON-форматы

- `lms_lessons.blocks` — `[LessonBlock{kind, title, content, url, node_id}]`
- `lms_questions.options` — `[{label, correct, ...}]`
- `lms_questions.answer` — ответ в зависимости от `kind`
- `lms_training_tasks.target_state` — `[TaskCondition{object_id, attribute, relation, value, value2}]`, relation: `==`, `!=`, `>=`, `<=`, `>`, `<`
- `lms_training_tasks.restrictions` / `critical_errors` — `[RestrictionRule{action_type, object_id, relation, value, severity, message}]`
- `lms_training_tasks.criteria` — `[Criterion{key, title, weight}]`
- `lms_training_tasks.expected_actions` — `[ExpectedAction{seq, object_id, action_type, value, description, deadline_t, weight}]`
- `lms_scenarios.initial_state` / `final_state` — `{ "<id>_running": bool, "<id>_position": %, "<id>_fuel_flow": ... }`
- `lms_scenarios.events` — `[ScenarioEventDef{time, event_type, object_id, param, value, severity, message}]`
- `lms_scenarios.success_criteria` — `[Criterion]`
- `lms_scenarios.target_state` — `[TaskCondition]` (цель как результат, напр. `{object_id: "col_4", attribute: "level_m", relation: ">=", value: 2.5}`); участвует в оценке практики вместе с `lms_training_tasks.target_state`
- `lms_assessments.answers` / `criteria_scores` / `feedback_good` / `feedback_bad` — JSON
- `state_snapshots.*` — JSON-словари телеметрии
- `actions.old_value` / `new_value` — JSON

---

## 8. Схемы P&ID (вне БД)

Схемы технологических линий хранятся в `elou_avt_twin/schemes/*.json`:

```json
{
  "id": "default",
  "name": "Схема «default»",
  "nodes": [{"id": "pump_H1", "type": "pump", "name": "Н-1", "x": ..., "y": ..., "params": {...}}],
  "edges": [{"id": "...", "source": "...", "target": "...",
              "source_port": "out", "target_port": "in", "kind": "process"}]
}
```

Текущая активная схема задаётся глобальной переменной `scheme_store` в
`api_server.py`; `GET /scheme` возвращает её, `POST /scheme` сохраняет в файл
`schemes/<id>.json` и пересобирает движок.

---

## 9. Резервное копирование и восстановление

- Файл БД: `elou_avt_twin/sessions.db` (+ файлы WAL `sessions.db-wal`, `-shm`
  при работающем приложении).
- Для корректной копии БД нужно останавливать приложение либо использовать
  `sqlite3 .backup` / `VACUUM INTO` (безопасно при работающем WAL).
- Схемы P&ID: каталог `elou_avt_twin/schemes/`.
