from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" # El que pusiste en el Webhook de Meta
URL_GOOGLE_GAS = "https://script.google.com/macros/s/AKfycbwwpy4hrxa8flB7C19EN8UAGMGZhfXzI5L4CuK9OXpyL-OoSX6x2ziZ5bM9oqkrRIDmqA/exec"

def limpiar_telefono(tel):
    return "52" + "".join(filter(str.isdigit, str(tel)))[-10:]

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    telefono = limpiar_telefono(data.get('telefono'))
    payload = {
        "messaging_product": "whatsapp", "to": telefono, "type": "template",
        "template": {
            "name": "confirmacion_cita", "language": {"code": "es_MX"},
            "components": [{"type": "body", "parameters": [
                {"type": "text", "text": data.get('nombre')},
                {"type": "text", "text": data.get('fecha')},
                {"type": "text", "text": data.get('hora')}
            ]}]
        }
    }
    resp = requests.post(f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages", 
                         json=payload, headers={"Authorization": f"Bearer {META_TOKEN}"})
    return jsonify({"status": resp.status_code})

def marcar_confirmado(telefono_recibido):
    service = obtener_servicio_calendar() # Usa la conexión que ya tienes configurada
    ahora = datetime.utcnow().isoformat() + 'Z'
    
    # Buscamos eventos desde hoy
    eventos_result = service.events().list(calendarId='primary', timeMin=ahora,
                                           singleEvents=True, orderBy='startTime').execute()
    eventos = eventos_result.get('items', [])

    for evento in eventos:
        descripcion = evento.get('description', '')
        # Si el teléfono del mensaje está en la descripción del evento...
        if telefono_recibido in descripcion:
            titulo_actual = evento.get('summary', '')
            if "✅" not in titulo_actual:
                evento['summary'] = f"✅ {titulo_actual}"
                service.events().update(calendarId='primary', eventId=evento['id'], body=evento).execute()
                print(f"Calendario actualizado: ✅ {titulo_actual}")
                return True
    return False

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    if 'messages' in data['entry'][0]['changes'][0]['value']:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        texto = msg.get('text', {}).get('body', '').lower()
        if "si" in texto or "confirmar" in texto:
            # Notifica a Google Apps Script
            requests.post(URL_GOOGLE_GAS, json={"telefono": msg['from'][-10:]})
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
