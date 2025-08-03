"""
Серверная часть для платформы речевой аналитики
Включает распознавание речи, анализ эмоций и генерацию отчетов
"""

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import speech_recognition as sr
import librosa
import numpy as np
from textblob import TextBlob
import re
import json
from datetime import datetime
import os
import tempfile
import wave
from threading import Thread
import queue
import time
import asyncio

# Дополнительные библиотеки для анализа
from collections import Counter
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.sentiment import SentimentIntensityAnalyzer

# Импорт новых модулей
from video_audio_processor import media_processor
from ai_integration import ai_manager, initialize_ai_providers

# Инициализация NLTK (выполните один раз)
# nltk.download('punkt')
# nltk.download('stopwords')
# nltk.download('vader_lexicon')

app = Flask(__name__)
CORS(app)

# Инициализация ИИ провайдеров
AI_CONFIG = {
    "openai": {
        "enabled": True,
        "api_key": os.environ.get("OPENAI_API_KEY", ""),
        "model": "gpt-4"
    },
    "mistral": {
        "enabled": True,
        "api_key": os.environ.get("MISTRAL_API_KEY", ""),
        "model": "mistral-large-latest"
    },
    "preferred_provider": "openai"
}

# Инициализируем ИИ провайдеры при старте
initialize_ai_providers(AI_CONFIG)

