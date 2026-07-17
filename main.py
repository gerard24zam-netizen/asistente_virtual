import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" 
SCOPES = ['https://www.googleapis.com/auth/calendar']

def obtener_servicio_calendar():
    # Leemos el JSON desde la variable de entorno que configuramos en Render
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        raise ValueError("Error: No se encontró la variable GOOGLE_CREDENTIALS")
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

def limpiar_telefono(tel):
    return "52" + "".join(filter(str.isdigit, str(tel)))[-10:]

# --- LÓGICA DE ACTUALIZACIÓN DE CALENDARIO ---
def marcar_evento(telefono_recibido, accion):
    try:
        service = obtener_servicio_calendar()
        ahora = datetime.utcnow().isoformat() + 'Z'
        
        # Buscamos eventos desde hoy
        eventos_result = service.events().list(calendarId='primary', timeMin=ahora,
                                               singleEvents=True, orderBy='startTime').execute()
        eventos = eventos_result.get('items', [])

        for evento in eventos:
            descripcion = evento.get('description', '')
            if telefono_recibido in descripcion:
                titulo_actual = evento.get('summary', '')
                
                # Lógica para confirmar (✅) o reagendar (❌)
                if accion == 'confirmar' and "✅" not in titulo_actual:
                    evento['summary'] = f"✅ {titulo_actual}"
                elif accion == 'reagendar' and "❌" not in titulo_actual:
                    evento['summary'] = f"❌ {titulo_actual}"
                else:
                    return False # Ya estaba marcado o no aplica

                service.events().update(calendarId='primary', eventId=evento['id'], body=evento).execute()
                return True
    except Exception as e:
        print(f"Error al actualizar calendario: {e}")
    return False

# --- RUTAS ---
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
        telefono = limpiar_telefono(msg.get('from'))
        
        if "si" in texto or "confirmar" in texto:
            marcar_evento(telefono, 'confirmar')
        elif "no" in texto or "reagendar" in texto:
            marcar_evento(telefono, 'reagendar')
            
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
