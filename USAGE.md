# HelperCaller - Система подсказок для продаж

Единый пайплайн для генерации подсказок оператору в реальном времени.

## Функциональность

- **Распознавание речи** (Whisper)
- **Определение ролей** говорящих (ИИ + эвристика)
- **Генерация подсказок** в реальном времени (~1.5с)
- **Режим файла** и **режим реального времени**

## Установка зависимостей

```bash
pip install torch openai-whisper openai pyaudio
```

## Быстрый запуск

### 1. Обработка аудио файла

```bash
# Простой запуск
python main.py audio_file.mp3

# Полный запуск с настройками
python helper_caller_pipeline.py --input audio_file.wav \
  --company "ВестКолл" \
  --goal "привлечь клиента" \
  --whisper-model base
```

### 2. Режим реального времени

```bash
# Простой запуск
python main.py --realtime

# Полный запуск
python helper_caller_pipeline.py --realtime \
  --whisper-model tiny \
  --company "Ваша компания"
```

### 3. Прямой запуск модуля реального времени

```bash
python realtime_assistant.py
```

## Файловая структура

```
HelperCaller/
├── main.py                     # Упрощенный интерфейс
├── helper_caller_pipeline.py   # Основной пайплайн
├── realtime_assistant.py       # Модуль реального времени
├── 01_prepare_audio.py         # Подготовка аудио
├── 02_transcribe.py            # Транскрипция
├── 03_label_roles.py           # Определение ролей
├── 04_coach_replies.py         # Генерация подсказок
└── run_pipeline_slices.py      # Обработка по частям
```

## Оптимизации для скорости

1. **Модель Whisper**: `tiny` или `base` для реального времени
2. **OpenAI модель**: `gpt-4o-mini` (~1.5с на генерацию)
3. **Ограничение контекста**: только последние 6 реплик
4. **Короткие промпты**: до 300 токенов
5. **Строгие таймауты**: 8 сек для API

## Параметры командной строки

### helper_caller_pipeline.py

```bash
python helper_caller_pipeline.py [ОПЦИИ]

Основные:
  --input PATH              Аудио файл для обработки
  --output PATH             Папка для результатов
  --realtime                Режим реального времени

Модели:
  --whisper-model MODEL     tiny|base|small|medium|large-v3 (default: base)
  --openai-model MODEL      gpt-4o-mini|gpt-4o (default: gpt-4o-mini)
  --language LANG           Язык распознавания (default: ru)

Компания:
  --company NAME            Название компании (default: ВестКолл)
  --goal TEXT               Цель продаж
  --tone TEXT               Тональность общения
  --company-info TEXT       Информация о компании
  --constraints TEXT        Ограничения
```

## Примеры использования

### Обработка звонка

```bash
# Базовая обработка
python main.py recordings/call_001.wav

# С настройками компании
python helper_caller_pipeline.py \
  --input recordings/call_001.wav \
  --company "TechSoft" \
  --goal "продать CRM систему" \
  --tone "технический, экспертный" \
  --company-info "CRM решения для малого бизнеса"
```

### Реальное время

```bash
# Быстрый старт для демо
python main.py --realtime

# Настроенный для производства
python helper_caller_pipeline.py --realtime \
  --whisper-model tiny \
  --company "Ваша компания" \
  --goal "квалифицировать лиды"
```

## Форматы результатов

### Структура подсказок (JSON)

```json
{
  "сейчас": [
    "Активно слушайте клиента",
    "Задайте уточняющий вопрос"
  ],
  "скоро": [
    "Выясните бюджет",
    "Предложите демо"
  ],
  "позже": [
    "Назначьте встречу",
    "Отправьте коммерческое предложение"
  ],
  "возражения": [
    "Покажите понимание проблемы",
    "Приведите кейс похожего клиента"
  ]
}
```

### Файлы результатов

- `dialog.json` - История диалога с ролями
- `dialog.txt` - Текстовый формат диалога
- `suggestions.json` - Финальные подсказки
- `{имя_файла}_results/` - Папка со всеми результатами

## Производительность

### Время обработки

- **Транскрипция**: ~0.3с на сегмент (Whisper tiny)
- **Определение роли**: ~0.1с (эвристика + ИИ)
- **Генерация подсказок**: ~1.5с (gpt-4o-mini)
- **Общее время**: ~2с на сегмент

### Требования к ресурсам

- **CPU**: 2+ ядра для Whisper
- **RAM**: 2GB для модели tiny, 4GB для base
- **Интернет**: для OpenAI API (~1KB на запрос)

## Диагностика проблем

### Частые ошибки

1. **"Не найден пакет"** → `pip install torch openai-whisper openai`
2. **"Не найден API-ключ"** → Проверьте ключ в коде или переменной OPENAI_API_KEY
3. **"Ошибка аудио"** → Установите ffmpeg
4. **"Нет микрофона"** → Установите pyaudio, проверьте права доступа

### Проверка установки

```bash
# Проверка зависимостей
python -c "import torch, whisper, openai; print('OK')"

# Проверка ffmpeg
ffmpeg -version

# Проверка микрофона (для реального времени)
python -c "import pyaudio; print('Audio OK')"
```

## Интеграция в производство

### API режим (будущая функция)

```python
from helper_caller_pipeline import HelperCallerPipeline

pipeline = HelperCallerPipeline(
    whisper_model="base",
    openai_model="gpt-4o-mini"
)

# Обработка текста
suggestions = pipeline.process_text_realtime("Клиент: Мне нужна CRM система")
```

### Веб-интерфейс (будущая функция)

```bash
# Запуск веб-сервера
python web_interface.py --port 8080
```

## Лицензия и поддержка

Этот код создан для демонстрации возможностей ИИ в телефонных продажах.
Для производственного использования требуется дополнительная настройка безопасности.