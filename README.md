# ЭЛОУ-АВТ Digital Twin — Integrated MVP

## Состав
- `elou_avt_twin/` — Python Digital Twin + FastAPI REST/WebSocket backend.
- `elou_avt_web/` — React HMI (Vite + React Flow): технологическая схема, телеметрия, управление.
- `START_ALL.bat` — запуск backend и web-фронтенда.
- `elou_avt_twin/run_backend.bat` — запуск backend отдельно.

## Быстрый запуск
Требуется Windows 10/11, Python 3.11+ и Node.js 18+ (npm).

### Установка с нуля (после клонирования)
```bat
REM 1. Установка Python-зависимостей бэкенда
cd elou_avt_twin
py -3 -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
cd ..

REM 2. Установка зависимостей фронтенда
cd elou_avt_web
npm install
cd ..

REM 3. Запуск обоих сервисов
START_ALL.bat
```

Либо просто запусти `START_ALL.bat` — он сам создаст venv, поставит зависимости
и запустит backend + web. Обрати внимание: `node_modules/`, `.venv/` и `dist/`
не хранятся в git, поэтому после клонирования **обязательно** выполнить
`pip install -r requirements.txt` и `npm install` (это делает `START_ALL.bat`).

### Запуск
1. Запусти `START_ALL.bat`.
2. Backend будет доступен на `http://127.0.0.1:8000/docs`.
3. Web-интерфейс откроется на `http://localhost:5173`.
4. Для демонстрации аварии используй инжекцию отказа через UI или `POST /failure/{equipment_id}`.

## API
- `GET /health`
- `GET /state`
- `GET /alarms`
- `GET /events`
- `GET /score`
- `POST /input`
- `POST /action`
- `POST /scenario/start`
- `POST /scenario/reset`
- `POST /scenario/step`
- `POST /failure/{equipment_id}`
- `WS /ws/simulation`

## Демонстрационный сценарий
1. Запустить систему.
2. Показать технологическую схему (React Flow).
3. Инжектировать отказ насоса.
4. Показать изменение состояния и тревоги.
5. Запустить резервный насос через API/UI-интеграцию.
6. Показать восстановление процесса.

## Важно
Физическое ядро является MVP-моделью. Для промышленного применения необходима дальнейшая валидация термодинамики и MESH-решателя.
