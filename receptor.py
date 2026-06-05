import os
import requests
from flask import Flask, request, jsonify
import asistente_total # Asegúrate de que este sea tu archivo donde tienes la lógica de Google Calendar

app = Flask(__name__)

# --- PARTE 1: ENVÍO DE RECORDATORIOS (Lo que ya tenías) ---
@app.route('/enviar-recordatorio', methods=['POST'])
def enviar_recordatorio():
    datos = request.json
    telefono = datos.get('telefono')
    nombre = datos.get('nombre', 'Paciente')
    fecha = datos.get('fecha', 'mañana')
    hora = datos.get('hora', '10:00 am')
    
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "template",
        "template": {
            "name": "confirmacion_cita",
            "language": {"code": "es_MX"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre},
                        {"type": "text", "text": fecha},
                        {"type": "text", "text": hora}
                    ]
                }
            ]
        }
    }
    
    headers = {
        "Authorization": f"Bearer {os.getenv('META_TOKEN')}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"https://graph.facebook.com/v21.0/{os.getenv('META_PHONE_ID')}/messages",
        json=payload,
        headers=headers
    )
    return response.json(), response.status_code

# --- PARTE 2: RECEPCIÓN DE RESPUESTAS (Webhook) ---
@app.route('/webhook', methods=['GET', 'POST'])
def recibir_mensaje():
    if request.method == 'GET':
        # Verificación con Meta
        verify_token = request.args.get("hub.verify_token")
        if verify_token == os.getenv("VERIFY_TOKEN"):
            return request.args.get("hub.challenge")
        return "Token inválido", 403

if request.method == 'POST':
        datos = request.json
        # Meta envía los datos en esta ruta
        try:
            value = datos['entry'][0]['changes'][0]['value']
            if 'messages' in value:
                msg = value['messages'][0]
                
                # Para botones, el tipo es 'interactive'
                if msg.get('type') == 'interactive':
                    telefono_paciente = msg['from']
                    # RUTA CORRECTA PARA BOTONES
                    button_text = msg['interactive']['button_reply']['title']
                    
                    print(f"Botón presionado: {button_text} por {telefono_paciente}")
                    
                    # Llamar a tu lógica
                    service = asistente_total.obtener_servicio_google()
                    asistente_total.marcar_confirmado(telefono_paciente, service, button_text)
                    
            return jsonify({"status": "ok"}), 200
        except Exception as e:
            print(f"Error detectado: {e}")
            return jsonify({"status": "error"}), 200
