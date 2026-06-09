from flask import Flask, request, jsonify
import requests
import asistente_total

app = Flask(__name__)

# ==========================================
# CONFIGURACIÓN DE TU SAAS (LLENA TUS DATOS)
# ==========================================
VERIFY_TOKEN = "mi_token_secreto_Gera"
WHATSAPP_TOKEN = "EAAXdEhil3gMBRjKZCho9kNZBWc1IgIY0fH0FliaG2FkPj8kWIdAYthZCbkVecL0VDUYk14LBMYWbTobDTg3fC99zZAP170M5ImxwpCgFxmcDSlQNDTHnYEZCYoQsgsNVmXSOFMVzcfqny2lfCQgpa4S9EFZBvhwKmq1lzC2WrxEwxvYm9uZAMOGVJaaJ8tUEjHkUwZDZD" # Reemplaza esto
TELEFONO_ID = "1120833397777315" # Reemplaza esto

def enviar_mensaje_wa(telefono_destino, mensaje_texto):
    """Función para enviar mensajes por WhatsApp"""
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
        response = requests.post(url, headers=headers, json=data)
        return response  # <--- CLAVE 1: Retornamos la respuesta completa de Meta
    except Exception as e:
        print(f"Error enviando mensaje WA: {e}")
        return None

# ==========================================
# PUERTA 1: RECIBIR RESPUESTAS DEL PACIENTE (WEBHOOK META)
# ==========================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Token incorrecto", 403

    if request.method == 'POST':
        data = request.get_json()
        try:
            entry = data.get('entry', [])[0]
            changes = entry.get('changes', [])[0].get('value', {})
            
            if 'messages' in changes:
                mensaje_info = changes['messages'][0]
                telefono_paciente = mensaje_info['from']
                
                texto_recibido = ""
                if 'text' in mensaje_info:
                    texto_recibido = mensaje_info['text']['body'].lower()

                # A) Enviar respuesta de confirmación al WhatsApp
                if "confirm" in texto_recibido or "sí" in texto_recibido or "si" in texto_recibido:
                    enviar_mensaje_wa(telefono_paciente, "¡Perfecto! Hemos confirmado tu cita. ✅")
                elif "reagendar" in texto_recibido or "cancel" in texto_recibido or "no" in texto_recibido:
                    enviar_mensaje_wa(telefono_paciente, "Entendido, nos pondremos en contacto para reagendar. ❌")

                # B) Actualizar el Google Calendar con ✅ o ❌
                try:
                    service = asistente_total.obtener_servicio_google()
                    asistente_total.marcar_confirmado(telefono_paciente, service, texto_recibido)
                except Exception as e:
                    print(f"Error actualizando Calendar: {e}")

        except Exception as e:
            print(f"Error procesando webhook: {e}")
        return "OK", 200

# ==========================================
# PUERTA 2: ENVIAR RECORDATORIOS (DESDE GOOGLE APPS SCRIPT)
# ==========================================
@app.route('/enviar-recordatorio', methods=['POST'])
def enviar_recordatorio():
    try:
        # Recibimos los datos que manda Google Apps Script
        data = request.get_json()
        telefono = data.get('telefono')
        if telefono and len(str(telefono)) == 10:
           telefono = f"52{telefono}"
        nombre = data.get('nombre')
        fecha = data.get('fecha')
        hora = data.get('hora')
        
        if not telefono:
            return jsonify({"error": "Falta el telefono"}), 400
            
        # Armamos el mensaje que le llegará al paciente
        mensaje = f"Hola {nombre}, te recordamos tu cita para el {fecha} a las {hora}. ¿Confirmas tu asistencia? (Responde CONFIRMAR o CANCELAR)"
        
        # Lo enviamos por WhatsApp
        enviar_mensaje_wa(telefono, mensaje)
        
        print(f"Recordatorio enviado con éxito a {telefono}")
        return jsonify({"status": "Recordatorio enviado"}), 200
        
    except Exception as e:
        print(f"Error en recordatorio: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