class SpeechAnalyzer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone() if sr.Microphone.list_microphone_names() else None
        
        # Настройки для распознавания речи
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.8
        self.recognizer.phrase_threshold = 0.3
        
        # Инициализация анализатора настроений
        try:
            self.sentiment_analyzer = SentimentIntensityAnalyzer()
        except:
            self.sentiment_analyzer = None
            
        # Словари для анализа
        self.positive_keywords = [
            'отлично', 'хорошо', 'замечательно', 'превосходно', 'спасибо',
            'благодарю', 'довольный', 'удовлетворен', 'рекомендую'
        ]
        
        self.negative_keywords = [
            'плохо', 'ужасно', 'недовольный', 'жалоба', 'проблема',
            'ошибка', 'не работает', 'расстроен', 'возмущен'
        ]
        
        # Стоп-слова для фильтрации
        try:
            self.stop_words = set(stopwords.words('russian'))
        except:
            self.stop_words = set()
    
    def audio_to_text(self, audio_file_path):
        """Преобразование аудиофайла в текст"""
        try:
            with sr.AudioFile(audio_file_path) as source:
                # Калибровка шума
                self.recognizer.adjust_for_ambient_noise(source)
                audio = self.recognizer.record(source)
            
            # Попытка распознавания с разными сервисами
            text = ""
            try:
                # Попробуем Google Speech Recognition (бесплатно, но с ограничениями)
                text = self.recognizer.recognize_google(audio, language='ru-RU')
            except sr.UnknownValueError:
                try:
                    # Попробуем с английским языком
                    text = self.recognizer.recognize_google(audio, language='en-US')
                except:
                    text = "Не удалось распознать речь"
            except sr.RequestError:
                # Если Google недоступен, используем offline распознавание
                try:
                    text = self.recognizer.recognize_sphinx(audio, language='ru-RU')
                except:
                    text = "Ошибка распознавания речи"
            
            return text
        
        except Exception as e:
            return f"Ошибка обработки аудио: {str(e)}"
    
    def analyze_sentiment(self, text):
        """Анализ эмоциональной окраски текста"""
        if not text:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0}
        
        # Простой анализ на основе ключевых слов
        text_lower = text.lower()
        positive_count = sum(1 for word in self.positive_keywords if word in text_lower)
        negative_count = sum(1 for word in self.negative_keywords if word in text_lower)
        
        if self.sentiment_analyzer:
            # Используем VADER для более точного анализа
            scores = self.sentiment_analyzer.polarity_scores(text)
            compound_score = scores['compound']
            
            if compound_score >= 0.05:
                sentiment = "positive"
            elif compound_score <= -0.05:
                sentiment = "negative"
            else:
                sentiment = "neutral"
                
            return {
                "sentiment": sentiment,
                "score": compound_score,
                "confidence": abs(compound_score),
                "details": scores
            }
        else:
            # Простой анализ
            if positive_count > negative_count:
                sentiment = "positive"
                score = 0.5 + (positive_count - negative_count) * 0.1
            elif negative_count > positive_count:
                sentiment = "negative"
                score = -0.5 - (negative_count - positive_count) * 0.1
            else:
                sentiment = "neutral"
                score = 0.0
            
            return {
                "sentiment": sentiment,
                "score": score,
                "confidence": abs(score)
            }
    
    def extract_keywords(self, text, top_n=10):
        """Извлечение ключевых слов из текста"""
        if not text:
            return []
        
        # Токенизация и очистка
        words = word_tokenize(text.lower(), language='russian')
        
        # Фильтрация стоп-слов и коротких слов
        filtered_words = [
            word for word in words 
            if word.isalpha() and len(word) > 2 and word not in self.stop_words
        ]
        
        # Подсчет частоты
        word_freq = Counter(filtered_words)
        
        return [word for word, count in word_freq.most_common(top_n)]
    
    def analyze_speech_quality(self, text, audio_duration=0):
        """Анализ качества речи и обслуживания"""
        if not text:
            return {"score": 0, "metrics": {}}
        
        # Метрики качества
        metrics = {}
        
        # 1. Длина разговора
        word_count = len(text.split())
        metrics['word_count'] = word_count
        metrics['speech_rate'] = word_count / max(audio_duration, 1) if audio_duration > 0 else 0
        
        # 2. Вежливость (наличие вежливых слов)
        polite_words = ['пожалуйста', 'спасибо', 'извините', 'добро пожаловать', 'до свидания']
        politeness_score = sum(1 for word in polite_words if word in text.lower())
        metrics['politeness'] = min(politeness_score * 20, 100)  # Максимум 100%
        
        # 3. Структурированность (наличие вопросов и ответов)
        question_marks = text.count('?')
        metrics['interactivity'] = min(question_marks * 10, 100)
        
        # 4. Эмоциональная окраска
        sentiment_result = self.analyze_sentiment(text)
        if sentiment_result['sentiment'] == 'positive':
            emotion_score = 80 + sentiment_result['confidence'] * 20
        elif sentiment_result['sentiment'] == 'neutral':
            emotion_score = 60
        else:
            emotion_score = 40 - sentiment_result['confidence'] * 20
        
        metrics['emotional_tone'] = max(0, min(100, emotion_score))
        
        # Общий балл качества
        overall_score = (
            metrics['politeness'] * 0.3 +
            metrics['interactivity'] * 0.2 +
            metrics['emotional_tone'] * 0.5
        )
        
        return {
            "score": round(overall_score, 1),
            "metrics": metrics
        }
    
    def detect_speakers(self, text):
        """Простое определение говорящих на основе паттернов"""
        # Это упрощенная версия. В реальности нужно использовать 
        # специализированные библиотеки для speaker diarization
        
        lines = text.split('\n')
        speakers = []
        current_speaker = "Говорящий 1"
        
        for i, line in enumerate(lines):
            if line.strip():
                # Простая эвристика: если предложение начинается с приветствия,
                # возможно, это новый говорящий
                if any(greeting in line.lower() for greeting in ['здравствуйте', 'добрый день', 'алло']):
                    if i > 0:  # Не первая строка
                        current_speaker = "Говорящий 2" if current_speaker == "Говорящий 1" else "Говорящий 1"
                
                speakers.append({
                    "speaker": current_speaker,
                    "text": line.strip(),
                    "timestamp": f"00:{i:02d}"
                })
        
        return speakers
    
    def generate_insights(self, analysis_results):
        """Генерация инсайтов и рекомендаций"""
        insights = {"positive": [], "improvements": [], "recommendations": []}
        
        sentiment = analysis_results.get('sentiment', {})
        quality = analysis_results.get('quality', {})
        
        # Позитивные моменты
        if sentiment.get('sentiment') == 'positive':
            insights['positive'].append("Позитивная тональность разговора")
        
        if quality.get('metrics', {}).get('politeness', 0) > 60:
            insights['positive'].append("Вежливое общение")
        
        # Области для улучшения
        if quality.get('score', 0) < 70:
            insights['improvements'].append("Низкое общее качество обслуживания")
        
        if sentiment.get('sentiment') == 'negative':
            insights['improvements'].append("Негативная эмоциональная окраска")
        
        # Рекомендации
        if quality.get('metrics', {}).get('interactivity', 0) < 50:
            insights['recommendations'].append("Больше задавать уточняющих вопросов")
        
        if quality.get('metrics', {}).get('politeness', 0) < 50:
            insights['recommendations'].append("Использовать больше вежливых форм обращения")
        
        return insights

