# GeoAI Analytics - Agente de Recuperación & Arquitectura Medallón

Implementación del agente de recuperación ante incidentes, servidor MCP con el SDK oficial, pipeline ETL por capas (Bronze → Silver → Gold) y dashboard operacional interactivo en Streamlit.

---

## 1. Arquitectura General del Sistema

```
                                  ┌────────────────────────┐
                                  │   Transaction Service  │
                                  │      (Puerto 8002)     │
                                  └───────────┬────────────┘
                                              │ POST /transactions
                                              ▼
┌────────────────────────┐        ┌────────────────────────┐
│    Location Service    │        │  Agent Service (FastAPI│
│      (Puerto 8001)     │        │      (Puerto 8000)     │
└───────────▲────────────┘        └───────────┬────────────┘
            │ REST                            │
┌───────────┴────────────┐                    │ 1. Invoca Tools MCP
│   MCP Server (FastMCP) │◄───────────────────┤ 2. Analiza Sentimiento & Urgencia
│      (Puerto 8003)     │      SSE Protocol  │ 3. Persiste en Bronze
└────────────────────────┘                    │
                                              ▼
                           ┌─────────────────────────────────────┐
                           │      PostgreSQL (Puerto 5432)       │
                           │  - Bronze: agent_interactions       │
                           │  - Silver: enriched_transactions    │
                           │  - Gold:   analytics_metrics        │
                           └──────────────────┬──────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      │                                               │
                      ▼                                               ▼
          ┌────────────────────────┐                     ┌────────────────────────┐
          │   ETL Pipeline Worker  │                     │   Streamlit Dashboard  │
          │  Bronze → Silver → Gold│                     │      (Puerto 8501)     │
          └────────────────────────┘                     └────────────────────────┘
```

---

## 2. Estructura de Entrega de la Solución

Todo el código desarrollado se encuentra estructurado estrictamente dentro del directorio `candidate-solution/`, preservando intactos los componentes originales del repositorio según las instrucciones de la evaluación:

```text
candidate-solution/
├── mcp_server/                  # Servidor MCP con SDK oficial (FastMCP) y transporte SSE
│   ├── server.py                # Definición de herramientas MCP y endpoints ASGI (/health)
│   └── location_client.py       # Cliente HTTP asíncrono hacia Location Service
├── agent/                       # Agente de recuperación ante incidentes
│   ├── main.py                  # API FastAPI (POST /transactions, GET /health)
│   ├── agent_workflow.py        # Grafo de estados con LangGraph (StateGraph)
│   ├── mcp_client.py            # Conexión cliente al MCP Server sobre SSE
│   ├── llm_service.py           # Abstracción multi-proveedor (OpenAI, Anthropic, Ollama, Fallback)
│   └── database.py              # Inserción segura en capa Bronze (agent_interactions)
├── pipeline/                    # Pipeline ETL Medallón en pandas
│   ├── bronze_to_silver.py      # Validación de calidad de datos, rangos y enriquecimiento
│   ├── silver_to_gold.py        # Agregaciones analíticas y UPSERT idempotente en PostgreSQL
│   ├── etl_runner.py            # Orquestador con soporte demonio continuo y flag --once
│   └── db_connection.py         # Conexión robusta con SQLAlchemy y psycopg2
├── dashboard/                   # Dashboard operacional Near Real-Time en Streamlit
│   ├── app.py                   # UI moderna (Inter font, Plotly cyber-teal, KPI cards)
│   ├── queries.py               # Consultas optimizadas a Gold y vistas analíticas
│   └── assets/                  # Logotipo y recursos visuales
├── tests/                       # Suite de pruebas unitarias automatizadas (pytest)
│   ├── test_etl_validation.py   # Pruebas de calidad y clasificación de intenciones
│   ├── test_agent_schemas.py    # Validación de esquemas Pydantic (TransactionRequest)
│   └── test_mcp_client.py       # Mocking asíncrono de peticiones MCP
├── docker-compose.yml           # Orquestación completa de los 7 contenedores
├── pyproject.toml               # Configuración unificada de dependencias, empaquetado y linter
└── README.md                    # Documentación técnica completa
```

