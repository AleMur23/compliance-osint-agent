# Agente de Cumplimiento de Grado Empresarial: Gestión Segura de Documentos y Cribado OSINT de Medios Adversos

Flujo de trabajo orientado a producción para **KYC/AML** que combina **extracción estructurada de documentos** con **cribado OSINT de medios adversos** mediante agentes, pensado para entornos FinTech y regulados donde importan la privacidad de datos y la auditoría.

---

## 1. Resumen / Elevator Pitch

Este agente reduce la fricción en **Conozca a su Cliente (KYC)** y **Diligencia Debida Reforzada (EDD)** al:

- **Extraer datos estructurados** de PDFs KYC/EDD (sujeto, empleador, ingresos, resumen) mediante un LLM, con salida JSON estricta para reducir la entrada manual y los errores.
- **Ejecutar cribado de medios adversos** dirigido con la API de Tavily (fuentes de noticias, legales y gubernamentales) en lugar de búsqueda genérica, lo que ayuda a **reducir falsos positivos** y ruido de foros y sitios de preguntas y respuestas.
- **Mantener el contenido sensible de documentos opcionalmente on-premise** gracias a una **arquitectura dual de LLM**: **Ollama** local para procesamiento 100 % privado y “air-gapped”, o **Groq** en la nube para demos ultrarrápidas cuando se relaja la privacidad.

El resultado es una herramienta **human-in-the-loop** que se integra en flujos de cumplimiento existentes: el analista sube un documento, revisa los campos extraídos, lanza OSINT sobre el sujeto o el empleador y obtiene un informe de riesgo estructurado con fuentes, sin enviar PII a terceros salvo que elija explícitamente el LLM en la nube.

---

## 2. Características Principales

| Característica | Descripción |
|----------------|-------------|
| **Arquitectura dual de LLM** | **Local (Ollama, llama3.2)** para privacidad total y cumplimiento air-gapped; **Nube (Groq, Llama-3.3-70b-versatile)** para procesamiento ultrarrápido en demos o entornos no sensibles. |
| **OSINT agéntico** | Integración con la **API de Tavily** para cribado web forense: búsqueda avanzada en noticias, fuentes legales y gubernamentales, con recuperación de imágenes y prompts anti-alucinación para que el LLM solo cite URLs proporcionadas. |
| **UI human-in-the-loop** | Interfaz **Streamlit** con entidades de búsqueda editables, botones “Cargar Sujeto” / “Cargar Empleador” desde los datos extraídos, seguimiento simulado de créditos Tavily (estilo FinOps) y miniaturas de medios clicables con URLs de origen visibles. |
| **Extracción estructurada** | **LangChain** + **Pydantic** imponen parsing JSON estricto de documentos KYC: **Sujeto**, **Empleador**, **Ingresos/Finanzas** (importes, moneda, fechas, periodicidad) y **Resumen**, reduciendo deriva y limpieza manual. |

---

## 3. Arquitectura del Sistema

La aplicación sigue un **pipeline en 2 pasos**:

```
┌─────────────────────────────────────────────────────────────────┐
│  Paso 1: Extracción AI de PDF (LLM)                              │
│  Subir PDF → extracción de texto PyMuPDF → LLM (Ollama/Groq)     │
│  → JSON validado con Pydantic (sujeto, empleador, ingresos,     │
│    resumen)                                                      │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  Paso 2: Análisis de Riesgo OSINT Automatizado                   │
│  Entidad (del Paso 1 o manual) → búsqueda Tavily (texto + imágenes) │
│  → LLM compara contexto del documento + resultados de búsqueda   │
│  → Informe de Medios Adversos (resumen, verdadero/falso positivo, │
│    fuentes)                                                      │
└─────────────────────────────────────────────────────────────────┘
```

- **Paso 1** lo impulsa el backend LLM elegido (Ollama o Groq) y rellena la UI con campos estructurados; el usuario puede cargar **Sujeto** o **Empleador** en la búsqueda OSINT.
- **Paso 2** es **independiente y editable**: se puede ejecutar OSINT sobre cualquier entidad (con o sin documento previo), y el informe incluye una sección **Fuentes y referencias** construida a partir de las URLs exactas devueltas por Tavily.

---

## 4. Instalación y Configuración Local

### Requisitos previos

- **Python 3.10+**
- **Ollama** (para LLM local): [ollama.com](https://ollama.com)
- **TAVILY_API_KEY** (obligatorio para OSINT): [tavily.com](https://tavily.com)
- **GROQ_API_KEY** (opcional, solo para backend Cloud Demo): [console.groq.com](https://console.groq.com)

### Clonar e instalar

```bash
# Clonar el repositorio
git clone <url-de-tu-repo>
cd compliance-agent

# Crear y activar entorno virtual (Unix/macOS)
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
# python -m venv .venv
# .venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt
```

### Variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
TAVILY_API_KEY=tvly-tu-clave-tavily
GROQ_API_KEY=gsk_tu-clave-groq
```

- **TAVILY_API_KEY** es **obligatoria** para la búsqueda de medios adversos.
- **GROQ_API_KEY** solo es necesaria si usas el backend “Cloud Demo (Groq)” en la interfaz.

### LLM local (Ollama)

Para el backend por defecto **Local (Ollama)**, instala Ollama y descarga el modelo:

```bash
ollama run llama3.2
```

Mantén el servicio Ollama en ejecución (por defecto `http://localhost:11434`) al usar el backend local.

---

## 5. Uso

Inicia la aplicación Streamlit desde la raíz del proyecto:

```bash
streamlit run app.py --logger.level=error
```

A continuación:

1. **Paso 1 — Extracción de documento:** Sube un PDF KYC/EDD y pulsa **Extract Information**. Revisa Sujeto, Empleador, Ingresos y Resumen extraídos.
2. **Paso 2 — OSINT:** Opcionalmente pulsa **Load Extracted Subject** o **Load Extracted Employer**, o escribe cualquier nombre de entidad. Pulsa **Run OSINT Search** para ejecutar la búsqueda Tavily y generar el informe de medios adversos. El informe y las miniaturas de medios relacionadas (con URLs clicables) aparecen debajo.

Usa la barra lateral para cambiar entre **Local (Ollama)** y **Cloud Demo (Groq)** y para ver los créditos Tavily restantes (simulados).

---

## 6. Aviso Legal

**OSINT y miniaturas de medios:**  
Los resultados de medios adversos y las miniaturas o enlaces mostrados provienen de **fuentes web de terceros** (p. ej. vía Tavily). Se ofrecen **solo como apoyo a la revisión humana**. No se garantiza la exactitud, relevancia ni integridad del contenido rastreado o agregado. Siempre valida los hallazgos frente a fuentes primarias y tus políticas internas antes de tomar decisiones de cumplimiento o riesgo.

---

## Stack tecnológico (resumen)

- **LLM / orquestación:** LangChain, LangChain Core, LangChain Community, LangChain Groq  
- **LLM local:** Ollama (llama3.2)  
- **LLM nube:** Groq (llama-3.3-70b-versatile)  
- **OSINT:** API Tavily (tavily-python)  
- **PDF:** PyMuPDF  
- **Validación:** Pydantic  
- **UI:** Streamlit  
- **Entorno:** python-dotenv  

Consulta `requirements.txt` para versiones y dependencias opcionales.
