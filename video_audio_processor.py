"""
Модуль для обработки видео и аудио файлов всех форматов
Поддерживает извлечение аудио из видео и конвертацию форматов
"""

import os
import tempfile
import subprocess
import librosa
import soundfile as sf
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class VideoAudioProcessor:
    """Процессор для обработки видео и аудио файлов"""
    
    # Поддерживаемые форматы
    SUPPORTED_VIDEO_FORMATS = {
        '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', 
        '.m4v', '.3gp', '.ogv', '.ts', '.mts', '.vob'
    }
    
    SUPPORTED_AUDIO_FORMATS = {
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a',
        '.opus', '.amr', '.3ga', '.awb', '.dss', '.dvf', '.gsm'
    }
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        
    def is_video_file(self, file_path: str) -> bool:
        """Проверка, является ли файл видео"""
        return Path(file_path).suffix.lower() in self.SUPPORTED_VIDEO_FORMATS
    
    def is_audio_file(self, file_path: str) -> bool:
        """Проверка, является ли файл аудио"""
        return Path(file_path).suffix.lower() in self.SUPPORTED_AUDIO_FORMATS
    
    def extract_audio_from_video(self, video_path: str, output_format: str = 'wav') -> Optional[str]:
        """
        Извлечение аудио из видеофайла с помощью ffmpeg
        
        Args:
            video_path: Путь к видеофайлу
            output_format: Формат выходного аудио (wav, mp3, etc.)
            
        Returns:
            Путь к извлеченному аудиофайлу или None при ошибке
        """
        try:
            # Создаем временный файл для аудио
            temp_audio = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix=f'.{output_format}',
                dir=self.temp_dir
            )
            temp_audio.close()
            
            # Команда ffmpeg для извлечения аудио
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # Без видео
                '-acodec', 'pcm_s16le' if output_format == 'wav' else 'mp3',
                '-ar', '16000',  # Частота дискретизации 16kHz для речи
                '-ac', '1',  # Моно
                '-y',  # Перезаписать если файл существует
                temp_audio.name
            ]
            
            # Выполняем команду
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=300  # 5 минут максимум
            )
            
            if result.returncode == 0:
                logger.info(f"Аудио успешно извлечено: {temp_audio.name}")
                return temp_audio.name
            else:
                logger.error(f"Ошибка ffmpeg: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("Таймаут при извлечении аудио")
            return None
        except Exception as e:
            logger.error(f"Ошибка при извлечении аудио: {e}")
            return None
    
    def convert_audio_format(self, input_path: str, output_format: str = 'wav') -> Optional[str]:
        """
        Конвертация аудиофайла в нужный формат
        
        Args:
            input_path: Путь к входному аудиофайлу
            output_format: Целевой формат
            
        Returns:
            Путь к сконвертированному файлу или None при ошибке
        """
        try:
            # Загружаем аудио с помощью librosa
            audio_data, sample_rate = librosa.load(input_path, sr=16000, mono=True)
            
            # Создаем временный файл
            temp_audio = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f'.{output_format}',
                dir=self.temp_dir
            )
            temp_audio.close()
            
            # Сохраняем в нужном формате
            sf.write(temp_audio.name, audio_data, sample_rate)
            
            logger.info(f"Аудио сконвертировано: {temp_audio.name}")
            return temp_audio.name
            
        except Exception as e:
            logger.error(f"Ошибка конвертации аудио: {e}")
            return None
    
    def process_media_file(self, file_path: str) -> Tuple[Optional[str], dict]:
        """
        Обработка медиафайла (видео или аудио)
        
        Args:
            file_path: Путь к медиафайлу
            
        Returns:
            Tuple (путь к аудиофайлу, метаданные)
        """
        metadata = {
            'original_format': Path(file_path).suffix.lower(),
            'file_size': os.path.getsize(file_path),
            'is_video': False,
            'duration': 0
        }
        
        try:
            if self.is_video_file(file_path):
                # Обрабатываем видеофайл
                metadata['is_video'] = True
                audio_path = self.extract_audio_from_video(file_path)
                
                if audio_path:
                    # Получаем длительность
                    audio_data, sr = librosa.load(audio_path, sr=None)
                    metadata['duration'] = len(audio_data) / sr
                    metadata['sample_rate'] = sr
                    
                return audio_path, metadata
                
            elif self.is_audio_file(file_path):
                # Обрабатываем аудиофайл
                try:
                    # Пробуем загрузить напрямую
                    audio_data, sr = librosa.load(file_path, sr=16000, mono=True)
                    metadata['duration'] = len(audio_data) / sr
                    metadata['sample_rate'] = sr
                    
                    # Если формат не WAV, конвертируем
                    if Path(file_path).suffix.lower() != '.wav':
                        converted_path = self.convert_audio_format(file_path)
                        return converted_path, metadata
                    else:
                        return file_path, metadata
                        
                except Exception as e:
                    # Пробуем конвертировать через ffmpeg
                    logger.warning(f"Прямая загрузка не удалась, пробуем ffmpeg: {e}")
                    converted_path = self.convert_audio_with_ffmpeg(file_path)
                    if converted_path:
                        audio_data, sr = librosa.load(converted_path, sr=None)
                        metadata['duration'] = len(audio_data) / sr
                        metadata['sample_rate'] = sr
                    return converted_path, metadata
            else:
                logger.error(f"Неподдерживаемый формат файла: {file_path}")
                return None, metadata
                
        except Exception as e:
            logger.error(f"Ошибка обработки медиафайла: {e}")
            return None, metadata
    
    def convert_audio_with_ffmpeg(self, input_path: str) -> Optional[str]:
        """Конвертация аудио через ffmpeg как fallback"""
        try:
            temp_audio = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.wav',
                dir=self.temp_dir
            )
            temp_audio.close()
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-y',
                temp_audio.name
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            
            if result.returncode == 0:
                return temp_audio.name
            else:
                return None
                
        except Exception as e:
            logger.error(f"Ошибка ffmpeg конвертации: {e}")
            return None
    
    def get_media_info(self, file_path: str) -> dict:
        """Получение информации о медиафайле"""
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Ошибка получения медиа-информации: {e}")
            return {}
    
    def cleanup_temp_files(self, file_paths: list):
        """Очистка временных файлов"""
        for file_path in file_paths:
            try:
                if file_path and os.path.exists(file_path):
                    os.unlink(file_path)
                    logger.info(f"Удален временный файл: {file_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {file_path}: {e}")

# Глобальный экземпляр процессора
media_processor = VideoAudioProcessor()