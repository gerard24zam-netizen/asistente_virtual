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

def enviar_plantilla_wa(telefono_destino, nombre_paciente, hora_cita):
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
            "name": "confirmacion_cita", 
            "language": { "code": "es_MX" },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre_paciente}, # Llena el {{1}}
                        {"type": "text", "text": "hoy"},            # Llena el {{2}}
                        {"type": "text", "text": hora_cita}          # Llena el {{3}}
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

# =====================================================================
# FUNCIÓN ENLACE: ENVÍA EL ESTATUS DE REGRESO A GOOGLE APPS SCRIPT
# =====================================================================
def notificar_cambio_a_google(telefono_paciente, estatus_evento):
    # Pega aquí la URL que te dio Google al implementar como Aplicación Web
    URL_GOOGLE_WEBAPP = "https://script.google.com/macros/s/AKfycbwVkPIYpllxegZaPvJACGNSSOwty5mcBxNTY_MMPgySMN-VuVjjVknRqUWYBShJPZJ3zQ/exec"
    
    # Extraemos solo los últimos 10 dígitos para asegurar compatibilidad con Google Calendar
    telefono_10_digitos = telefono_paciente[-10:]
    
    payload = {
        "telefono": telefono_10_digitos,
        "estatus": estatus_evento  # Enviará 'confirmado' o 'cancelado'
    }
    try:
        import requests
        response = requests.post(URL_GOOGLE_WEBAPP, json=payload)
        print(f" Sincronización con Google Calendar: {response.json()}")
    except Exception as e:
        print(f"❌ Error al sincronizar con Google Calendar: {e}")

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
                if any(x in texto_recibido for x in ["Si, confirmo", "confirm", "sí", "si", "correcto", "ok"]):
                    enviar_texto_wa(telefono_paciente, "¡Perfecto! Hemos confirmado tu cita. ✅")
                    try:
                        service = asistente_total.obtener_servicio_google()
                        if service:
                            # Limpieza para Calendar: Extraemos los últimos 10 dígitos (elimina el '521')
                            telefono_buscar = "".join(filter(str.isdigit, str(telefono_paciente)))[-10:]
                            asistente_total.marcar_confirmado(telefono_buscar, service, "confirmar")
                    except Exception as e:
                        print(f"Error en Google Calendar: {e}")

                elif any(x in texto_recibido for x in ["No, reagendar", "reagendar", "cancel", "no", "no puedo"]):
                    enviar_texto_wa(telefono_paciente, "Entendido, nos pondremos en contacto para reagendar. ❌")
                    try:
                        service = asistente_total.obtener_servicio_google()
                        if service:
                            # Limpieza para Calendar: Extraemos los últimos 10 dígitos (elimina el '521')
                            telefono_buscar = "".join(filter(str.isdigit, str(telefono_paciente)))[-10:]
                            asistente_total.marcar_confirmado(telefono_buscar, service, "reagendar")
                    except Exception as e:
                        print(f"Error en Google Calendar: {e}")
                        if button_id == "confirmar_cita":
                            print(f"Paciente {telefono} confirmó cita")
                            enviar_mensaje_texto(telefono, "¡Gracias! Tu cita ha sido confirmada con éxito. Te esperamos.")
                            #  NUEVA LÍNEA: Avisamos a Google Calendar que ponga la palomita
                            notificar_cambio_a_google(telefono, "confirmado")
                                    
                        elif button_id == "cancelar_cita":
                             print(f"Paciente {telefono} canceló cita")
                             enviar_mensaje_texto(telefono, "Entendido. Tu cita ha sido cancelada. Si deseas reagendar, quedamos a tus órdenes.")
                             #  NUEVA LÍNEA: Avisamos a Google Calendar que ponga el tache
                             notificar_cambio_a_google(telefono, "cancelado")

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
        hora = data.get('hora', 'la hora acordada')
        
        if not telefono:
            return jsonify({"error": "Falta el telefono"}), 400
            
        # Forzar formato correcto del número (Limpieza estricta)
        telefono_limpio = "".join(filter(str.isdigit, str(telefono)))
        if len(telefono_limpio) == 10:
            telefono_limpio = f"52{telefono_limpio}"
        
        print(f"Despachando plantilla de recordatorio para {nombre} a las {hora}")
        enviar_plantilla_wa(telefono_limpio, nombre, hora)
        
        return jsonify({"status": "Recordatorio enviado a Meta con éxito"}), 200
        
    except Exception as e:
        print(f"Error en recordatorio: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
