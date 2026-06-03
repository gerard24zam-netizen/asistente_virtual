from flask import Flask, request, jsonify
import asistente_total
import os

app = Flask(__name__)

# En lugar de hardcodear el token, usaremos una variable de entorno
TOKEN_VERIFICACION = os.getenv("VERIFY_TOKEN")

@app.route('/webhook', methods=['GET'])
def verificar_webhook():
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if token == TOKEN_VERIFICACION:
        return challenge
    return "Token incorrecto", 403

@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    datos = request.json
    try:
        # Extraemos info de forma más segura
        value = datos['entry'][0]['changes'][0]['value']
        if 'messages' not in value:
            return jsonify({"status": "ok"}), 200
        
        message = value['messages'][0]
        telefono_paciente = message['from']
        
        # Detectamos si es un botón
        if message['type'] == 'button':
            button_text = message['button']['text']
            print(f"Paciente {telefono_paciente} presionó: {button_text}")
            
            # Autenticamos el servicio (esto usará tu OAuth Client ID)
            service = asistente_total.obtener_servicio_google()
            
            # Llamamos a tu lógica de calendario
            asistente_total.marcar_confirmado(telefono_paciente, service, button_text)
            
        return jsonify({"status": "recibido"}), 200
    except Exception as e:
        print(f"Error procesando mensaje: {e}")
        return jsonify({"status": "error"}), 200

if __name__ == '__main__':
    # Render usa una variable de entorno llamada PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
