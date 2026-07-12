from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN (Rellena esto una única vez) ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBRz3MsGhr3HDZAy8squZCSZCqRyG8R82vZCvpeZA92WWVoc2ZBIRLlAVVFuF7qVKLbgdJJOFRCoQf60HLGKod8O2F6rzaPVKclx732sZAv97NLSo8Wg52UXJFjVMiXomDrL6OpRe0rgX2So92x0vIRD2Gl8YjHtETEOwt3dh1inVN8OFroqo5VZBN0dAWWquPOpLhs8ENIZBWqJEPNZC4ozbCnQxF00tHqeJftrdrH9alVl"
VERIFY_TOKEN = "TOKEN_SECRETO_META" # El que pongas en Meta
URL_GOOGLE_GAS = "https://script.google.com/macros/s/AKfycbwVkPIYpllxegZaPvJACGNSSOwty5mcBxNTY_MMPgySMN-VuVjjVknRqUWYBShJPZJ3zQ/exec" # La que termina en /exec

# --- RUTAS DEL SERVIDOR ---

@app.route('/', methods=['GET'])
def home():
    # Esta ruta evita que el navegador o monitores den error 404
    return "Servidor Activo", 200

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    telefono = "".join(filter(str.isdigit, str(data.get('telefono', ''))))
    # Asegurar que tenga el prefijo de país si es necesario
    if not telefono.startswith('52'): telefono = '52' + telefono
    
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "template",
        "template": {
            "name": "confirmacion_cita",
            "language": {"code": "es_MX"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": data.get('nombre', 'Paciente')},
                    {"type": "text", "text": data.get('fecha', 'hoy')},
                    {"type": "text", "text": data.get('hora', 'por definir')}
                ]
            }]
        }
    }
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    resp = requests.post(f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages", json=payload, headers=headers)
    return jsonify({"status": resp.status_code})

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. VERIFICACIÓN (Petición GET de Meta)
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Forbidden", 403
    
    # 2. RECEPCIÓN DE MENSAJES (Petición POST de Meta)
    if request.method == 'POST':
        data = request.get_json()
        try:
            msg = data['entry'][0]['changes'][0]['value']['messages'][0]
            texto = msg.get('text', {}).get('body', '').lower()
            telefono_remitente = msg.get('from')
            
            # Si el usuario confirma, avisamos a Google
            if "si" in texto or "confirmar" in texto or "confirmado" in texto:
                # Extraemos últimos 10 dígitos para que coincidan con Google
                tel_limpio = telefono_remitente[-10:] 
                requests.post(URL_GOOGLE_GAS, json={"telefono": tel_limpio})
                
        except (KeyError, IndexError):
            pass # No es un mensaje de texto, ignoramos
            
        return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
