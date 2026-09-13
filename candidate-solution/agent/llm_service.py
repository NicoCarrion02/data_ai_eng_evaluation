"""
LLM and Sentiment/Urgency Analysis Service for Agent.
Provides multi-provider LLM support (OpenAI, Anthropic, Ollama)
and an autonomous local analyzer engine.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("agent.llm_service")


class LLMService:
    """Service to perform sentiment analysis, urgency detection, and contextual response generation."""

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL")
        self.ollama_model = os.getenv("OLLAMA_MODEL")

    async def analyze_and_respond(
        self,
        query: str,
        location_data: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = "gpt-4",
    ) -> Tuple[str, str, str]:
        """
        Analyze sentiment, urgency, and generate a contextual response.
        Tries providers in sequence: OpenAI -> Anthropic -> Ollama -> Local Engine Fallback.

        Args:
            query: The user query string.
            location_data: Enriched location data dictionary from MCP.
            model_name: The suggested or preferred model name.

        Returns:
            Tuple of (sentiment, urgency_level, agent_response)
            - sentiment: 'positive' | 'neutral' | 'negative'
            - urgency_level: 'low' | 'medium' | 'high'
            - agent_response: contextual generated string
        """
        # 1. Attempt OpenAI if API key provided and valid
        if self.openai_api_key and not self.openai_api_key.startswith("your_"):
            try:
                res = await self._call_openai(query, location_data, model_name)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"OpenAI analysis failed, checking next provider: {e}")

        # 2. Attempt Anthropic if API key provided and valid
        if self.anthropic_api_key and not self.anthropic_api_key.startswith("your_"):
            try:
                res = await self._call_anthropic(query, location_data, model_name)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Anthropic analysis failed, checking next provider: {e}")

        # 3. Attempt Ollama if configured
        if self.ollama_base_url and not self.ollama_base_url.startswith("your_"):
            try:
                res = await self._call_ollama(query, location_data, model_name)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Ollama analysis unavailable, falling back to local engine: {e}")

        # 4. Local intelligent engine fallback
        return self._local_analysis_engine(query, location_data)

    def _format_location_facts(self, location_data: Optional[Dict[str, Any]]) -> str:
        """Format MCP location dictionary into clear human-readable facts for LLM context."""
        if not location_data:
            return "No local context available."

        city = location_data.get("city")
        country = location_data.get("country")
        location_label = ", ".join(filter(None, [city, country])) or "Unknown Location"

        weather = location_data.get("weather") or {}
        temp = weather.get("temperature")
        temp_str = f"{temp}°C" if temp is not None else "N/A"
        condition = weather.get("condition") or "N/A"
        humidity = weather.get("humidity")
        humidity_str = f"{humidity}%" if humidity is not None else "N/A"
        wind = weather.get("wind_speed")
        wind_str = f"{wind} km/h" if wind is not None else "N/A"

        tz = location_data.get("timezone") or "UTC"

        demo = location_data.get("demographics") or {}
        pop = demo.get("population")
        pop_str = f"{pop:,}" if isinstance(pop, (int, float)) else (str(pop) if pop else "N/A")
        lang = demo.get("language") or "N/A"
        curr = demo.get("currency") or "N/A"

        obs = location_data.get("observations") or []
        obs_str = "; ".join(obs) if obs else "Standard operational schedule"

        return (
            f"- Location: {location_label}\n"
            f"- Current Weather: {condition}, Temperature: {temp_str}, Humidity: {humidity_str}, Wind Speed: {wind_str}\n"
            f"- Timezone: {tz}\n"
            f"- Demographics: Population: {pop_str} inhabitants, Official Language: {lang}, Currency: {curr}\n"
            f"- Local Observations & Operational Peak Hours: {obs_str}"
        )

    def _build_prompt(self, query: str, location_data: Optional[Dict[str, Any]]) -> str:
        """Construct prompt with explicit real-time facts and language matching instructions."""
        facts = self._format_location_facts(location_data)

        return (
            f"You are the official GeoAI Analytics location assistant.\n"
            f"Verified real-time context from MCP service:\n"
            f"{facts}\n\n"
            f"User Query: \"{query}\"\n\n"
            f"Instructions:\n"
            f"1. Sentiment: 'positive', 'neutral', or 'negative'.\n"
            f"2. Urgency Level: 'low', 'medium', or 'high'.\n"
            f"3. Agent Response ('agent_response'):\n"
            f"   - Must be written in the SAME LANGUAGE as the User Query (If query is in Spanish -> reply in Spanish; if in English -> reply in English).\n"
            f"   - Must be a natural, conversational prose paragraph (NEVER output a dictionary, JSON, or key-value list).\n"
            f"   - Directly integrate verified data (temperature, weather, peak hours, observations) to answer the user's question.\n\n"
            f"Respond strictly in JSON format with keys: \"sentiment\", \"urgency_level\", \"agent_response\"."
        )

    def _clean_response(self, response: Any) -> str:
        """Sanitize agent response to ensure clean conversational text without raw dict dumps or formatting glitches."""
        # 1. If response is a dict or stringified dict, unpack into natural text
        if isinstance(response, str):
            trimmed = response.strip()
            if trimmed.startswith("{") and (trimmed.endswith("}") or "}" in trimmed):
                try:
                    match_brace = re.search(r"\{.*\}", trimmed, re.DOTALL)
                    if match_brace:
                        parsed = json.loads(match_brace.group(0))
                        if isinstance(parsed, dict):
                            response = parsed
                except Exception:
                    pass

        if isinstance(response, dict):
            if "agent_response" in response and isinstance(response["agent_response"], str):
                response = response["agent_response"]
            elif any(k in response for k in ["message", "contenido", "texto", "text"]):
                response = response.get("message") or response.get("contenido") or response.get("texto") or response.get("text")
            else:
                # Convert dictionary items into natural flowing sentences instead of raw dict dump
                parts = []
                for k, v in response.items():
                    k_clean = str(k).replace("_", " ").strip()
                    parts.append(f"{k_clean} es {v}" if not str(v).lower().startswith("es ") else f"{k_clean} {v}")
                response = ". ".join(parts) + "."

        res_str = str(response).strip()

        # 2. Extract nested agent_response if enclosed in quotes or sub-JSON
        if "agent_response" in res_str:
            sub = re.search(r'"agent_response"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', res_str)
            if sub:
                res_str = sub.group(1).replace(r'\"', '"')

        # 3. Strip any residual surrounding curly braces, extra quotes, or brackets
        res_str = re.sub(r'^\s*[\{\[\"\']+\s*', '', res_str)
        res_str = re.sub(r'\s*[\}\]\"\']+\s*$', '', res_str)
        res_str = res_str.replace('\r', ' ').replace('\n', ' ').strip()
        res_str = re.sub(r'\s+', ' ', res_str)
        return res_str

    async def _call_openai(
        self, query: str, location_data: Optional[Dict[str, Any]], model_name: str
    ) -> Optional[Tuple[str, str, str]]:
        """Attempt LLM completion via OpenAI client."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.openai_api_key)
            prompt = self._build_prompt(query, location_data)

            completion = await client.chat.completions.create(
                model=model_name or "gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            data = json.loads(completion.choices[0].message.content)
            sentiment = data.get("sentiment", "neutral").lower()
            urgency = data.get("urgency_level", "low").lower()
            response = data.get("agent_response", "Información procesada exitosamente.")
            return sentiment, urgency, self._clean_response(response)
        except Exception as e:
            logger.error(f"OpenAI execution error: {e}")
            return None

    async def _call_anthropic(
        self, query: str, location_data: Optional[Dict[str, Any]], model_name: str
    ) -> Optional[Tuple[str, str, str]]:
        """Attempt LLM completion via Anthropic Claude client."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self.anthropic_api_key)
            prompt = self._build_prompt(query, location_data)

            claude_model = model_name if "claude" in (model_name or "").lower() else "claude-3-haiku-20240307"
            message = await client.messages.create(
                model=claude_model,
                max_tokens=400,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                sentiment = data.get("sentiment", "neutral").lower()
                urgency = data.get("urgency_level", "low").lower()
                response = data.get("agent_response", "Información procesada exitosamente.")
                return sentiment, urgency, self._clean_response(response)
            return None
        except Exception as e:
            logger.error(f"Anthropic execution error: {e}")
            return None

    async def _call_ollama(
        self, query: str, location_data: Optional[Dict[str, Any]], model_name: str
    ) -> Optional[Tuple[str, str, str]]:
        """
        Attempt LLM completion via local Ollama instance.
        Supports both direct host and docker host gateway URLs.
        """
        import httpx

        candidate_urls = []
        if "localhost" in self.ollama_base_url or "127.0.0.1" in self.ollama_base_url:
            host_url = re.sub(r"localhost|127\.0\.0\.1", "host.docker.internal", self.ollama_base_url)
            candidate_urls.append(host_url)
        candidate_urls.append(self.ollama_base_url)

        prompt = self._build_prompt(query, location_data)

        for base_url in candidate_urls:
            url = base_url.rstrip("/")
            try:
                async with httpx.AsyncClient(timeout=65.0) as client:
                    # 1. Discover installed models from Ollama
                    installed_models = []
                    try:
                        tags_res = await client.get(f"{url}/api/tags", timeout=4.0)
                        if tags_res.status_code == 200:
                            installed_models = [m.get("name") for m in tags_res.json().get("models", []) if m.get("name")]
                    except Exception as e:
                        logger.debug(f"Could not fetch tags from {url}: {e}")

                    # 2. If no models installed and none configured, fall back cleanly
                    if not installed_models and not self.ollama_model:
                        logger.warning(f"Ollama at {url} has no models installed. Falling back to local engine.")
                        continue

                    # 3. Determine active model:
                    # A. Configured OLLAMA_MODEL (exact or partial match)
                    # B. Transaction requested model_name (if present in Ollama)
                    # C. First available installed model (auto-detect)
                    active_model = None
                    if self.ollama_model:
                        match_m = next((m for m in installed_models if self.ollama_model in m or m.startswith(self.ollama_model)), None)
                        active_model = match_m or self.ollama_model
                    elif model_name and installed_models:
                        match_m = next((m for m in installed_models if model_name.lower() in m.lower()), None)
                        if match_m:
                            active_model = match_m

                    if not active_model:
                        active_model = installed_models[0] if installed_models else "llama3.2:3b"

                    chat_payload = {
                        "model": active_model,
                        "messages": [
                            {"role": "system", "content": "You are GeoAI Analytics assistant. Always output valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.2}
                    }

                    res = await client.post(f"{url}/api/chat", json=chat_payload, timeout=60.0)
                    if res.status_code == 200:
                        content = res.json().get("message", {}).get("content", "")
                        match = re.search(r"\{.*\}", content, re.DOTALL)
                        if match:
                            data = json.loads(match.group(0))
                            sentiment = str(data.get("sentiment", "neutral")).lower()
                            urgency = str(data.get("urgency_level", "low")).lower()
                            response = data.get("agent_response", "Información procesada exitosamente.")
                            if isinstance(response, str) and "agent_response" in response:
                                sub = re.search(r'"agent_response"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', response)
                                if sub:
                                    response = sub.group(1).replace(r'\"', '"')

                            clean_txt = self._clean_response(response)
                            logger.info(f"Successfully obtained analysis from local Ollama model: {active_model}")
                            return sentiment, urgency, clean_txt
            except Exception as exc:
                logger.warning(f"Ollama attempt on {url} failed: {exc}")
                continue

        return None

    def _local_analysis_engine(
        self, query: str, location_data: Optional[Dict[str, Any]]
    ) -> Tuple[str, str, str]:
        """
        Autonomous contextual analysis engine.
        Evaluates sentiment and urgency based on linguistics and generates rich responses.
        """
        q_lower = query.lower()

        # Urgency detection
        high_urgency_tokens = [
            "urgente", "urgent", "emergencia", "emergency", "asap", "inmediato",
            "immediate", "ahora", "now", "ayuda", "help", "crítico", "critical",
            "alerta", "alert", "grave", "severe", "auxilio", "peligro", "danger"
        ]
        med_urgency_tokens = [
            "rápido", "quick", "cuándo", "when", "tiempo", "demora", "revisar",
            "check", "status", "estado", "pronto", "soon"
        ]

        if any(re.search(rf"\b{tok}\b", q_lower) for tok in high_urgency_tokens):
            urgency = "high"
        elif any(re.search(rf"\b{tok}\b", q_lower) for tok in med_urgency_tokens):
            urgency = "medium"
        else:
            urgency = "low"

        # Sentiment detection
        neg_tokens = [
            "terrible", "mal", "bad", "horrible", "error", "falla", "fail",
            "problema", "problem", "lento", "slow", "queja", "inútil", "pésimo",
            "worst", "hate", "odioso", "desastre", "disaster", "molesto", "annoying"
        ]
        pos_tokens = [
            "gracias", "thank", "excelente", "bueno", "great", "good", "perfect",
            "maravilla", "genial", "super", "agradezco", "increíble", "awesome",
            "maravilloso", "amable", "éxito"
        ]

        if any(re.search(rf"\b{tok}\b", q_lower) for tok in neg_tokens):
            sentiment = "negative"
        elif any(re.search(rf"\b{tok}\b", q_lower) for tok in pos_tokens):
            sentiment = "positive"
        else:
            sentiment = "neutral"

        # Contextual response generation
        loc = location_data or {}
        city = loc.get("city")
        country = loc.get("country")
        loc_display = ", ".join(filter(None, [city, country])) or "the requested location"
        weather = loc.get("weather", {})
        temp = weather.get("temperature")
        temp_str = f"{temp}°C" if temp is not None else "N/A"
        condition = weather.get("condition", "unknown")
        humidity = weather.get("humidity")
        humidity_str = f"{humidity}%" if humidity is not None else "N/A"
        wind = weather.get("wind_speed")
        wind_str = f"{wind} km/h" if wind is not None else "N/A"
        demographics = loc.get("demographics", {})
        population = demographics.get("population")
        pop_display = f"{population:,}" if isinstance(population, (int, float)) else str(population or "N/A")
        currency = demographics.get("currency", "N/A")
        language = demographics.get("language", "N/A")
        tz = loc.get("timezone", "UTC")
        observations = loc.get("observations", [])

        obs_str = f" Local observations: {', '.join(observations)}." if observations else ""

        if any(k in q_lower for k in ["clima", "weather", "temperatura", "temperature", "humidity", "humedad"]):
            response = (
                f"In {loc_display}, current weather is {condition} with a temperature of {temp_str}, "
                f"relative humidity of {humidity_str}, and wind speed of {wind_str}.{obs_str}"
            )
        elif any(k in q_lower for k in ["hora", "time", "timezone", "zona horaria"]):
            response = (
                f"The official timezone in {loc_display} is {tz}.{obs_str}"
            )
        elif any(k in q_lower for k in ["población", "population", "habitantes", "demographics", "demografía", "people", "inhabitants"]):
            response = (
                f"{loc_display} has an approximate population of {pop_display} inhabitants. "
                f"Primary language: {language}. Official currency: {currency}.{obs_str}"
            )
        elif any(k in q_lower for k in ["pico", "peak"]):
            response = (
                f"For {loc_display}, transit and operational observations indicate: "
                f"{obs_str.strip() or 'Standard urban operational schedule.'}"
            )
        else:
            response = (
                f"Contextual data for {loc_display}: Weather is {condition} ({temp_str}), "
                f"timezone {tz}, population: {pop_display} inhabitants.{obs_str}"
            )

        return sentiment, urgency, response
