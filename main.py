import pytz
import sys
import re
import os
import json
import requests
import datetime
import threading
from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
from supabase import create_client

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" 
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- CONFIGURACIÓN SUPABASE ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def log_debug(mensaje):
    print(f"DEBUG: {mensaje}", flush=True)

def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json: return None
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

calendario = obtener_servicio_calendar()

# --- FUNCIONES DE EXTRACCIÓN MEJORADAS ---
def extraer_telefono_paciente(evento):
    """Limpia el texto y extrae el número de 10 dígitos de forma robusta."""
    texto = f"{evento.get('summary', '')} {evento.get('description', '')}"
    # Eliminar guiones, espacios, paréntesis, etc.
    clean_text = re.sub(r'[\s\-\(\)\+]', '', texto)
    
    # Buscar patrones: opcionalmente empieza con 52 o 521, seguido de 10 dígitos
    # Buscamos los últimos 10 dígitos después de eliminar prefijos comunes
    match = re.search(r'(?:521?)?(\d{10})', clean_text)
    if match:
        telefono = match.group(1)
        return telefono
    return None

def enviar_mensaje(telefono, tipo, contenido=None, template_params=None):
    headers = {"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"}
    url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages"
    
    if tipo == "template":
        payload = {
            "messaging_product": "whatsapp", "to": telefono, "type": "template",
            "template": {
                "name": "confirmacion_cita", "language": {"code": "es_MX"},
                "components": [{"type": "body", "parameters": template_params}]
            }
        }
    else:
        payload = {"messaging_product": "whatsapp", "to": telefono, "text": {"body": contenido}}
        
    try:
        resp = requests.post(url, json=payload, headers=headers)
        return resp
    except Exception as e:
        log_debug(f"Error en envío: {e}")
        return None

def enviar_recordatorios_a_pacientes(doc, hoy):
    cal_id = doc.get("calendar_id") or doc.get("email")
    if not cal_id: return
    
    zona_mexico = pytz.timezone('America/Mexico_City')
    inicio_mexico = datetime.datetime.now(zona_mexico).replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico = datetime.datetime.now(zona_mexico).replace(hour=23, minute=59, second=59, microsecond=0)
    
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')

    eventos = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute().get('items', [])
    
    contador = 0
    for evento in eventos:
        tel = extraer_telefono_paciente(evento)
        nombre = "Paciente" # Se puede mejorar la extracción de nombre aquí
        
        if tel and len(tel) == 10:
            params = [{"type": "text", "text": nombre}]
            resp = enviar_mensaje(tel, "template", template_params=params)
            if resp and resp.status_code in [200, 201]:
                contador += 1
                log_debug(f"✅ Enviado a {tel}")
        else:
            log_debug(f"⚠️ No se pudo extraer teléfono válido de: {evento.get('summary')}")
            
    # Notificar al doctor
    tel_doc = "".join(filter(str.isdigit, str(doc.get("wa_link", ""))))
    if tel_doc:
        enviar_mensaje(tel_doc, "text", contenido=f"📊 Se han enviado {contador} recordatorios de cita a los pacientes programados para hoy.")

# --- ENDPOINTS ---
@app.route('/disparar-reportes', methods=['POST'])
def endpoint_disparar_reportes():
    log_debug("Iniciando jornada...")
    try:
        doctores = supabase.table("Doctores").select("*").execute().data
        for doc in doctores:
            # 1. Reporte al doctor
            # ... (código previo para reporte doc)
            # 2. Recordatorios pacientes
            enviar_recordatorios_a_pacientes(doc, "")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": str(e)}), 500

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == "TOKEN_SECRETO_META": return request.args.get("hub.challenge")
        return "Forbidden", 403
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
