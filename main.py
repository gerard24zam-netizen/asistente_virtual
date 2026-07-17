from flask import Flask, request, jsonify
import requests
import datetime
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META"

# Configuración de Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'credentials.json' # Asegúrate de que este archivo esté en tu carpeta raíz

def obtener_servicio_calendar():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

def limpiar_telefono(tel):
    return "52" + "".join(filter(str.isdigit, str(tel)))[-10:]

def marcar_confirmado(telefono_recibido):
    service = obtener_servicio_calendar()
    # Buscamos eventos de hoy
    ahora = datetime.datetime.utcnow().isoformat() + 'Z'
    eventos_result = service.events().list(calendarId='primary', timeMin=ahora,
                                           singleEvents=True, orderBy='startTime').execute()
    eventos = eventos_result.get('items', [])

    for evento in eventos:
        # Asumimos que el teléfono está en la descripción o título. 
        # Ajusta esto si el teléfono está en otro campo.
        descripcion = evento.get('description', '')
        if telefono_recibido in descripcion:
            titulo_actual = evento.get('summary', '')
            if "✅" not in titulo_actual:
                evento['summary'] = f"✅ {titulo_actual}"
                service.events().update(calendarId='primary', eventId=evento['id'], body=evento).execute()
                return True
    return False

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    # Extraer mensaje
    try:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        telefono = msg.get('from')[-10:]
        texto = msg.get('text', {}).get('body', '').lower()
        
        if "si" in texto or "confirmar" in texto:
            if marcar_confirmado(telefono):
                print(f"Éxito: Cita confirmada para {telefono}")
            else:
                print(f"Error: No se encontró cita para {telefono}")
    except Exception as e:
        print(f"Error en Webhook: {e}")
        
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
