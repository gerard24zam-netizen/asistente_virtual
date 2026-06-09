from flask import Flask, request
import requests
import asistente_total

app = Flask(__name__)

# ==========================================
# CONFIGURACIÓN DE TU SAAS (LLENA TUS DATOS)
# ==========================================
VERIFY_TOKEN = "mi_token_secreto_Gera" # Ya lo tomé de tu imagen
WHATSAPP_TOKEN = "EAAXdEhil3gMBRjKZCho9kNZBWc1IgIY0fH0FliaG2FkPj8kWIdAYthZCbkVecL0VDUYk14LBMYWbTobDTg3fC99zZAP170M5ImxwpCgFxmcDSlQNDTHnYEZCYoQsgsNVmXSOFMVzcfqny2lfCQgpa4S9EFZBvhwKmq1lzC2WrxEwxvYm9uZAMOGVJaaJ8tUEjHkUwZDZD" # El token largo que te da Facebook
TELEFONO_ID = "1120833397777315" # El ID del número de WhatsApp

def enviar_mensaje_wa(telefono_destino, mensaje_texto):
    """Función para enviar mensajes de regreso por WhatsApp"""
    url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": telefono_destino,
        "type": "text",
        "text": {"body": mensaje_texto}
    }
    try:
        requests.post(url, headers=headers, json=data)
    except Exception as e:
        print(f"Error enviando mensaje WA: {e}")

# ==========================================
# PUNTO DE ENTRADA (WEBHOOK)
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. VERIFICACIÓN DE META (Para que el panel esté en verde)
    if request.method == 'GET':
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Token incorrecto", 403

    # 2. RECEPCIÓN Y PROCESAMIENTO DE MENSAJES DEL PACIENTE
    if request.method == 'POST':
        data = request.get_json()
        try:
            # Navegar por el JSON que envía Meta
            entry = data.get('entry', [])[0]
            changes = entry.get('changes', [])[0].get('value', {})
            
            if 'messages' in changes:
                mensaje_info = changes['messages'][0]
                telefono_paciente = mensaje_info['from']
                
                # Extraer texto del paciente (ya sea texto libre o botón)
                texto_recibido = ""
                if 'text' in mensaje_info:
                    texto_recibido = mensaje_info['text']['body'].lower()
                elif 'button' in mensaje_info:
                    texto_recibido = mensaje_info['button']['text'].lower()
                elif 'interactive' in mensaje_info:
                    texto_recibido = mensaje_info['interactive']['button_reply']['title'].lower()

                # --- LÓGICA DE NEGOCIO ---
                
                # A) Enviar respuesta por WhatsApp
                if "confirm" in texto_recibido:
                    enviar_mensaje_wa(telefono_paciente, "¡Perfecto! Hemos confirmado tu cita. ✅")
                elif "reagendar" in texto_recibido or "cancel" in texto_recibido:
                    enviar_mensaje_wa(telefono_paciente, "Entendido, nos pondremos en contacto para reagendar. 🔄")

                # B) Actualizar el Google Calendar (tu código asistente_total)
                try:
                    service = asistente_total.obtener_servicio_google()
                    asistente_total.marcar_confirmado(telefono_paciente, service, texto_recibido)
                except Exception as e:
                    print(f"Error actualizando Calendar: {e}")

            return "OK", 200
            
        except Exception as e:
            print(f"Error procesando webhook: {e}")
            # Siempre debes devolver 200 a Meta, aunque falle tu código interno, 
            # de lo contrario Meta te bloqueará el Webhook por "errores continuos".
            return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
