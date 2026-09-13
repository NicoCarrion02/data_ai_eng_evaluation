"""
Demonstration script sending realistic domain-specific queries to the Agent
running the live Ollama LLM (llama3.2:1b) enriched with real-time MCP facts.
Covers both Spanish and English language queries.
"""

import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

test_cases = [
    # --- Casos en Español ---
    {
        "id": "demo_es_01_ny_operaciones",
        "city": "New York",
        "query": "¿Cuáles son las horas pico en New York y qué temperatura tenemos ahora para coordinar despachos de flota?",
        "topic": "Logística Operacional y Clima (Español)",
    },
    {
        "id": "demo_es_02_tokyo_demografia",
        "city": "Tokyo",
        "query": "¿Cuál es la población actual de Tokyo, qué idioma se habla y cuál es su moneda oficial?",
        "topic": "Datos Demográficos y Económicos (Español)",
    },
    {
        "id": "demo_es_03_londres_clima",
        "city": "London",
        "query": "¿Cómo están las condiciones del clima, humedad y viento en Londres hoy? Tenemos obras al aire libre.",
        "topic": "Monitoreo Meteorológico para Operaciones (Español)",
    },
    # --- Casos en Inglés ---
    {
        "id": "demo_en_01_paris_weather",
        "city": "Paris",
        "query": "What is the current temperature, weather condition, and wind speed in Paris right now?",
        "topic": "Current Weather & Wind Telemetry (English)",
    },
    {
        "id": "demo_en_02_tokyo_timezone",
        "city": "Tokyo",
        "query": "Could you provide the official timezone, local population, and transit observations for Tokyo?",
        "topic": "Timezone, Demographics & Transit (English)",
    },
    {
        "id": "demo_en_03_london_peak",
        "city": "London",
        "query": "What are the local peak hours and current weather conditions in London to schedule deliveries?",
        "topic": "Delivery Scheduling & Peak Hours (English)",
    },
]

print("\n" + "=" * 80)
print("  EVALUACIÓN EN VIVO: CONSULTAS REALES GEOAI (MCP + Ollama llama3.2:3b)")
print("=" * 80 + "\n")

for tc in test_cases:
    payload = {
        "transaction_id": tc["id"],
        "user_id": "analyst_geoai",
        "timestamp": "2026-09-12T18:10:00Z",
        "query": tc["query"],
        "llm_model": "llama3.2:3b",
        "tokens_used": 180,
        "response_time_ms": 400,
        "location_metadata": {"city": tc["city"]},
    }

    req = urllib.request.Request(
        "http://localhost:8000/transactions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    raw = urllib.request.urlopen(req).read().decode("utf-8")
    elapsed = time.time() - t0
    resp = json.loads(raw)

    loc = resp.get("enriched_location", {})
    weather = loc.get("weather", {})
    demo = loc.get("demographics", {})
    obs = loc.get("observations", [])

    print(f"📌 CASO: {tc['topic']}")
    print(f"📍 Contexto MCP Obtenido en Vivo:")
    print(f"   - Ciudad: {loc.get('city')}, {loc.get('country')} (TZ: {loc.get('timezone')})")
    print(f"   - Clima: {weather.get('condition')} | Temp: {weather.get('temperature')}°C | Humedad: {weather.get('humidity')}% | Viento: {weather.get('wind_speed')} km/h")
    print(f"   - Demografía: Población {demo.get('population'):,} hab. | Idioma: {demo.get('language')} | Moneda: {demo.get('currency')}")
    print(f"   - Observaciones/Horas pico: {'; '.join(obs)}")
    print(f"👤 Pregunta del Usuario:\n   \"{tc['query']}\"")
    print(f"🤖 Diagnóstico LLM: Sentimiento = [{resp.get('sentiment')}] | Urgencia = [{resp.get('urgency_level')}] | Latencia = {elapsed:.2f}s")
    print(f"💬 RESPUESTA DEL LLM AL CLIENTE:\n   \"{resp.get('agent_response')}\"")
    print("-" * 80 + "\n")
