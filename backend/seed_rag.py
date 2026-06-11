import asyncio
import voyageai
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv("/opt/guiame/backend/.env")

VOYAGE_KEY = os.getenv("VOYAGE_API_KEY")
DB_URL = os.getenv("DATABASE_URL").replace("+asyncpg", "")

casos = [
    ("ANSES: Su jubilación fue suspendida. Ingrese a http://anses-pagos.com para regularizar", "danger", 95),
    ("AFIP: Tiene una deuda impositiva pendiente. Evite multas ingresando a afip-deuda.net", "danger", 95),
    ("Mercado Pago: Su cuenta fue suspendida por actividad sospechosa. Verifique en mp-verificacion.com", "danger", 92),
    ("Banco Nación: Acceso bloqueado. Actualice sus datos en bna-seguridad.com", "danger", 93),
    ("Ganaste un iPhone 15! Reclamá tu premio en premios-claro.com antes de las 24hs", "danger", 90),
    ("ANSES te informa que tu CBU fue dado de baja. Actualizá tus datos urgente", "danger", 88),
    ("Su tarjeta Visa fue bloqueada por uso fraudulento. Llame al 0800-333-fake", "danger", 91),
    ("Hola! Te mando el resumen de la reunión de ayer como prometí", "safe", 5),
    ("El paquete de Correo Argentino llegará mañana entre 10 y 14hs", "safe", 8),
    ("Recordatorio: turno médico mañana a las 15hs en el centro de salud", "safe", 3),
    ("Mercado Libre: Tu compra fue enviada. Seguí el envío con el código ML123456", "safe", 10),
    ("Hola vecino, ¿podés prestarme la escalera este finde?", "safe", 2),
    ("Este link parece sospechoso, ¿podés verificarlo? http://bit.ly/2xK9mP", "warn", 55),
    ("Promoción exclusiva: 70% off en electrodomésticos. Solo hoy. Comprá ahora", "warn", 50),
    ("Tu cuenta de Netflix será cancelada. Actualizá tu método de pago", "warn", 65),
    ("Felicitaciones! Fuiste seleccionado para recibir un subsidio del gobierno", "warn", 70),
    ("Necesito que me hagas una transferencia urgente, te explico después", "warn", 60),
]

def main():
    print("Conectando a Voyage AI...")
    vo = voyageai.Client(api_key=VOYAGE_KEY)

    print("Conectando a PostgreSQL...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print(f"Generando embeddings para {len(casos)} casos...")
    textos = [c[0] for c in casos]
    result = vo.embed(textos, model="voyage-large-2")
    embeddings = result.embeddings

    insertados = 0
    for i, (texto, level, score) in enumerate(casos):
        embedding = embeddings[i]
        preview = texto[:80]
        cur.execute("""
            INSERT INTO analyses 
            (user_id, content_preview, content_hash, channel, input_type, 
             level, score, confidence, explanation, signals, recommendations, embedding, created_at)
            VALUES (1, %s, md5(%s), 'seed', 'msg', %s, %s, 85, %s, '[]', '[]', %s::vector, NOW())
        """, (
            preview, texto, level, score,
            f"Caso de referencia: {level.upper()} con score {score}",
            str(embedding)
        ))
        insertados += 1
        print(f"  ✅ [{level.upper()}] {preview[:50]}...")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\n✅ Seed completada: {insertados} casos insertados en la DB")

if __name__ == "__main__":
    main()