### Tabla de Servicios y Puertos

| Servicio | Contenedor | Puerto Local | Endpoint de Diagnóstico / Salud |
|---|---|---|---|
| **PostgreSQL** | `gen-ai-postgres` | `5432` | `pg_isready -U agent_user -d gen_ai_agent_db` |
| **Location Service** (Base) | `gen-ai-location-service` | `8001` | `GET http://localhost:8001/` |
| **Transaction Service** (Base) | `gen-ai-transaction-service` | `8002` | `GET http://localhost:8002/status` |
| **MCP Server** | `gen-ai-mcp-server` | `8003` | `GET http://localhost:8003/health` |
| **Agent Recovery Service** | `gen-ai-agent` | `8000` | `GET http://localhost:8000/health` |
| **ETL Pipeline Worker** | `gen-ai-pipeline` | Background | Logs: `docker logs -f gen-ai-pipeline` |
| **Streamlit Dashboard** | `gen-ai-dashboard` | `8501` | `GET http://localhost:8501` |

---

## 3. Componentes Implementados

### 1. Servidor MCP (`mcp_server/`)
- Desarrollado con el **SDK Oficial de MCP** (`FastMCP` / `MCPServer`) con transporte **SSE**.
- Consume el `Location Service` oficial y expone 5 herramientas (*tools*) estandarizadas:
  1. `get_all_locations`: Lista las 12 ubicaciones globales con clima y demografía.
  2. `get_location_by_id`: Búsqueda exacta por ID (ej. `loc_cdmx_001`).
  3. `get_location_by_city`: Búsqueda insensible a mayúsculas por nombre de ciudad.
  4. `get_location_by_coordinates`: Búsqueda por coordenadas geográficas y tolerancia radial.
  5. `get_locations_by_country`: Filtro de ubicaciones por país.
- Incluye endpoint de salud y diagnóstico en `GET /health`.

### 2. Agente Analizador (`agent/`)
- Construido con **LangGraph** (`StateGraph`) y expone el endpoint requerido `POST /transactions` sobre **FastAPI**.
- **Flujo Agéntico Basado en Grafo**:
  ```mermaid
  flowchart LR
      START([START]) --> N1[enrich_context_node]
      N1 --> N2[analyze_llm_node]
      N2 --> N3[persist_bronze_node]
      N3 --> END([END])
  ```
  - `enrich_context_node`: Se conecta al MCP Server sobre SSE para obtener clima, demografía y observaciones locales.
  - `analyze_llm_node`: Realiza el análisis de sentimiento (`positive`, `neutral`, `negative`), nivel de urgencia (`low`, `medium`, `high`) y genera la respuesta contextual.
  - `persist_bronze_node`: Almacena la interacción en la capa **Bronze** (`agent_interactions`) con métricas de latencia y metadata JSONB.
- **Soporte de Modelos y Modo Fallback**: Compatible con Ollama en local (`llama3.2:3b`) o proveedores cloud (OpenAI, Anthropic). Si no se configuran API keys externas, el agente activa un motor heurístico de respaldo que permite probar el flujo completo de extremo a extremo sin costos ni dependencias de red.

### 3. Pipeline ETL Medallón (`pipeline/`)
- Construido en Python con **pandas** y **SQLAlchemy / psycopg2**.
- **Bronze → Silver** (`bronze_to_silver.py`):
  - Identifica transacciones no procesadas de `agent_interactions`.
  - Realiza validaciones de calidad de datos (coordenadas en rango [-90, 90] y [-180, 180], temperatura razonable, humedad en [0, 100], campos obligatorios).
  - Determina `is_valid` y registra errores detallados en `validation_errors`.
  - Desempaqueta y enriquece los datos en `enriched_transactions`.
