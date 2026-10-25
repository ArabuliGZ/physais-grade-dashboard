# PhysAIs — анализ оценок

Статическая интерактивная панель для исследования связи выполнения домашних заданий с учебными результатами.

Сайт: [stat.physais.ru](https://stat.physais.ru)

## Состав проекта

- `dist/` — готовый сайт;
- `generate_data.py` — подготовка обезличенных данных для панели;
- `analyze_historical.py` и `experiment_data.py` — аналитические расчёты;
- `qa.mjs` и `verify_experiment.py` — проверки данных и интерфейса;
- `deploy-vds.ps1` — публикация на VDS.

Исходная база с персональными данными хранится вне репозитория и не публикуется. В `dist/data.js` находятся только данные, подготовленные для публичной визуализации.

## Обновление

```powershell
python generate_data.py
node qa.mjs
python verify_experiment.py
.\deploy-vds.ps1
```

