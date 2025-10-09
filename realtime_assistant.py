#!/usr/bin/env python3
"""
HelperCaller - Режим реального времени
Обработка аудио потока в реальном времени для генерации подсказок
"""

import json
import os
import sys
import threading
import time
import queue
import pyaudio
import wave
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
import numpy as np

try:
    import torch
    import whisper
    from openai import OpenAI
except ImportError:
    raise SystemExit("Установите: pip install torch openai-whisper openai pyaudio")

# Конфигурация OpenAI
OPENAI_API_KEY = "***REMOVED***"

class RealtimeHelperCaller:
    def __init__(self):
        # Параметры аудио
        self.CHUNK = 1024  # Размер буфера
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.RECORD_SECONDS = 3  # Длина буферов для обработки
        
        # Инициализация компонентов
        self._init_audio()
        self._init_whisper()
        self._init_openai()
        
        # Состояние
        self.audio_buffer = []
        self.dialog_history = []
        self.is_recording = False
        self.last_suggestion_time = 0
        self.suggestion_cooldown = 5  # Секунд между подсказками
        
        # Очереди для потоков
        self.audio_queue = queue.Queue()
        self.text_queue = queue.Queue()
        self.suggestion_queue = queue.Queue()
        
    def _init_audio(self):
        """Инициализация аудио системы"""
        try:
            self.audio = pyaudio.PyAudio()
            # Поиск устройства ввода
            self.input_device_index = None
            for i in range(self.audio.get_device_count()):
                info = self.audio.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    self.input_device_index = i
                    break
            
            if self.input_device_index is None:
                raise Exception("Не найдено устройство для записи аудио")
                
        except Exception as e:
            raise SystemExit(f"Ошибка инициализации аудио: {e}")
    
    def _init_whisper(self):
        """Инициализация Whisper с оптимизацией для скорости"""
        print("Загружаю модель Whisper (tiny для скорости)...")
        self.whisper = whisper.load_model("tiny", device="cpu")
        torch.set_num_threads(2)  # Ограничение для производительности
        
    def _init_openai(self):
        """Инициализация OpenAI клиента"""
        api_key = OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise SystemExit("Не найден API-ключ OpenAI")
        self.openai_client = OpenAI(api_key=api_key, timeout=5.0)  # Короткий таймаут
    
    def start_recording(self):
        """Начать запись аудио"""
        try:
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.CHUNK
            )
            self.is_recording = True
            print("🎤 Запись начата. Говорите...")
            
        except Exception as e:
            raise Exception(f"Ошибка начала записи: {e}")
    
    def stop_recording(self):
        """Остановить запись"""
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        self.is_recording = False
        print("⏹️ Запись остановлена")
    
    def audio_capture_thread(self):
        """Поток захвата аудио"""
        frame_count = 0
        frames = []
        
        while self.is_recording:
            try:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
                frame_count += 1
                
                # Каждые 3 секунды отправляем на обработку
                if frame_count >= (self.RATE / self.CHUNK * self.RECORD_SECONDS):
                    audio_data = b''.join(frames)
                    self.audio_queue.put(audio_data)
                    frames = []
                    frame_count = 0
                    
            except Exception as e:
                print(f"Ошибка захвата аудио: {e}")
                break
    
    def audio_processing_thread(self):
        """Поток обработки аудио (распознавание речи)"""
        while self.is_recording:
            try:
                # Ждем аудио данные
                audio_data = self.audio_queue.get(timeout=1)
                
                # Сохранение во временный файл
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                    # Создание WAV файла
                    wf = wave.open(tmp_file.name, 'wb')
                    wf.setnchannels(self.CHANNELS)
                    wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                    wf.setframerate(self.RATE)
                    wf.writeframes(audio_data)
                    wf.close()
                    
                    # Транскрипция
                    start_time = time.time()
                    result = self.whisper.transcribe(
                        tmp_file.name,
                        language="ru",
                        task="transcribe",
                        verbose=False
                    )
                    transcription_time = time.time() - start_time
                    
                    text = result.get("text", "").strip()
                    if text:
                        print(f"🎤 Распознано ({transcription_time:.1f}с): {text}")
                        self.text_queue.put(text)
                    
                    # Очистка временного файла
                    os.unlink(tmp_file.name)
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Ошибка обработки аудио: {e}")
    
    def text_processing_thread(self):
        """Поток обработки текста и генерации подсказок"""
        while self.is_recording:
            try:
                # Ждем текст
                text = self.text_queue.get(timeout=1)
                
                # Определение роли говорящего
                role = self.identify_speaker_role(text)
                
                # Добавление в историю
                dialog_item = {
                    "role": role,
                    "text": text,
                    "timestamp": time.time()
                }
                self.dialog_history.append(dialog_item)
                
                print(f"💬 {role}: {text}")
                
                # Генерация подсказок (только для реплик клиента или периодически)
                current_time = time.time()
                if (role == "Клиент" or 
                    current_time - self.last_suggestion_time > self.suggestion_cooldown):
                    
                    start_time = time.time()
                    suggestions = self.generate_fast_suggestions()
                    generation_time = time.time() - start_time
                    
                    if suggestions:
                        print(f"🎯 Подсказки сгенерированы за {generation_time:.1f}с")
                        self.display_suggestions(suggestions)
                        self.last_suggestion_time = current_time
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Ошибка обработки текста: {e}")
    
    def identify_speaker_role(self, text: str) -> str:
        """Быстрое определение роли (упрощенная эвристика)"""
        # Ключевые слова для клиента
        client_keywords = ["не", "нет", "но", "хочу", "нужно", "мне", "у меня", "подумаю"]
        # Ключевые слова для менеджера  
        manager_keywords = ["предлагаем", "можем", "наша компания", "vestcall", "вестколл"]
        
        text_lower = text.lower()
        
        client_score = sum(1 for word in client_keywords if word in text_lower)
        manager_score = sum(1 for word in manager_keywords if word in text_lower)
        
        if manager_score > client_score:
            return "Менеджер"
        else:
            return "Клиент"
    
    def generate_fast_suggestions(self) -> Dict[str, List[str]]:
        """Быстрая генерация подсказок (оптимизировано для скорости)"""
        try:
            # Используем только последние 5 реплик для скорости
            recent_dialog = self.dialog_history[-5:]
            dialog_text = "\n".join([f"{item['role']}: {item['text']}" for item in recent_dialog])
            
            # Упрощенный промпт для быстрой генерации
            prompt = f"""
Диалог:
{dialog_text}

Дай 1-2 краткие подсказки менеджеру в JSON:
{{"сейчас": ["подсказка"], "скоро": ["что делать дальше"]}}
"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Самая быстрая модель
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200  # Ограничение для скорости
            )
            
            response_text = response.choices[0].message.content.strip()
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                return self._get_fallback_suggestions()
                
        except Exception as e:
            print(f"Ошибка генерации подсказок: {e}")
            return self._get_fallback_suggestions()
    
    def _get_fallback_suggestions(self) -> Dict[str, List[str]]:
        """Подсказки по умолчанию"""
        return {
            "сейчас": ["Внимательно слушайте клиента"],
            "скоро": ["Задайте уточняющий вопрос"]
        }
    
    def display_suggestions(self, suggestions: Dict[str, List[str]]):
        """Отображение подсказок в консоли"""
        print("\n" + "="*40)
        print("🎯 ПОДСКАЗКИ:")
        for category, items in suggestions.items():
            for item in items:
                print(f"  💡 {item}")
        print("="*40 + "\n")
    
    def run(self):
        """Запуск режима реального времени"""
        print("🚀 Запуск HelperCaller в режиме реального времени")
        print("Для остановки нажмите Ctrl+C")
        
        try:
            # Запуск записи
            self.start_recording()
            
            # Запуск потоков обработки
            audio_thread = threading.Thread(target=self.audio_capture_thread)
            processing_thread = threading.Thread(target=self.audio_processing_thread)
            text_thread = threading.Thread(target=self.text_processing_thread)
            
            audio_thread.daemon = True
            processing_thread.daemon = True
            text_thread.daemon = True
            
            audio_thread.start()
            processing_thread.start()
            text_thread.start()
            
            # Основной цикл
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n⚠️ Остановка...")
            self.is_recording = False
            self.stop_recording()
            
            # Сохранение истории диалога
            if self.dialog_history:
                output_file = f"dialog_history_{int(time.time())}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(self.dialog_history, f, ensure_ascii=False, indent=2)
                print(f"💾 История диалога сохранена: {output_file}")
        
        finally:
            if hasattr(self, 'audio'):
                self.audio.terminate()


def main():
    """Главная функция для запуска"""
    try:
        assistant = RealtimeHelperCaller()
        assistant.run()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()