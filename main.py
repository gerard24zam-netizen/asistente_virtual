import pytz
import sys
import re
import os
import json
import requests
import datetime
from flask import Flask, request, jsonify
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" 
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- INICIALIZACIÓN ---
def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json:
        raise ValueError("Error: No se encontró la variable GOOGLE_CREDENTIALS")
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

# Inicializamos el calendario globalmente para usarlo en marcar_evento
calendario = obtener_servicio_calendar()

def limpiar_telefono(tel):
    # Estandariza a 10 dígitos (últimos 10 números del string)
    return "".join(filter(str.isdigit, str(tel)))[-10:]

# --- LÓGICA DE ACTUALIZACIÓN ---
import pytz # Asegúrate de tener esta librería

def marcar_evento(telefono_recibido, accion):
    tel_buscado = limpiar_telefono(telefono_recibido)
    print(f"DEBUG: Buscando cita para el teléfono: {tel_buscado}")
    
    # 1. Definir la zona horaria de México
    zona_mexico = pytz.timezone('America/Mexico_City')
    
    # 2. Obtener el inicio y fin del día en hora México
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio_mexico = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0)
    
    # 3. Convertir a UTC (formato ISO con 'Z') para Google Calendar
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    
    print(f"DEBUG: Buscando eventos hoy en México entre {inicio} y {fin}")
    
    eventos_result = calendario.events().list(calendarId='primary', timeMin=inicio, timeMax=fin).execute()
    eventos = eventos_result.get('items', [])
    
    if not eventos:
        print("DEBUG: ¡No se encontraron eventos hoy en el calendario de México!")
        return False
        
    for evento in eventos:
        titulo = evento.get('summary', '')
        titulo_limpio = limpiar_telefono(titulo)
        
        if tel_buscado in titulo_limpio:
            if "✅" in titulo:
                print("DEBUG: El evento ya estaba marcado.")
                return True
                
            nuevo_titulo = f"{titulo.replace(' ✅', '').replace(' ❌', '')} ✅"
            evento['summary'] = nuevo_titulo
            calendario.events().update(calendarId='primary', eventId=evento['id'], body=evento).execute()
            print("DEBUG: Evento actualizado exitosamente con hora México.")
            return True
            
    print("DEBUG: Ningún evento coincidió con el teléfono en el rango horario de México.")
    return False
# --- RUTAS ---

@app.route('/debug_calendarios', methods=['GET'])
def debug_calendarios():
    # Esta función imprimirá los nombres y IDs de todos tus calendarios
    lista = calendario.calendarList().list().execute()
    items = lista.get('items', [])
    resultado = ""
    for cal in items:
        resultado += f"Nombre: {cal.get('summary')} | ID: {cal.get('id')}\n"
    print(f"DEBUG: LISTA DE CALENDARIOS:\n{resultado}")
    return resultado

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    telefono = data.get('telefono') # Ya no limpiamos aquí, asumimos formato E.164
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
    print(f"DATOS RECIBIDOS: {data}")
    sys.stdout.flush()

    # Lógica de detección de mensajes
    if 'messages' in data['entry'][0]['changes'][0]['value']:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        msg_type = msg.get('type')
        telefono_cliente = msg.get('from')
        texto = ""

        if msg_type == 'text':
            texto = msg.get('text', {}).get('body', '').lower()
        elif msg_type == 'button':
            texto = msg.get('button', {}).get('text', '').lower()

        if "si" in texto or "confirmo" in texto:
            print(f"DEBUG: Usuario confirmó: {telefono_cliente}")
            marcar_evento(telefono_cliente, 'confirmar')

    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
