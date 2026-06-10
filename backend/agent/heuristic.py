import re
from dataclasses import dataclass


@dataclass
class HeuristicHit:
    msg: str
    severity: str  # danger | warn
    points: int


RULES = [
    # ── DANGER (+18 pts) ──────────────────────────────────────────────────
    (r"bloqueada?|suspendida?|cancelada?|cerrada?",
     "Amenaza de bloqueo de cuenta", "danger", 18),
    (r"urgente|inmediatamente|ahora mismo|en \d+\s*hora|antes de las",
     "Urgencia artificial", "danger", 18),
    (r"clave|contraseña|password|pin|código de verificación",
     "Solicitud de datos secretos", "danger", 18),
    (r"ganaste|felicitaciones|premiado|sorteo|seleccionado",
     "Premio o sorteo falso", "danger", 18),
    (r"número de tarjeta|CVV|cvu|alias|transferir dinero",
     "Solicitud de datos bancarios", "danger", 18),
    (r"http://",
     "Enlace sin cifrado (HTTP)", "danger", 18),
    (r"(banco|pay|secure|login|cuenta)[^.\s]*\.(xyz|tk|ml|top|click|link|online)",
     "Dominio sospechoso", "danger", 18),
    (r"dni|documento de identidad|cuit|cuil",
     "Solicitud de documento de identidad", "danger", 18),
    (r"click aquí|haga clic|toca este enlace|abrí este link",
     "Llamado a acción sobre enlace", "danger", 15),
    (r"mercadolibre|mercado libre|meli|mlm",
     "Suplantación de Mercado Libre", "danger", 15),
    (r"whatsapp|soporte de whatsapp|cuenta de whatsapp",
     "Suplantación de WhatsApp", "danger", 15),
    (r"afip|arca|anses|renaper|migraciones",
     "Suplantación de organismo oficial AR", "danger", 18),

    # ── WARN (+9 pts) ─────────────────────────────────────────────────────
    (r"banco|bbva|santander|galicia|macro|mercadopago|paypal|naranja|brubank|uala",
     "Menciona entidad financiera", "warn", 9),
    (r"gratis|sin costo|descuento|oferta especial|regalo|promo",
     "Oferta demasiado atractiva", "warn", 9),
    (r"bit\.ly|tinyurl|goo\.gl|t\.co|shorturl|cutt\.ly|rb\.gy",
     "Enlace acortado (oculta destino)", "warn", 9),
    (r"verificar cuenta|confirmar identidad|actualizar datos|validar",
     "Pedido de verificación falsa", "warn", 9),
    (r"última oportunidad|expira hoy|caduca|no ignores|tiempo limitado",
     "Presión de tiempo falsa", "warn", 9),
    (r"hacé clic|haz click|ingresá aquí|entrá ahora|accedé",
     "Llamado a acción urgente", "warn", 9),
    (r"premio|beneficio|bono|cashback|reintegro",
     "Promesa de beneficio económico", "warn", 9),
]


def run_heuristic(text: str) -> tuple[list[HeuristicHit], int]:
    """
    Ejecuta las reglas heurísticas sobre el texto.
    Retorna (lista de hits, score total 0-100)
    """
    hits: list[HeuristicHit] = []
    score = 0

    for pattern, msg, severity, points in RULES:
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(HeuristicHit(msg=msg, severity=severity, points=points))
            score += points

    score = min(score, 100)
    return hits, score


def get_level(score: int) -> str:
    if score >= 28:
        return "danger"
    elif score >= 12:
        return "warn"
    return "safe"
