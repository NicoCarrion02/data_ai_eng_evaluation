import asyncio
import sys
import httpx

sys.stdout.reconfigure(encoding="utf-8")

cases = [
    {
        "transaction_id": "test_domain_es_01",
        "user_id": "analista_logistica",
        "timestamp": "2026-09-12T18:15:00Z",
        "query": "Necesito saber de urgencia cuáles son las horas pico en New York y la temperatura actual para despachar los camiones de carga.",
        "llm_model": "llama3.2:3b",
        "tokens_used": 140,
        "response_time_ms": 400,
        "location_metadata": {"city": "New York"},
    },
    {
        "transaction_id": "test_domain_es_02",
        "user_id": "investigador_urbano",
        "timestamp": "2026-09-12T18:16:00Z",
        "query": "¿Cuántos habitantes tiene Tokyo, qué idioma se habla principalmente y cuál es la moneda de curso legal?",
        "llm_model": "llama3.2:3b",
        "tokens_used": 130,
        "response_time_ms": 380,
        "location_metadata": {"city": "Tokyo"},
    },
    {
        "transaction_id": "test_domain_en_03",
        "user_id": "operations_manager",
        "timestamp": "2026-09-12T18:17:00Z",
        "query": "What is the current temperature and humidity in London? We have outdoor engineering maintenance scheduled.",
        "llm_model": "llama3.2:3b",
        "tokens_used": 150,
        "response_time_ms": 420,
        "location_metadata": {"city": "London"},
    },
    {
        "transaction_id": "test_domain_en_04",
        "user_id": "tourist_planner",
        "timestamp": "2026-09-12T18:18:00Z",
        "query": "Could you provide the weather conditions and peak travel hours for Paris today? Thank you very much!",
        "llm_model": "llama3.2:3b",
        "tokens_used": 120,
        "response_time_ms": 350,
        "location_metadata": {"city": "Paris"},
    },
]

async def main():
    async with httpx.AsyncClient(timeout=40.0) as client:
        for c in cases:
            resp = await client.post("http://localhost:8000/transactions", json=c)
            data = resp.json()
            print(f"[{c['transaction_id']}] -> Status: {resp.status_code} | Sentiment: {data.get('sentiment')} | Urgency: {data.get('urgency_level')}")
            print(f"Query: \"{c['query']}\"")
            print(f"Respuesta del Agente:\n\"{data.get('agent_response')}\"\n")

if __name__ == "__main__":
    asyncio.run(main())