# Глобальный экземпляр анализатора
analyzer = SpeechAnalyzer()

@app.route('/')
def index():
    """Главная страница с интерфейсом"""
    # Здесь можно вернуть HTML интерфейс или редирект на фронтенд
    return jsonify({
        "message": "Speech Analytics API",
        "version": "1.0",
        "endpoints": {
            "/analyze": "POST - Анализ аудиофайла",
            "/health": "GET - Проверка состояния сервиса"
        }
    })

@app.route('/health')
def health_check():
    """Проверка состояния сервиса"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "microphone_available": analyzer.microphone is not None
    })

@app.route('/analyze', methods=['POST'])
def analyze_media():
    """Основной эндпоинт для анализа аудио и видео файлов"""
    try:
        if 'media' not in request.files and 'audio' not in request.files:
            return jsonify({"error": "Медиафайл не найден"}), 400
        
        # Поддерживаем оба названия поля для обратной совместимости
        media_file = request.files.get('media') or request.files.get('audio')
        if media_file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        # Сохраняем временный файл
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            media_file.save(temp_file.name)
            temp_filename = temp_file.name
        
        temp_audio_path = None
        try:
            # Обрабатываем медиафайл (видео или аудио)
            audio_path, media_metadata = media_processor.process_media_file(temp_filename)
            temp_audio_path = audio_path
            
            if not audio_path:
                return jsonify({"error": "Не удалось обработать медиафайл"}), 400
            
            # Распознавание речи
            transcript = analyzer.audio_to_text(audio_path)
            
            # Анализ настроений
            sentiment_result = analyzer.analyze_sentiment(transcript)
            
            # Извлечение ключевых слов
            keywords = analyzer.extract_keywords(transcript)
            
            # Анализ качества
            quality_result = analyzer.analyze_speech_quality(transcript, media_metadata.get('duration', 0))
            
            # Определение говорящих
            speakers = analyzer.detect_speakers(transcript)
            
            # Результаты анализа
            analysis_results = {
                "transcript": transcript,
                "sentiment": sentiment_result,
                "quality": quality_result,
                "keywords": keywords,
                "speakers": speakers,
                "duration": media_metadata.get('duration', 0),
                "media_info": media_metadata,
                "timestamp": datetime.now().isoformat()
            }
            
            # Генерация инсайтов
            insights = analyzer.generate_insights(analysis_results)
            analysis_results["insights"] = insights
            
            # Сохраняем транскрипцию глобально для протоколов
            app.config['LAST_TRANSCRIPT'] = transcript
            app.config['LAST_ANALYSIS'] = analysis_results
            
            return jsonify({
                "success": True,
                "results": analysis_results
            })
        
        finally:
            # Удаляем временные файлы
            cleanup_files = [temp_filename]
            if temp_audio_path and temp_audio_path != temp_filename:
                cleanup_files.append(temp_audio_path)
            
            media_processor.cleanup_temp_files(cleanup_files)
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/analyze/text', methods=['POST'])
def analyze_text():
    """Анализ только текста (без аудио)"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({"error": "Текст не найден"}), 400
        
        text = data['text']
        
        # Анализ настроений
        sentiment_result = analyzer.analyze_sentiment(text)
        
        # Извлечение ключевых слов
        keywords = analyzer.extract_keywords(text)
        
        # Анализ качества (без учета времени)
        quality_result = analyzer.analyze_speech_quality(text)
        
        # Определение говорящих
        speakers = analyzer.detect_speakers(text)
        
        analysis_results = {
            "transcript": text,
            "sentiment": sentiment_result,
            "quality": quality_result,
            "keywords": keywords,
            "speakers": speakers,
            "timestamp": datetime.now().isoformat()
        }
        
        # Генерация инсайтов
        insights = analyzer.generate_insights(analysis_results)
        analysis_results["insights"] = insights
        
        return jsonify({
            "success": True,
            "results": analysis_results
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/export/report', methods=['POST'])
def export_report():
    """Экспорт отчета в различных форматах"""
    try:
        data = request.get_json()
        if not data or 'results' not in data:
            return jsonify({"error": "Данные для экспорта не найдены"}), 400
        
        results = data['results']
        format_type = data.get('format', 'json').lower()
        
        if format_type == 'json':
            return jsonify({
                "success": True,
                "report": results,
                "format": "json"
            })
        
        elif format_type == 'txt':
            # Генерация текстового отчета
            report_text = f"""
ОТЧЕТ ПО АНАЛИЗУ РЕЧИ
Дата: {results.get('timestamp', 'N/A')}

ТРАНСКРИПЦИЯ:
{results.get('transcript', 'N/A')}

АНАЛИЗ НАСТРОЕНИЙ:
Тональность: {results.get('sentiment', {}).get('sentiment', 'N/A')}
Оценка: {results.get('sentiment', {}).get('score', 'N/A')}

КАЧЕСТВО ОБСЛУЖИВАНИЯ:
Общая оценка: {results.get('quality', {}).get('score', 'N/A')}%

КЛЮЧЕВЫЕ СЛОВА:
{', '.join(results.get('keywords', []))}

ИНСАЙТЫ:
Позитивные моменты: {'; '.join(results.get('insights', {}).get('positive', []))}
Области для улучшения: {'; '.join(results.get('insights', {}).get('improvements', []))}
Рекомендации: {'; '.join(results.get('insights', {}).get('recommendations', []))}
            """
            
            return jsonify({
                "success": True,
                "report": report_text,
                "format": "txt"
            })
        
        else:
            return jsonify({"error": "Неподдерживаемый формат"}), 400
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/generate/protocol', methods=['POST'])
def generate_protocol():
    """Генерация структурированного протокола"""
    try:
        data = request.get_json()
        
        # Используем транскрипцию из запроса или последнюю сохраненную
        if data and 'transcript' in data:
            transcript = data['transcript']
        elif 'LAST_TRANSCRIPT' in app.config:
            transcript = app.config['LAST_TRANSCRIPT']
        else:
            return jsonify({"error": "Транскрипция не найдена. Сначала выполните анализ аудио/видео."}), 400
        
        protocol_type = data.get('protocol_type', 'detailed') if data else 'detailed'
        custom_prompt = data.get('custom_prompt', '') if data else ''
        
        # Асинхронная генерация протокола
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            protocol = loop.run_until_complete(
                ai_manager.generate_protocol(transcript, protocol_type, custom_prompt)
            )
            
            if protocol:
                return jsonify({
                    "success": True,
                    "protocol": protocol
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Не удалось сгенерировать протокол"
                }), 500
                
        finally:
            loop.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/generate/all-protocols', methods=['POST'])
def generate_all_protocols():
    """Генерация всех типов протоколов"""
    try:
        data = request.get_json()
        
        # Используем транскрипцию из запроса или последнюю сохраненную
        if data and 'transcript' in data:
            transcript = data['transcript']
        elif 'LAST_TRANSCRIPT' in app.config:
            transcript = app.config['LAST_TRANSCRIPT']
        else:
            return jsonify({"error": "Транскрипция не найдена. Сначала выполните анализ аудио/видео."}), 400
        
        # Асинхронная генерация всех протоколов
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            protocols = loop.run_until_complete(
                ai_manager.generate_all_protocols(transcript)
            )
            
            return jsonify({
                "success": True,
                "protocols": protocols
            })
                
        finally:
            loop.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/analyze/custom', methods=['POST'])
def custom_analysis():
    """Анализ с произвольным промптом пользователя"""
    try:
        data = request.get_json()
        if not data or 'prompt' not in data:
            return jsonify({"error": "Промпт не найден"}), 400
        
        # Используем транскрипцию из запроса или последнюю сохраненную
        if 'transcript' in data:
            transcript = data['transcript']
        elif 'LAST_TRANSCRIPT' in app.config:
            transcript = app.config['LAST_TRANSCRIPT']
        else:
            return jsonify({"error": "Транскрипция не найдена. Сначала выполните анализ аудио/видео."}), 400
        
        custom_prompt = data['prompt']
        
        # Асинхронный анализ
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                ai_manager.custom_analysis(transcript, custom_prompt)
            )
            
            if result:
                return jsonify({
                    "success": True,
                    "analysis": result,
                    "prompt": custom_prompt,
                    "timestamp": datetime.now().isoformat()
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Не удалось выполнить анализ"
                }), 500
                
        finally:
            loop.close()
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/config/ai', methods=['GET', 'POST'])
def ai_config():
    """Управление конфигурацией ИИ"""
    if request.method == 'GET':
        # Возвращаем текущую конфигурацию (без API ключей)
        safe_config = {
            "openai": {
                "enabled": AI_CONFIG["openai"]["enabled"],
                "model": AI_CONFIG["openai"]["model"],
                "has_api_key": bool(AI_CONFIG["openai"]["api_key"])
            },
            "mistral": {
                "enabled": AI_CONFIG["mistral"]["enabled"],
                "model": AI_CONFIG["mistral"]["model"],
                "has_api_key": bool(AI_CONFIG["mistral"]["api_key"])
            },
            "preferred_provider": AI_CONFIG["preferred_provider"]
        }
        return jsonify(safe_config)
    
    elif request.method == 'POST':
        # Обновление конфигурации
        try:
            data = request.get_json()
            
            # Обновляем API ключи если предоставлены
            if 'openai_api_key' in data:
                AI_CONFIG["openai"]["api_key"] = data['openai_api_key']
                AI_CONFIG["openai"]["enabled"] = True
            
            if 'mistral_api_key' in data:
                AI_CONFIG["mistral"]["api_key"] = data['mistral_api_key']
                AI_CONFIG["mistral"]["enabled"] = True
            
            if 'preferred_provider' in data:
                AI_CONFIG["preferred_provider"] = data['preferred_provider']
            
            # Переинициализируем провайдеры
            initialize_ai_providers(AI_CONFIG)
            
            return jsonify({
                "success": True,
                "message": "Конфигурация ИИ обновлена"
            })
            
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

@app.route('/protocols/types', methods=['GET'])
def get_protocol_types():
    """Получение доступных типов протоколов с описаниями"""
    protocol_types = {
        "detailed": {
            "name": "Подробный протокол",
            "description": "Детальное резюме с хронологической последовательностью, техническими деталями и ключевыми репликами"
        },
        "executive": {
            "name": "Управленческое резюме",
            "description": "Лаконичное резюме с фокусом на бизнес-решения, риски и стратегические последствия"
        },
        "tasks": {
            "name": "Задачи и поручения",
            "description": "Структурированный список задач с ответственными, сроками и приоритетами"
        },
        "risks": {
            "name": "Анализ рисков",
            "description": "Выявление рисков, проблем и мер митигации с оценкой влияния"
        },
        "technical": {
            "name": "Техническое резюме",
            "description": "Детальный технический анализ с архитектурными решениями и ограничениями"
        },
        "decisions": {
            "name": "Принятые решения",
            "description": "Анализ всех решений с контекстом, альтернативами и обоснованием"
        }
    }
    
    return jsonify({
        "success": True,
        "protocol_types": protocol_types
    })

if __name__ == '__main__':
    print("🎙️ Запуск сервера Speech Analytics...")
    print("📊 Доступные endpoints:")
    print("   GET  /health - Проверка состояния")
    print("   POST /analyze - Анализ аудиофайла")
    print("   POST /analyze/text - Анализ текста")
    print("   POST /export/report - Экспорт отчета")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)