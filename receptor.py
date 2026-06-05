from flask import Flask, request, jsonify
import asistente_total
import os
import requests

app = Flask(__name__)

@app.route('/enviar-recordatorio', methods=['POST'])
def enviar_recordatorio():
    datos = request.json
    telefono = datos.get('telefono')
    mensaje = datos.get('mensaje')
    
    TOKEN = os.getenv("META_TOKEN") 
    NUMERO_ID = os.getenv("META_PHONE_ID")
    
    url_meta = f"https://graph.facebook.com/v21.0/{NUMERO_ID}/messages"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {
        "body": mensaje
        }
    }
    
    try:
        respuesta = requests.post(url_meta, json=payload, headers=headers)
        return jsonify({"status": "lanzado", "meta_response": respuesta.json()}), 200
    except Exception as e:
        return jsonify({"status": "error", "detalle": str(e)}), 500
        
@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    datos = request.json
    try:
        # Nivel 1 dentro de 'try' (4 espacios)
        if 'entry' in datos and 'changes' in datos['entry'][0]:
            # Nivel 2 (8 espacios)
            value = datos['entry'][0]['changes'][0]['value']
            if 'messages' in value:
                # Nivel 3 (12 espacios)
                message = value['messages'][0]
                telefono_paciente = message['from']
                
                # Nivel 3 (12 espacios)
                if message.get('type') == 'button':
                    # Nivel 4 (16 espacios)
                    button_text = message['button']['text']
                    print(f"Paciente {telefono_paciente} presionó: {button_text}")
                    service = asistente_total.obtener_servicio_google()
                    asistente_total.marcar_confirmado(telefono_paciente, service, button_text)
                    
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        # Nivel 1 dentro de 'except' (4 espacios)
        print(f"Error procesando mensaje: {e}")
        return jsonify({"status": "error"}), 200
