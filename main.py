from flask import Flask, request, jsonify
import requests
import asistente_total
import json

app = Flask(__name__)

# ==========================================
# CONFIGURACIÓN DE TU SAAS (LLENA TUS DATOS)
# ==========================================
VERIFY_TOKEN = "mi_token_secreto_Gera"
WHATSAPP_TOKEN = "EAAXdEhil3gMBRtHKscQaEsSju4zarI7n03Sx3ZA3l6GucdeNZAWe3HAcEQIRPV5QuA5FZBKq9VrEV3cwId2F0xdeZAc5b6xgjT5VCj7T4ZBTfZBaIggPHBLa4BjZCbijc1rfZCDbTX9eZC9mTZAmwiVC4ySSCcuXZAyKLAu0UTnponRQ3cIt0kjWcShqa6uMGosDS3fzgZDZD"
TELEFONO_ID = "1120833397777315"

def enviar_texto_wa(telefono_destino, mensaje_texto):
    """Envía un mensaje de texto plano normal (para responderle al paciente)"""
    url = f"https://graph.facebook.com/v18.0/{TELEFONO_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": telefono_destino,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": mensaje_texto
        }
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Respuesta texto WA: {response.status_code} - {response.text}")
    return response

def enviar_plantilla_wa(telefono_destino, nombre_paciente, fecha_cita, hora_cita):
    """Envía la plantilla aprobada por Meta (para recordatorios automáticos iniciales)"""
    url = f"https://graph.facebook.com/v18.0/{TELEFONO_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": telefono_destino,
        "type": "template",
        "template": {
            "name": "confirmacion_cita", # <-- ⚠️ NOTA: Asegúrate de que este sea el nombre exacto en tu Meta Business Suite
            "language": { "code": "es_MX" },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre_paciente}, # Llena el {{1}} (Nombre)
                        {"type": "text", "text": fecha_cita},      # Llena el {{2}} (Fecha de la cita)
                        {"type": "text", "text": hora_cita}        # Llena el {{3}} (Hora de la cita)
                    ]
                }
            ]
        }
    }
    response = requests.post(url, headers=headers, json=data)
    print(f"Respuesta plantilla WA: {response.status_code} - {response.text}")
    return response

# ==========================================
# PUERTA 1: WEBHOOK (VERIFICACIÓN Y RESPUESTAS DEL PACIENTE)
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def recibir_webhook():
    # A) VERIFICACIÓN DE META
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                print("¡Webhook verificado exitosamente por Meta!")
                return challenge, 200
            else:
                return "Token inválido", 403
        return "Faltan parámetros", 400

 # B) RECEPCIÓN DE MENSAJES EN TIEMPO REAL (POST)
    if request.method == 'POST':
        data = request.get_json()
        print("--- NOTIFICACIÓN DE META (WEBHOOK) ---")
        print(json.dumps(data, indent=2))

        try:
            entry = data.get('entry', [])[0]
            changes = entry.get('changes', [])[0].get('value', {})

            if 'messages' in changes:
                mensaje_info = changes['messages'][0]
                telefono_paciente = mensaje_info['from']

                texto_recibido = ""
                if 'text' in mensaje_info:
                    texto_recibido = mensaje_info['text']['body'].lower().strip()
                elif 'button' in mensaje_info:
                    texto_recibido = mensaje_info['button']['text'].lower().strip()

                print(f"Mensaje procesado de {telefono_paciente}: {texto_recibido}")

                # Evaluar respuesta del paciente
                if any(x in texto_recibido for x in ["confirm", "si", "sí", "correcto", "ok"]):
                    enviar_texto_wa(telefono_paciente, "¡Perfecto! Hemos confirmado tu cita. ✅")
                    try:
                        service = asistente_total.obtener_servicio_google()
                        if service:
                            # Enviamos el texto real recibido para que coloque la palomita
                            asistente_total.marcar_confirmado(telefono_paciente, service, texto_recibido)
                    except Exception as e:
                        print(f"Error en Google Calendar: {e}")

                elif any(x in texto_recibido for x in ["reagendar", "cancel", "no", "no puedo"]):
                    enviar_texto_wa(telefono_paciente, "Entendido, nos pondremos en contacto para reagendar. ❌")
                    try:
                        service = asistente_total.obtener_servicio_google()
                        if service:
                            # Enviamos el texto real recibido para que asistente_total coloque la equis ❌
                            asistente_total.marcar_confirmado(telefono_paciente, service, texto_recibido)
                    except Exception as e:
                        print(f"Error en Google Calendar: {e}")

        except Exception as e:
            print(f"Error estructurando datos del webhook: {e}")
            
        return "EVENT_RECEIVED", 200

# ==========================================
# PUERTA 2: ENVIAR RECORDATORIOS (DESDE GOOGLE APPS SCRIPT)
# ==========================================
@app.route('/enviar-recordatorio', methods=['POST'])
def enviar_recordatorio():
    try:
        data = request.get_json()
        telefono = data.get('telefono')
        nombre = data.get('nombre', 'Paciente')
        fecha = data.get('fecha', 'hoy') # Si Sheets no manda fecha, toma "hoy" por defecto
        hora = data.get('hora', 'la hora acordada')
        
        if not telefono:
            return jsonify({"error": "Falta el telefono"}), 400
            
        # Forzar formato correcto del número (Limpieza estricta)
        telefono_limpio = "".join(filter(str.isdigit, str(telefono)))
        if len(telefono_limpio) == 10:
            telefono_limpio = f"52{telefono_limpio}"
        
        print(f"Despachando plantilla de recordatorio para {nombre} el {fecha} a las {hora}")
        enviar_plantilla_wa(telefono_limpio, nombre, fecha, hora)
        
        return jsonify({"status": "Recordatorio enviado a Meta con éxito"}), 200
        
    except Exception as e:
        print(f"Error en recordatorio: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
