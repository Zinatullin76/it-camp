# ЭЛОУ-АВТ Digital Twin — Integrated MVP

## Состав
- `elou_avt_twin/` — Python Digital Twin + FastAPI REST/WebSocket backend.
- `elou_avt_web/` — React HMI (Vite + React Flow): технологическая схема, телеметрия, управление.
- `elou_avt_twin/run_backend.bat` — запуск backend отдельно.

## Быстрый запуск
Требуется Windows 10/11, Python 3.11+ и Node.js 18+ (npm).

### Установка с нуля (после клонирования)
```bat
REM 1. Установка Python-зависимостей бэкенда
cd elou_avt_twin
pip install -r requirements.txt
cd ..

REM 2. Установка зависимостей фронтенда
cd elou_avt_web
npm install
cd ..

Обрати внимание: `node_modules/`, `.venv/` и `dist/`
не хранятся в git, поэтому после клонирования **обязательно** выполнить
`pip install -r requirements.txt` и `npm install` (это делает `START_ALL.bat`).

### Запуск
1. Backend будет доступен на `http://127.0.0.1:8000/docs`.
2. Web-интерфейс откроется на `http://localhost:5173`.
3. Для демонстрации аварии используй инжекцию отказа через UI или `POST /failure/{equipment_id}`.

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

## Важно
Физическое ядро является MVP-моделью. Для промышленного применения необходима дальнейшая валидация термодинамики и MESH-решателя.