- **Silver → Gold** (`silver_to_gold.py`):
  - Agrupa por fecha y ciudad `(metric_date, city)`.
  - Calcula agregaciones: total transacciones, latencia promedio, tokens totales, usuarios únicos, clasificación del tipo de consulta más común, hora pico (`peak_hour`), clima predominante y métricas de sentimiento/urgencia.
  - Ejecuta un `UPSERT` idempotente en `analytics_metrics` (`ON CONFLICT (metric_date, city) DO UPDATE`).
- Puede ejecutarse en modo demonio continuo o por demanda con `--once`.

### 4. Dashboard Analítico (`dashboard/`)
- Aplicación interactiva construida con **Streamlit** y visualizaciones en **Plotly**.
- Conectado directamente a la capa **Gold** (`analytics_metrics`) y a las vistas analíticas (`v_location_stats`, `v_recent_enriched_transactions`).
- Ofrece:
  - **Tarjetas KPI en tiempo real**: Total transacciones, usuarios únicos, consumo de tokens, latencia promedio, tasa de sentimiento positivo y porcentaje de urgencia alta.
  - **4 Visualizaciones Analíticas**:
    1. Gráfico de barras horizontales con transacciones por ciudad y mapa de calor de temperatura.
    2. Donut chart interactivo con distribución de sentimiento y urgencia analizados por LLM.
    3. Serie temporal combinada (barras y línea de tendencia) de transacciones y tokens consumidos.
    4. Categorización de tipos de consulta y horas pico.
  - **Explorador Medallón Multi-Pestaña**: Visualización y exportación a CSV de las tablas Gold, transacciones recientes enriquecidas y resúmenes de ubicación.

---

## 4. Despliegue y Ejecución

Para iniciar todos los servicios del ecosistema con un solo comando, ejecuta desde la raíz del repositorio:

```bash
docker compose -f candidate-solution/docker-compose.yml up --build
```

*(O ingresando al directorio de la solución: `cd candidate-solution && docker compose up --build`)*.

