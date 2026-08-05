# ЭЛОУ-АВТ Digital Twin — Integrated MVP

## Состав
- `elou_avt_twin/` — Python Digital Twin + FastAPI REST/WebSocket backend.
- `elou_avt_web/` — React HMI (Vite + React Flow): технологическая схема, телеметрия, управление.
- `START_ALL.bat` — запуск backend и web-фронтенда.
- `elou_avt_twin/run_backend.bat` — запуск backend отдельно.

## Быстрый запуск
Требуется Windows 10/11, Python 3.11+ и Node.js 18+.

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
