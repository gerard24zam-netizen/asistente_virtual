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
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# --- CONFIGURACIÓN ---
TELEFONO_ID_META = "1120833397777315"
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
VERIFY_TOKEN = "TOKEN_SECRETO_META" 
API_KEY_SEGURIDAD = "MiClaveSuperSecreta123" 
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- CONFIGURACIÓN SUPABASE ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

RECORDATORIOS_ACTIVOS_MEMORIA = {}

def log_debug(mensaje):
    print(f"DEBUG: {mensaje}", flush=True)

# --- GOOGLE CALENDAR ---
def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json: return None
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

calendario = obtener_servicio_calendar()

# --- FUNCIONES DE ENVÍO ---
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
        return requests.post(url, json=payload, headers=headers)
    except: return None

# --- JOB 1: RECORDATORIOS PACIENTES (RESTAURADO) ---
def job_recordatorio_pacientes():
    log_debug("Iniciando recordatorios para pacientes...")
    if not supabase or not calendario: return
    try:
        doctores = supabase.table("Doctores").select("*").execute().data
        zona_mexico = pytz.timezone('America/Mexico_City')
        ahora = datetime.datetime.now(zona_mexico)
        inicio = ahora.replace(hour=0, minute=0, second=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
        fin = ahora.replace(hour=23, minute=59, second=59).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')

        for doc in doctores:
            cal_id = doc.get("calendar_id")
            if not cal_id: continue
            eventos = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute().get('items', [])
            for e in eventos:
                desc = e.get('description', '')
                tel_match = re.search(r'\d{10}', desc)
                if tel_match:
                    p_tel = tel_match.group()
                    p_nombre = e.get('summary', 'Paciente').split('(')[0].strip()
                    enviar_mensaje(p_tel, "template", template_params=[{"type": "text", "text": p_nombre}])
                    RECORDATORIOS_ACTIVOS_MEMORIA[p_tel] = doc.get('id')
    except Exception as e: log_debug(f"Error en recordatorios pacientes: {e}")

# --- JOB 2: REPORTE DOCTOR ---
def job_enviar_reporte_doctores():
    log_debug("Ejecutando proceso de reportes para doctores...")
    if not supabase or not calendario: return
    try:
        doctores = supabase.table("Doctores").select("*").execute().data
        zona_mexico = pytz.timezone('America/Mexico_City')
        ahora_str = datetime.datetime.now(zona_mexico).strftime('%Y-%m-%d')
        
        for doc in doctores:
            # Validación robusta de fecha
            db_date = doc.get("jornada_respondida_fecha")
            log_debug(f"Validando doctor {doc.get('name')}: Fecha en DB={db_date}, Hoy={ahora_str}")
            
            if db_date == ahora_str:
                log_debug(f"Doctor {doc.get('name')} ya respondió hoy. Omitiendo.")
                continue

            cal_id = doc.get("calendar_id")
            inicio = datetime.datetime.now(zona_mexico).replace(hour=0, minute=0, second=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
            fin = datetime.datetime.now(zona_mexico).replace(hour=23, minute=59, second=59).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
            
            count = len(calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute().get('items', []))
            
            telefono_doc = "".join(filter(str.isdigit, str(doc.get("wa_link", ""))))
            if telefono_doc:
                # Envío de plantilla
                url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages"
                payload = {
                    "messaging_product": "whatsapp", "to": telefono_doc, "type": "template",
                    "template": {
                        "name": "jornada_doc", "language": {"code": "es_MX"},
                        "components": [{"type": "body", "parameters": [{"type": "text", "text": str(doc.get('name'))}, {"type": "text", "text": str(count)}]}]
                    }
                }
                requests.post(url, json=payload, headers={"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"})
    except Exception as e: log_debug(f"Error en job reportes: {e}")

# --- SCHEDULER ---
scheduler = BackgroundScheduler()
scheduler.add_job(job_recordatorio_pacientes, 'cron', hour=9, minute=0) # Ajusta tu hora
scheduler.add_job(job_enviar_reporte_doctores, 'cron', hour=7, minute=0)
scheduler.start()

# --- WEBHOOK Y LÓGICA ---
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        return request.args.get("hub.challenge") if request.args.get("hub.verify_token") == VERIFY_TOKEN else "Forbidden"
    
    data = request.get_json()
    try:
        msg = data['entry'][0]['changes'][0]['value']['messages'][0]
        tel_origen = msg.get('from')
        tipo = msg.get('type')
        ahora_str = datetime.datetime.now(pytz.timezone('America/Mexico_City')).strftime('%Y-%m-%d')
        
        if tipo == 'interactive':
            btn = msg['interactive']['button_reply']['title']
            doctores = supabase.table("Doctores").select("*").execute().data
            for doc in doctores:
                if "".join(filter(str.isdigit, str(doc.get("wa_link", "")))) == tel_origen:
                    # Actualización explícita
                    supabase.table("Doctores").update({"jornada_respondida_fecha": ahora_str}).eq("id", doc['id']).execute()
                    texto = "*Confirmado, que tenga un excelente día laboral* atte.: *Stein su Asistente Virtual*" if "Empecemos" in btn else "Tomar un descanso es bueno, que descanse, nos vemos mañana. Atte.: *Stein su Asistente Virtual*"
                    enviar_mensaje(tel_origen, "text", contenido=texto)
                    break
    except: pass
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
