import json
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import anthropic

from .heuristic import run_heuristic, get_level
from ..config import settings


client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ── Estado del grafo ──────────────────────────────────────────────────────
class AgentState(TypedDict):
    content: str
    channel: str
    input_type: str
    heuristic_score: int
    heuristic_hits: list
    rag_similar_cases: int
    rag_context: str
    llm_explanation: str
    llm_recommendations: list
    final_level: str
    final_score: int
    final_confidence: int
    error: str


# ── Nodo 1: Sanitización ─────────────────────────────────────────────────
def node_sanitize(state: AgentState) -> AgentState:
    content = state["content"].strip()
    # Limitar a 2000 chars para evitar prompt injection y costos excesivos
    content = content[:2000]
    # Remover caracteres de control
    content = "".join(c for c in content if c.isprintable() or c in "\n\t")
    return {**state, "content": content, "error": ""}


# ── Nodo 2: Motor heurístico ──────────────────────────────────────────────
def node_heuristic(state: AgentState) -> AgentState:
    hits, score = run_heuristic(state["content"])
    hits_serializable = [{"msg": h.msg, "severity": h.severity} for h in hits]
    return {
        **state,
        "heuristic_score": score,
        "heuristic_hits": hits_serializable,
    }


# ── Nodo 3: RAG (búsqueda semántica) ─────────────────────────────────────
def node_rag(state: AgentState) -> AgentState:
    # Por ahora retorna contexto vacío — se conecta a pgvector en siguiente sprint
    # TODO: buscar embeddings similares en PostgreSQL
    return {
        **state,
        "rag_similar_cases": 0,
        "rag_context": "",
    }


# ── Nodo 4: Análisis LLM ─────────────────────────────────────────────────
def node_llm(state: AgentState) -> AgentState:
    score = state["heuristic_score"]
    hits = state["heuristic_hits"]
    channel = state["channel"]
    content = state["content"]
    rag_context = state.get("rag_context", "")

    hits_text = "\n".join([f"- [{h['severity'].upper()}] {h['msg']}" for h in hits]) or "Ninguna señal detectada"

    rag_section = f"\nCasos similares previos:\n{rag_context}" if rag_context else ""

    prompt = f"""Sos GuIAme, un asistente de ciberseguridad argentino para usuarios no expertos.
Analizá el siguiente mensaje/contenido recibido por {channel} y determiná si es seguro, sospechoso o peligroso.

CONTENIDO A ANALIZAR:
{content}

SEÑALES DETECTADAS POR ANÁLISIS HEURÍSTICO (score: {score}/100):
{hits_text}
{rag_section}

Respondé ÚNICAMENTE con un JSON válido con esta estructura exacta:
{{
  "level": "danger|warn|safe",
  "score": número entre 0 y 100,
  "confidence": número entre 0 y 100,
  "title": "título corto del resultado (máx 50 chars)",
  "subtitle": "subtítulo breve (máx 80 chars)",
  "explanation": "explicación clara en lenguaje cotidiano argentino de por qué es o no es peligroso (2-4 oraciones)",
  "recommendations": ["recomendación 1", "recomendación 2", "recomendación 3"]
}}

Reglas:
- Usá lenguaje simple, sin tecnicismos
- Las recomendaciones deben ser acciones concretas
- Si es danger: sé directo y claro sobre el riesgo
- Si es safe: igual mencioná precauciones generales
- Considerá el contexto argentino (AFIP, ANSES, Mercado Pago, bancos locales)
- NO incluyas nada antes o después del JSON"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()
        # Limpiar posibles backticks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())

        return {
            **state,
            "final_level": data.get("level", get_level(score)),
            "final_score": data.get("score", score),
            "final_confidence": data.get("confidence", 75),
            "llm_explanation": data.get("explanation", ""),
            "llm_recommendations": data.get("recommendations", []),
        }
    except Exception as e:
        # Fallback al motor heurístico si falla la API
        level = get_level(score)
        fallback_recs = {
            "danger": [
                "No respondas ni hagas clic en ningún enlace",
                "Contactá a la entidad directamente por su sitio oficial",
                "Si ya ingresaste datos, llamá a tu banco de inmediato"
            ],
            "warn": [
                "Verificá quién te envió el mensaje antes de actuar",
                "No accedas a enlaces: buscá el sitio oficial en Google",
                "En caso de duda, no respondas"
            ],
            "safe": [
                "El mensaje parece legítimo, podés proceder con normalidad",
                "Nunca compartas contraseñas ni códigos con nadie",
                "Si tenés dudas, consultá con GuIAme nuevamente"
            ],
        }
        return {
            **state,
            "final_level": level,
            "final_score": score,
            "final_confidence": 70,
            "llm_explanation": f"Análisis basado en patrones de detección. Se encontraron {len(hits)} señales de alerta.",
            "llm_recommendations": fallback_recs[level],
            "error": str(e),
        }


# ── Nodo 5: Veredicto final ───────────────────────────────────────────────
def node_verdict(state: AgentState) -> AgentState:
    # Combinar score heurístico y LLM con peso 40/60
    combined = int(state["heuristic_score"] * 0.4 + state["final_score"] * 0.6)
    return {
        **state,
        "final_score": min(combined, 100),
        "final_level": get_level(combined),
    }


# ── Construcción del grafo ────────────────────────────────────────────────
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("sanitize",  node_sanitize)
    graph.add_node("heuristic", node_heuristic)
    graph.add_node("rag",       node_rag)
    graph.add_node("llm",       node_llm)
    graph.add_node("verdict",   node_verdict)

    graph.set_entry_point("sanitize")
    graph.add_edge("sanitize",  "heuristic")
    graph.add_edge("heuristic", "rag")
    graph.add_edge("rag",       "llm")
    graph.add_edge("llm",       "verdict")
    graph.add_edge("verdict",   END)

    return graph.compile()


# Instancia global del grafo compilado
agent_graph = build_graph()


async def run_analysis(content: str, channel: str, input_type: str) -> dict:
    """Ejecuta el agente y retorna el resultado del análisis"""
    initial_state: AgentState = {
        "content": content,
        "channel": channel,
        "input_type": input_type,
        "heuristic_score": 0,
        "heuristic_hits": [],
        "rag_similar_cases": 0,
        "rag_context": "",
        "llm_explanation": "",
        "llm_recommendations": [],
        "final_level": "safe",
        "final_score": 0,
        "final_confidence": 0,
        "error": "",
    }
    result = agent_graph.invoke(initial_state)
    return result
