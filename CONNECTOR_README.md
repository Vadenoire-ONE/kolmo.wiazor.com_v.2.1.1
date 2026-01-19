# DTKT System Connector

## Назначение

Standalone-программа для связи проектов DTKT:

- **rates_winners** — Python/FastAPI бэкенд (API курсов и победителей)
- **kolmo_analysis** — React/Plotly фронтенд (графический анализ)

## Быстрый старт

### 1. Проверка статуса

```powershell
python dtkt_connector.py status
```

### 2. Инициализация kolmo_analysis

```powershell
python dtkt_connector.py init-analysis
```

Создаёт готовый Vite + React + TypeScript проект в `../kolmo_analysis/` с:

- Интеграцией plotly.js-dist-min
- Прокси к API на порту 8000
- Компонентами для отображения данных KOLMO

### 3. Запуск обоих серверов

```powershell
python dtkt_connector.py start-all
```

- API: http://localhost:8000 (+ OpenAPI docs на /docs)
- UI: http://localhost:5173 (с прокси /api → API)

### 4. Запуск по отдельности

```powershell
# Только API
python dtkt_connector.py start-api

# Только UI (после npm install в kolmo_analysis)
python dtkt_connector.py start-ui
```

## Параметры

| Флаг | Описание |
|------|----------|
| `--api-port` | Порт API (по умолчанию 8000) |
| `--ui-port` | Порт UI (по умолчанию 5173) |
| `--force` | Перезаписать kolmo_analysis при init |

## Структура после init-analysis

```
kolmo.wiazor.com_v2.1.1/
├── rates_winners/          # Бэкенд (этот проект)
│   ├── src/kolmo/
│   ├── dtkt_connector.py   # ← Этот скрипт
│   └── ...
│
└── kolmo_analysis/         # Фронтенд (создаётся автоматически)
    ├── src/
    │   ├── App.tsx         # Главный компонент с Plotly
    │   ├── main.tsx
    │   └── index.css
    ├── package.json
    ├── vite.config.ts      # Прокси к API
    └── index.html
```

## API Endpoints (для фронтенда)

Фронтенд использует прокси, поэтому запросы идут на `/api/v1/...`:

```typescript
// В kolmo_analysis/src/App.tsx
const res = await fetch('/api/v1/winner/latest')
const data: WinnerResponse = await res.json()

// Доступные поля для Plotly:
// - data.date — дата (x-axis)
// - data.kolmo_deviation — отклонение инварианта
// - data.r_me4u, data.r_iou2, data.r_uome — курсы
// - data.relpath_me4u, relpath_iou2, relpath_uome — RelativePath
// - data.winner — победитель дня
// - data.kolmo_state — OK/WARN/CRITICAL
```

## Зависимости

### rates_winners (Python)

Уже установлены через `pip install -e ".[dev]"`

### kolmo_analysis (Node.js)

После `init-analysis`:

```powershell
cd ../kolmo_analysis
npm install
```

Пакеты:
- react, react-dom
- plotly.js-dist-min
- vite, typescript
- lucide-react (иконки)
