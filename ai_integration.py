"""
Модуль интеграции с ИИ сервисами (ChatGPT 4, Mistral 3.1)
Для создания структурированных протоколов и анализа
"""

import os
import json
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class AIProvider(ABC):
    """Базовый класс для ИИ провайдеров"""
    
    @abstractmethod
    async def generate_response(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        pass

class OpenAIProvider(AIProvider):
    """Провайдер для OpenAI ChatGPT"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"
        
    async def generate_response(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Генерация ответа через OpenAI API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.3
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return None

class MistralProvider(AIProvider):
    """Провайдер для Mistral AI"""
    
    def __init__(self, api_key: str, model: str = "mistral-large-latest"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        
    async def generate_response(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Генерация ответа через Mistral API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4000,
            "temperature": 0.3
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        logger.error(f"Mistral API error: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Error calling Mistral API: {e}")
            return None

class ProtocolGenerator:
    """Генератор структурированных протоколов"""
    
    # Системные промпты для разных типов протоколов
    PROTOCOL_PROMPTS = {
        "detailed": """Создайте подробное резюме обсуждения, включающее основные темы, принятые решения, поставленные задачи и ключевые реплики участников. Сохраняйте хронологическую последовательность, группируя связанные пункты. Сфокусируйтесь на конкретных результатах и следующих шагах. Выделяйте важные детали технических обсуждений и договоренностей. Сохраняйте технические термины и определения в исходном виде.""",
        
        "executive": """Создайте лаконичное управленческое резюме, выделяя ключевые решения, основные результаты, стратегические последствия и критически важные следующие шаги. Сфокусируйтесь на бизнес-влиянии, рисках и возможностях. Группируйте информацию по важности, а не хронологически. Используйте деловой язык, избегая технических деталей там, где это возможно.""",
        
        "tasks": """Проанализируйте обсуждение и выделите все поставленные задачи, назначенные поручения и обсуждаемые сроки. Структурируйте информацию по ответственным лицам и приоритетам. Для каждой задачи укажите: ответственного, срок выполнения (если есть), зависимости от других задач, критерии выполнения. Отметьте задачи, требующие немедленного внимания или блокирующие другие работы.""",
        
        "risks": """Проанализируйте обсуждение на предмет выявления рисков, проблем и потенциальных сложностей. Для каждого риска укажите: описание, вероятность возникновения, потенциальное влияние, предложенные меры митигации. Отдельно выделите уже существующие проблемы и их текущий статус. Сгруппируйте риски по категориям (технические, организационные, внешние и т.д.).""",
        
        "technical": """Создайте детальное техническое резюме с акцентом на архитектурные решения, технологические выборы и технические ограничения. Сохраняйте все специфические термины, версии, параметры и метрики. Отдельно выделите: принятые технические решения, отвергнутые альтернативы с причинами, технические требования и ограничения, вопросы производительности и масштабируемости.""",
        
        "decisions": """Проанализируйте все принятые решения в ходе встречи. Для каждого решения укажите: суть решения, контекст и предпосылки, рассмотренные альтернативы, обоснование выбора, необходимые следующие шаги. Отдельно отметьте отложенные решения и решения, требующие дополнительного согласования. Сгруппируйте решения по темам или областям влияния."""
    }
    
    def __init__(self, ai_provider: AIProvider):
        self.ai_provider = ai_provider
        
    async def generate_protocol(self, transcript: str, protocol_type: str, custom_prompt: str = "") -> Optional[Dict[str, Any]]:
        """
        Генерация протокола указанного типа
        
        Args:
            transcript: Транскрипция встречи
            protocol_type: Тип протокола (detailed, executive, tasks, etc.)
            custom_prompt: Пользовательский промпт (опционально)
            
        Returns:
            Структурированный протокол
        """
        try:
            # Выбираем системный промпт
            if custom_prompt:
                system_prompt = custom_prompt
            elif protocol_type in self.PROTOCOL_PROMPTS:
                system_prompt = self.PROTOCOL_PROMPTS[protocol_type]
            else:
                system_prompt = self.PROTOCOL_PROMPTS["detailed"]  # По умолчанию
            
            # Формируем промпт для анализа
            analysis_prompt = f"""
Проанализируйте следующую транскрипцию встречи и создайте структурированный протокол согласно инструкциям.

ТРАНСКРИПЦИЯ:
{transcript}

ИНСТРУКЦИИ:
{system_prompt}

Представьте результат в формате JSON со следующей структурой:
{{
    "title": "Заголовок протокола",
    "date": "Дата анализа",
    "protocol_type": "Тип протокола",
    "summary": "Краткое резюме",
    "main_points": [
        "Основной пункт 1",
        "Основной пункт 2"
    ],
    "decisions": [
        {{
            "decision": "Описание решения",
            "responsible": "Ответственный",
            "deadline": "Срок (если есть)"
        }}
    ],
    "action_items": [
        {{
            "task": "Описание задачи",
            "assignee": "Исполнитель",
            "due_date": "Срок",
            "priority": "high/medium/low"
        }}
    ],
    "risks_issues": [
        {{
            "risk": "Описание риска",
            "impact": "Влияние",
            "mitigation": "Способы митигации"
        }}
    ],
    "next_steps": [
        "Следующий шаг 1",
        "Следующий шаг 2"
    ],
    "participants": [
        "Участник 1",
        "Участник 2"
    ],
    "technical_details": {{
        "systems": ["Система 1", "Система 2"],
        "technologies": ["Технология 1", "Технология 2"],
        "requirements": ["Требование 1", "Требование 2"]
    }},
    "appendix": "Дополнительная информация"
}}

Убедитесь, что JSON валиден и содержит всю релевантную информацию из транскрипции.
            """
            
            # Генерируем ответ
            response = await self.ai_provider.generate_response(analysis_prompt)
            
            if not response:
                return None
            
            # Пытаемся парсить JSON
            try:
                # Извлекаем JSON из ответа (может быть обернут в markdown)
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                
                if json_start != -1 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    protocol_data = json.loads(json_str)
                    
                    # Добавляем метаданные
                    protocol_data["generated_at"] = datetime.now().isoformat()
                    protocol_data["ai_model"] = getattr(self.ai_provider, 'model', 'unknown')
                    protocol_data["protocol_type"] = protocol_type
                    
                    return protocol_data
                else:
                    # Если JSON не найден, возвращаем текстовый протокол
                    return {
                        "title": f"Протокол встречи ({protocol_type})",
                        "date": datetime.now().isoformat(),
                        "protocol_type": protocol_type,
                        "content": response,
                        "format": "text",
                        "generated_at": datetime.now().isoformat(),
                        "ai_model": getattr(self.ai_provider, 'model', 'unknown')
                    }
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                # Возвращаем текстовый формат
                return {
                    "title": f"Протокол встречи ({protocol_type})",
                    "date": datetime.now().isoformat(),
                    "protocol_type": protocol_type,
                    "content": response,
                    "format": "text",
                    "generated_at": datetime.now().isoformat(),
                    "ai_model": getattr(self.ai_provider, 'model', 'unknown')
                }
                
        except Exception as e:
            logger.error(f"Error generating protocol: {e}")
            return None
    
    async def generate_multiple_protocols(self, transcript: str, protocol_types: List[str]) -> Dict[str, Any]:
        """Генерация нескольких типов протоколов одновременно"""
        results = {}
        
        tasks = []
        for protocol_type in protocol_types:
            task = asyncio.create_task(
                self.generate_protocol(transcript, protocol_type)
            )
            tasks.append((protocol_type, task))
        
        for protocol_type, task in tasks:
            try:
                result = await task
                results[protocol_type] = result
            except Exception as e:
                logger.error(f"Error generating {protocol_type} protocol: {e}")
                results[protocol_type] = None
        
        return results
    
    async def analyze_with_custom_prompt(self, transcript: str, custom_prompt: str) -> Optional[str]:
        """Анализ с произвольным промптом пользователя"""
        try:
            analysis_prompt = f"""
{custom_prompt}

ТРАНСКРИПЦИЯ ДЛЯ АНАЛИЗА:
{transcript}
            """
            
            response = await self.ai_provider.generate_response(analysis_prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error with custom prompt analysis: {e}")
            return None

class AIAnalysisManager:
    """Менеджер для управления ИИ анализом"""
    
    def __init__(self):
        self.providers = {}
        self.protocol_generator = None
        
    def add_openai_provider(self, api_key: str, model: str = "gpt-4"):
        """Добавление OpenAI провайдера"""
        provider = OpenAIProvider(api_key, model)
        self.providers["openai"] = provider
        if not self.protocol_generator:
            self.protocol_generator = ProtocolGenerator(provider)
        
    def add_mistral_provider(self, api_key: str, model: str = "mistral-large-latest"):
        """Добавление Mistral провайдера"""
        provider = MistralProvider(api_key, model)
        self.providers["mistral"] = provider
        if not self.protocol_generator:
            self.protocol_generator = ProtocolGenerator(provider)
    
    def set_active_provider(self, provider_name: str):
        """Установка активного провайдера"""
        if provider_name in self.providers:
            self.protocol_generator = ProtocolGenerator(self.providers[provider_name])
            return True
        return False
    
    async def generate_protocol(self, transcript: str, protocol_type: str = "detailed", custom_prompt: str = "") -> Optional[Dict[str, Any]]:
        """Генерация протокола"""
        if not self.protocol_generator:
            logger.error("No AI provider configured")
            return None
        
        return await self.protocol_generator.generate_protocol(transcript, protocol_type, custom_prompt)
    
    async def generate_all_protocols(self, transcript: str) -> Dict[str, Any]:
        """Генерация всех типов протоколов"""
        if not self.protocol_generator:
            logger.error("No AI provider configured")
            return {}
        
        protocol_types = ["detailed", "executive", "tasks", "risks", "technical", "decisions"]
        return await self.protocol_generator.generate_multiple_protocols(transcript, protocol_types)
    
    async def custom_analysis(self, transcript: str, custom_prompt: str) -> Optional[str]:
        """Анализ с произвольным промптом"""
        if not self.protocol_generator:
            logger.error("No AI provider configured")
            return None
        
        return await self.protocol_generator.analyze_with_custom_prompt(transcript, custom_prompt)

# Глобальный менеджер
ai_manager = AIAnalysisManager()

# Функция для инициализации с настройками
def initialize_ai_providers(config: Dict[str, Any]):
    """Инициализация ИИ провайдеров из конфигурации"""
    
    # OpenAI
    if config.get("openai", {}).get("enabled", False):
        api_key = config["openai"].get("api_key")
        model = config["openai"].get("model", "gpt-4")
        if api_key:
            ai_manager.add_openai_provider(api_key, model)
            logger.info("OpenAI provider initialized")
    
    # Mistral
    if config.get("mistral", {}).get("enabled", False):
        api_key = config["mistral"].get("api_key")
        model = config["mistral"].get("model", "mistral-large-latest")
        if api_key:
            ai_manager.add_mistral_provider(api_key, model)
            logger.info("Mistral provider initialized")
    
    # Устанавливаем активный провайдер
    preferred = config.get("preferred_provider", "openai")
    ai_manager.set_active_provider(preferred)