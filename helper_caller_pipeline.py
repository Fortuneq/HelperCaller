#!/usr/bin/env python3
"""
HelperCaller - Единый пайплайн для генерации подсказок оператору в реальном времени
Объединяет: распознавание речи + определение ролей + генерацию подсказок

Для работы в реальном времени требуется:
- ffmpeg (для обработки аудио)
- openai (pip install openai)  
- whisper (pip install openai-whisper)
- torch (для Whisper)
"""

import argparse
import json
import os
import sys
import threading
import time
import queue
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess
import tempfile

# Импорты для компонентов пайплайна
try:
    import torch
    import whisper
except ImportError:
    raise SystemExit("Установите: pip install torch openai-whisper")

try:
    from openai import OpenAI
except ImportError:
    raise SystemExit("Установите: pip install openai")

# Конфигурация OpenAI
OPENAI_API_KEY = "***REMOVED***"

class HelperCallerPipeline:
    def __init__(self, 
                 whisper_model: str = "base",
                 openai_model: str = "gpt-4o-mini",
                 company: str = "ВестКолл",
                 goal: str = "привлечь клиента и продать услуги",
                 tone: str = "дружелюбный, экспертный",
                 company_info: str = "",
                 constraints: str = "",
                 language: str = "ru"):
        
        self.whisper_model = whisper_model
        self.openai_model = openai_model
        self.company = company
        self.goal = goal
        self.tone = tone
        self.company_info = company_info
        self.constraints = constraints
        self.language = language
        
        # Инициализация компонентов
        self._init_whisper()
        self._init_openai()
        
        # Состояние диалога
        self.dialog_history: List[Dict[str, Any]] = []
        self.current_suggestions: Dict[str, List[str]] = {}
        
        # Очереди для обработки в реальном времени
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()
        self.suggestions_queue = queue.Queue()
        
        # Флаги управления
        self.running = False
        
    def _init_whisper(self):
        """Инициализация модели Whisper"""
        print(f"Загружаю модель Whisper: {self.whisper_model}")
        self.whisper = whisper.load_model(self.whisper_model, device="cpu")
        torch.set_num_threads(4)  # Оптимизация для CPU
        
    def _init_openai(self):
        """Инициализация клиента OpenAI"""
        api_key = OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("Не найден API-ключ OpenAI")
        self.openai_client = OpenAI(api_key=api_key, timeout=10.0)
        
    def process_audio_chunk(self, audio_data: bytes) -> Optional[str]:
        """Обработка аудио чанка и извлечение текста"""
        try:
            # Сохранение во временный файл
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_path = tmp_file.name
            
            # Транскрипция
            result = self.whisper.transcribe(
                tmp_path, 
                language=self.language, 
                task="transcribe",
                verbose=False
            )
            
            # Очистка временного файла
            os.unlink(tmp_path)
            
            text = result.get("text", "").strip()
            return text if text else None
            
        except Exception as e:
            print(f"Ошибка обработки аудио: {e}", file=sys.stderr)
            return None
    
    def identify_speaker_role(self, text: str, context: List[str] = None) -> str:
        """Определение роли говорящего (Менеджер/Клиент)"""
        try:
            context_text = "\n".join(context[-5:]) if context else ""
            
            prompt = f"""
Контекст предыдущих реплик:
{context_text}

Новая реплика: "{text}"

Определи, кто говорит - Менеджер компании {self.company} или Клиент.
Ответь одним словом: "Менеджер" или "Клиент".
"""
            
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            
            role = response.choices[0].message.content.strip()
            return "Менеджер" if "Менеджер" in role else "Клиент"
            
        except Exception as e:
            print(f"Ошибка определения роли: {e}", file=sys.stderr)
            # Простая эвристика как fallback
            return "Клиент" if any(word in text.lower() for word in ["не", "нет", "но", "хочу", "нужно"]) else "Менеджер"
    
    def generate_suggestions(self, dialog_history: List[Dict]) -> Dict[str, List[str]]:
        """Генерация подсказок на основе истории диалога (оптимизировано для скорости ~1.5с)"""
        try:
            start_time = time.time()
            
            # Ограничиваем историю для быстрой обработки
            recent_history = dialog_history[-6:]  # Только последние 6 реплик
            dialog_text = ""
            for item in recent_history:
                dialog_text += f"{item['role']}: {item['text']}\n"
            
            # Упрощенный и короткий промпт для скорости
            system_prompt = (
                "Ты коуч продаж. Дай 2-3 краткие подсказки менеджеру в JSON: "
                '{"сейчас": ["что делать"], "скоро": ["что сказать"]}. Каждая до 100 символов.'
            )
            
            user_prompt = f"""
Диалог:
{dialog_text}

Компания: {self.company}
Цель: {self.goal}

JSON подсказки:"""
            
            # Оптимизированный запрос к API
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5,  # Снижено для стабильности
                max_tokens=300,   # Сокращено для скорости
                timeout=8.0       # Строгий таймаут
            )
            
            generation_time = time.time() - start_time
            print(f"⚡ Подсказки сгенерированы за {generation_time:.1f}с")
            
            suggestions_text = response.choices[0].message.content.strip()
            
            # Парсинг JSON с fallback
            try:
                # Попытка извлечь JSON из ответа
                if "{" in suggestions_text:
                    json_start = suggestions_text.find("{")
                    json_end = suggestions_text.rfind("}") + 1
                    json_text = suggestions_text[json_start:json_end]
                    suggestions = json.loads(json_text)
                    return suggestions
                else:
                    return self._get_default_suggestions()
            except json.JSONDecodeError:
                return self._get_default_suggestions()
                
        except Exception as e:
            print(f"Ошибка генерации подсказок: {e}", file=sys.stderr)
            return self._get_default_suggestions()
    
    def _get_default_suggestions(self) -> Dict[str, List[str]]:
        """Подсказки по умолчанию"""
        return {
            "сейчас": ["Активно слушайте клиента", "Задавайте уточняющие вопросы"],
            "скоро": ["Выясните основные потребности", "Предложите решение"],
            "позже": ["Назначьте демо-встречу", "Обсудите следующие шаги"],
            "возражения": ["Покажите понимание", "Приведите примеры успеха"]
        }
    
    def process_text_realtime(self, text: str):
        """Обработка текста в реальном времени"""
        if not text.strip():
            return
            
        # Определение роли
        context = [item['text'] for item in self.dialog_history[-5:]]
        role = self.identify_speaker_role(text, context)
        
        # Добавление в историю
        dialog_item = {
            "role": role,
            "text": text,
            "timestamp": time.time()
        }
        self.dialog_history.append(dialog_item)
        
        print(f"{role}: {text}")
        
        # Генерация подсказок для менеджера
        if role == "Клиент" or len(self.dialog_history) % 2 == 0:
            suggestions = self.generate_suggestions(self.dialog_history)
            self.current_suggestions = suggestions
            self.display_suggestions(suggestions)
    
    def display_suggestions(self, suggestions: Dict[str, List[str]]):
        """Отображение подсказок"""
        print("\n" + "="*50)
        print("🎯 ПОДСКАЗКИ МЕНЕДЖЕРУ:")
        print("="*50)
        
        for category, items in suggestions.items():
            print(f"\n{category.upper()}:")
            for item in items:
                print(f"  • {item}")
        
        print("="*50 + "\n")
    
    def run_file_mode(self, audio_file: Path) -> Dict[str, Any]:
        """Режим обработки файла"""
        print(f"Обработка файла: {audio_file}")
        
        # Подготовка аудио (конвертация в моно 16kHz)
        mono_file = self._prepare_audio_file(audio_file)
        
        # Транскрипция
        print("Транскрибирую аудио...")
        result = self.whisper.transcribe(
            str(mono_file), 
            language=self.language,
            task="transcribe",
            verbose=False
        )
        
        # Обработка сегментов
        segments = result.get("segments", [])
        print(f"Найдено сегментов: {len(segments)}")
        
        for segment in segments:
            text = segment.get("text", "").strip()
            if text:
                self.process_text_realtime(text)
        
        # Очистка временного файла
        if mono_file != audio_file:
            os.unlink(mono_file)
        
        return {
            "dialog_history": self.dialog_history,
            "final_suggestions": self.current_suggestions,
            "total_segments": len(segments)
        }
    
    def _prepare_audio_file(self, audio_file: Path) -> Path:
        """Подготовка аудио файла (конвертация в нужный формат)"""
        if audio_file.suffix.lower() == '.wav':
            return audio_file
            
        # Конвертация с помощью ffmpeg
        output_file = audio_file.with_suffix('.wav')
        cmd = [
            "ffmpeg", "-y", "-i", str(audio_file),
            "-ac", "1", "-ar", "16000",
            str(output_file)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return output_file
        except subprocess.CalledProcessError as e:
            print(f"Ошибка конвертации аудио: {e}", file=sys.stderr)
            return audio_file
    
    def run_realtime_mode(self):
        """Режим реального времени"""
        try:
            from realtime_assistant import RealtimeHelperCaller
            print("🚀 Запуск режима реального времени...")
            realtime_assistant = RealtimeHelperCaller()
            realtime_assistant.run()
        except ImportError:
            print("❌ Для режима реального времени требуется модуль realtime_assistant")
            print("Убедитесь, что установлен pyaudio: pip install pyaudio")
        except Exception as e:
            print(f"❌ Ошибка режима реального времени: {e}")
            print("Используйте режим файла: --input audio_file.wav")
    
    def save_results(self, output_dir: Path, results: Dict[str, Any]):
        """Сохранение результатов"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохранение диалога
        dialog_file = output_dir / "dialog.json"
        with open(dialog_file, 'w', encoding='utf-8') as f:
            json.dump(results["dialog_history"], f, ensure_ascii=False, indent=2)
        
        # Сохранение подсказок
        suggestions_file = output_dir / "suggestions.json"
        with open(suggestions_file, 'w', encoding='utf-8') as f:
            json.dump(results["final_suggestions"], f, ensure_ascii=False, indent=2)
        
        # Текстовый формат диалога
        dialog_txt = output_dir / "dialog.txt"
        with open(dialog_txt, 'w', encoding='utf-8') as f:
            for item in results["dialog_history"]:
                f.write(f"{item['role']}: {item['text']}\n")
        
        print(f"Результаты сохранены в: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="HelperCaller - Пайплайн подсказок для продаж")
    
    # Основные параметры
    parser.add_argument("--input", type=Path, help="Аудио файл для обработки")
    parser.add_argument("--output", type=Path, help="Папка для результатов")
    parser.add_argument("--realtime", action="store_true", help="Режим реального времени")
    
    # Параметры моделей
    parser.add_argument("--whisper-model", default="base", 
                       choices=["tiny", "base", "small", "medium", "large-v3"],
                       help="Модель Whisper")
    parser.add_argument("--openai-model", default="gpt-4o-mini", help="Модель OpenAI")
    parser.add_argument("--language", default="ru", help="Язык для распознавания")
    
    # Параметры компании
    parser.add_argument("--company", default="ВестКолл", help="Название компании")
    parser.add_argument("--goal", default="привлечь клиента и продать услуги",
                       help="Цель продаж")
    parser.add_argument("--tone", default="дружелюбный, экспертный",
                       help="Тональность общения")
    parser.add_argument("--company-info", default="", help="Информация о компании")
    parser.add_argument("--constraints", default="", help="Ограничения")
    
    args = parser.parse_args()
    
    # Проверка параметров
    if not args.realtime and not args.input:
        parser.error("Укажите --input для обработки файла или --realtime для режима реального времени")
    
    if args.input and not args.input.exists():
        parser.error(f"Файл не найден: {args.input}")
    
    # Создание пайплайна
    pipeline = HelperCallerPipeline(
        whisper_model=args.whisper_model,
        openai_model=args.openai_model,
        company=args.company,
        goal=args.goal,
        tone=args.tone,
        company_info=args.company_info,
        constraints=args.constraints,
        language=args.language
    )
    
    try:
        if args.realtime:
            # Режим реального времени
            pipeline.run_realtime_mode()
        else:
            # Режим обработки файла
            results = pipeline.run_file_mode(args.input)
            
            # Сохранение результатов
            if args.output:
                pipeline.save_results(args.output, results)
            else:
                output_dir = args.input.parent / f"{args.input.stem}_results"
                pipeline.save_results(output_dir, results)
                
            print(f"\nОбработано сегментов: {results['total_segments']}")
            print(f"Реплик в диалоге: {len(results['dialog_history'])}")
            
    except KeyboardInterrupt:
        print("\nОстановлено пользователем")
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()