Una vez que los contenedores estén levantados, los servicios estarán disponibles en:
- **Dashboard Streamlit**: [http://localhost:8501](http://localhost:8501)
- **Agente Analizador**: [http://localhost:8000](http://localhost:8000)
- **Servidor MCP**: [http://localhost:8003](http://localhost:8003)
- **Transaction Generator**: [http://localhost:8002](http://localhost:8002)
- **Location Service**: [http://localhost:8001](http://localhost:8001)
- **PostgreSQL**: `localhost:5432`

---

## 5. Validación del Flujo de Datos

### 1. Iniciar Envío de Transacciones
Puedes enviar transacciones de prueba usando la API del `Transaction Service`:

```bash
# En Windows PowerShell (usar curl.exe para evitar el alias de Invoke-WebRequest):
curl.exe -X POST "http://localhost:8002/send-batch?count=15"

# O con comando nativo de PowerShell:
Invoke-RestMethod -Method Post -Uri "http://localhost:8002/send-batch?count=15"

# En Linux/macOS o Git Bash:
curl -X POST "http://localhost:8002/send-batch?count=15"

# O activar el modo continuo (envío cada 5 segundos):
curl.exe -X POST "http://localhost:8002/start"
```

### 2. Validar Persistencia en PostgreSQL
Ingresa a PostgreSQL para consultar las tres capas medallón:

```bash
# Conectar al contenedor de base de datos
docker exec -it gen-ai-postgres psql -U agent_user -d gen_ai_agent_db
```

Ejecuta las siguientes consultas de verificación:

```sql
-- 1. Capa Bronze: Datos crudos recibidos por el agente
SELECT transaction_id, user_query, sentiment, urgency_level, response_time_ms, created_at 
FROM agent_interactions 
ORDER BY created_at DESC 
LIMIT 5;

-- 2. Capa Silver: Datos limpios y enriquecidos con validaciones
SELECT id, city, country, temperature, weather_condition, is_valid, processed_at 
FROM enriched_transactions 
ORDER BY processed_at DESC 
LIMIT 5;

-- 3. Capa Gold: Métricas analíticas pre-agregadas
SELECT metric_date, city, total_transactions, avg_response_time_ms, positive_sentiment_count, most_common_weather 
FROM analytics_metrics 
ORDER BY total_transactions DESC;
```

### 3. Visualizar el Dashboard
Abre tu navegador en:
👉 **[http://localhost:8501](http://localhost:8501)**

Podrás ver los KPIs actualizándose en tiempo real, filtrar por ciudades e inspeccionar las métricas agregadas en la capa Gold.

### 4. Demostración en Consola (Script de Prueba Rápida)
Para verificar de forma inmediata el razonamiento del Agente interactuando con el Servidor FastMCP y el modelo de lenguaje, se incluye un script de demostración con casos de prueba reales en español e inglés:

```bash
python candidate-solution/run_llm_demo.py
```
*(No requiere librerías externas; opera directamente con la biblioteca estándar `urllib.request` de Python).*

---

## 6. Variables de Entorno

| Variable | Descripción | Valor por Defecto |
|---|---|---|
| `POSTGRES_HOST` | Host de base de datos | `postgres` (en Docker) / `localhost` |
| `POSTGRES_PORT` | Puerto de PostgreSQL | `5432` |
| `POSTGRES_DB` | Base de datos | `gen_ai_agent_db` |
| `POSTGRES_USER` | Usuario de PostgreSQL | `agent_user` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | `agent_password` |
| `LOCATION_SERVICE_URL` | URL del Location Service | `http://location-service:8001` |
| `MCP_SERVER_URL` | URL del servidor FastMCP | `http://mcp-server:8003` |
| `AGENT_ENDPOINT` | Endpoint del Agente | `http://agent:8000/transactions` |
| `OPENAI_API_KEY` | *(Opcional)* API key de OpenAI | - |
| `ETL_INTERVAL_SECONDS` | Intervalo de polling del pipeline | `5` |

---

## 7. Pruebas Unitarias y Calidad de Código

El proyecto cuenta con una suite integral de **21 pruebas unitarias** que validan la calidad de datos, tipología de consultas, esquemas de entrada y clientes MCP:

```bash
# Validar linter de código (Ruff):
docker exec gen-ai-agent ruff check /app

# Ejecución dentro del contenedor Docker del Agente:
docker exec gen-ai-agent pytest /app/tests -v

# O en entorno local (con el paquete instalado):
pytest candidate-solution/tests/ -v
```

### Cobertura de Pruebas:
1. **Validación de Calidad ETL (`test_etl_validation.py`)**:
   - Validación de coordenadas dentro de límites geográficos válidos (latitud $[-90, 90]$, longitud $[-180, 180]$).
   - Validación de rangos de humedad $[0, 100]$.
   - Manejo de campos obligatorios faltantes (`user_id`, `timestamp`, coordenadas).
   - Categorización determinista de consultas analíticas (`weather`, `peak_hours`, `time`, `demographics`, `general_query`).
2. **Esquemas del Agente (`test_agent_schemas.py`)**:
   - Validación estricta del modelo Pydantic `TransactionRequest`.
   - Prevención de cargas malformadas (ausencia de `transaction_id` o `query`).
   - Mantenimiento de metadatos de ubicación opcionales.
3. **Cliente y Herramientas MCP (`test_mcp_client.py`)**:
   - Mocking asíncrono de endpoints del `Location Service`.
   - Validación de deserialización y tolerancia espacial.

---

## 8. Integración Continua (CI/CD)

Se incluye un pipeline automatizado en [`.github/workflows/ci.yml`](file:///c:/Users/nicoc/GitHub/data_ai_eng_evaluation/.github/workflows/ci.yml) para GitHub Actions con:
- **Matriz Multi-Versión**: Pruebas automáticas bajo Python 3.10 y 3.11.
- **Linter de Calidad de Código**: Inspección estricta con `ruff check`.
- **Ejecución de Tests**: Corrida de toda la suite de `pytest`.
- **Validación de Arquitectura Docker**: Verificación de sintaxis y dependencias con `docker compose config`.

