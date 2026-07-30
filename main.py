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

# --- CONFIGURACIÓN SUPABASE & SAAS ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

CONTACTOS_DOCTORES = {
    "default": {
        "nombre": "Psic. Gerardo Zamora",
        "wa_link": "https://wa.me/527226293417",
        "ocupation": "Atención Psicológica"
    }
}

def log_debug(mensaje):
    """Función para forzar que los prints salgan en los logs de Gunicorn/Render al instante"""
    print(f"DEBUG: {mensaje}", flush=True)

def get_doctor_data(doctor_id="default"):
    if supabase:
        try:
            log_debug(f"Consultando Supabase para el doctor_id: '{doctor_id}'")
            response = supabase.table("Doctores").select("*").eq("id", doctor_id).execute()
            if response.data and len(response.data) > 0:
                row = response.data[0]
                log_debug(f"¡Doctor encontrado en Supabase!: {row}")
                return {
                    "nombre": row.get("name") or row.get("nombre", "Psic. Gerardo Zamora"),
                    "wa_link": row.get("wa_link") or row.get("link", "https://wa.me/527226293417"),
                    "ocupation": row.get("ocupation", "Atención Psicológica")
                }
            else:
                log_debug(f"No se encontró el ID '{doctor_id}' en la tabla Doctores de Supabase. Usando respaldo.")
        except Exception as e:
            log_debug(f"Error crítico consultando Supabase: {e}")
    
    log_debug(f"Usando respaldo local para ID: '{doctor_id}'")
    return CONTACTOS_DOCTORES.get(doctor_id, CONTACTOS_DOCTORES["default"])

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
        payload = {
            "messaging_product": "whatsapp", "to": telefono, "text": {"body": contenido}
        }
        
    try:
        resp = requests.post(url, json=payload, headers=headers)
        log_debug(f"Mensaje enviado a {telefono}. Status: {resp.status_code}")
        if resp.status_code >= 400:
            log_debug(f"Respuesta de error de Meta: {resp.text}")
        return resp
    except Exception as e:
        log_debug(f"Excepción al enviar mensaje a Meta: {e}")
        return None

def obtener_servicio_calendar():
    creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
    if not creds_json: raise ValueError("Error: No se encontró la variable GOOGLE_CREDENTIALS")
    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=creds)

calendario = obtener_servicio_calendar()

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))[-10:]

def marcar_evento(telefono_recibido, accion):
    tel_buscado = limpiar_telefono(telefono_recibido)
    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio_mexico = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0)
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    
    simbolo = "✅" if accion == 'confirmar' else "❌"
    
    doctores_registrados = []
    if supabase:
        try:
            res = supabase.table("Doctores").select("*").execute()
            if res.data:
                doctores_registrados = res.data
        except Exception as e:
            log_debug(f"Error obteniendo lista de doctores para marcar evento: {e}")
            
    if not doctores_registrados:
        doctores_registrados = [{
            "id": "default",
            "calendar_id": "gerard24zam@gmail.com"
        }]
        
    for doc in doctores_registrados:
        cal_id = doc.get("calendar_id") or doc.get("email") or "gerard24zam@gmail.com"
        doc_id_actual = doc.get("id", "default")
        
        try:
            eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin).execute()
            eventos = eventos_result.get('items', [])
            
            for evento in eventos:
                titulo = evento.get('summary', '')
                descripcion = evento.get('description', '')
                descripcion_sin_emails = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', descripcion)
                texto_completo = f"{titulo} {descripcion_sin_emails}"
                numeros_en_evento = limpiar_telefono(texto_completo)
                
                if tel_buscado in numeros_en_evento:
                    log_debug(f"Cita encontrada en el calendario '{cal_id}' perteneciente al doctor_id: '{doc_id_actual}'")
                    if simbolo in titulo: 
                        return doc_id_actual
                    nuevo_titulo = f"{titulo.replace(' ✅', '').replace(' ❌', '').strip()} {simbolo}"
                    evento['summary'] = nuevo_titulo
                    calendario.events().update(calendarId=cal_id, eventId=evento['id'], body=evento).execute()
                    log_debug(f"Evento actualizado exitosamente en el calendario de: {cal_id}")
                    return doc_id_actual
        except Exception as e:
            log_debug(f"No se pudo revisar o actualizar el calendario {cal_id}: {e}")
            
    log_debug("No se encontró coincidencia del teléfono en ningún calendario, usando ID por defecto.")
    return "default"

def notificar_resumen_doctor(doc_id):
    log_debug(f"Iniciando notificación de resumen para doctor_id: '{doc_id}'")
    doc_row = None
    if supabase:
        try:
            res = supabase.table("Doctores").select("*").eq("id", doc_id).execute()
            if res.data:
                doc_row = res.data[0]
        except Exception as e:
            log_debug(f"Error obteniendo datos del doctor para resumen: {e}")
    
    if not doc_row:
        wa_link = CONTACTOS_DOCTORES.get("default", {}).get("wa_link", "https://wa.me/527226293417")
        cal_id = "gerard24zam@gmail.com"
    else:
        wa_link = doc_row.get("wa_link") or doc_row.get("link", "https://wa.me/527226293417")
        cal_id = doc_row.get("calendar_id") or doc_row.get("email") or "gerard24zam@gmail.com"
    
    tel_doctor = "".join(filter(str.isdigit, str(wa_link)))
    if not tel_doctor:
        log_debug("El teléfono del doctor está vacío, no se puede enviar resumen.")
        return

    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio_mexico = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_mexico = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0)
    inicio = inicio_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = fin_mexico.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')

    try:
        eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin).execute()
        eventos = eventos_result.get('items', [])
        
        confirmados = []
        cancelados = []

        for evento in eventos:
            titulo = evento.get('summary', '')
            start_dt = evento.get('start', {}).get('dateTime', '')
            hora_str = ""
            if start_dt:
                try:
                    dt_obj = datetime.datetime.fromisoformat(start_dt).astimezone(zona_mexico)
                    hora_str = dt_obj.strftime('%H:%M')
                except:
                    pass
            
            nombre_paciente = titulo.replace('✅', '').replace('❌', '').strip()

            if '✅' in titulo:
                confirmados.append(f"- {nombre_paciente} a las {hora_str} hrs")
            elif '❌' in titulo:
                cancelados.append(f"- {nombre_paciente} a las {hora_str} hrs")

        mensaje = f"📊 *Actualización de agenda (Resumen)*:\n\n"
        mensaje += f"✅ *Confirmados ({len(confirmados)}):*\n"
        if confirmados:
            mensaje += "\n".join(confirmados) + "\n"
        else:
            mensaje += "Ninguno aún\n"
        
        mensaje += f"\n❌ *Cancelados / Reagendados ({len(cancelados)}):*\n"
        if cancelados:
            mensaje += "\n".join(cancelados)
        else:
            mensaje += "Ninguno"

        enviar_mensaje(tel_doctor, "text", contenido=mensaje)
    except Exception as e:
        log_debug(f"Error al armar o enviar resumen al doctor: {e}")

@app.route('/')
def home():
    return "Bot de citas multi-tenant activo y funcionando correctamente", 200

@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio():
    data = request.get_json()
    tel_limpio = "".join(filter(str.isdigit, str(data.get('telefono'))))
    telefono = "52" + tel_limpio if len(tel_limpio) == 10 else tel_limpio
    
    doctor_id = data.get('doctor_id', 'default')
    doc_data = get_doctor_data(doctor_id)
    
    params = [
        {"type": "text", "text": data.get('nombre')},
        {"type": "text", "text": doc_data.get('ocupation')},
        {"type": "text", "text": data.get('fecha')},
        {"type": "text", "text": data.get('hora')},
        {"type": "text", "text": doc_data.get('nombre')}
    ]
    
    enviar_mensaje(telefono, "template", template_params=params)
    return jsonify({"status": 200})

def procesar_webhook_asincrono(data):
    try:
        if 'messages' in data['entry'][0]['changes'][0]['value']:
            msg = data['entry'][0]['changes'][0]['value']['messages'][0]
            telefono_cliente = msg.get('from')
            texto = msg.get('button', {}).get('text', '').lower() if msg.get('type'] == 'button' else msg.get('text', {}).get('body', '').lower()

            log_debug(f"Mensaje recibido de cliente {telefono_cliente}: '{texto}'")

            if "si" in texto or "confirmo" in texto:
                doc_id_encontrado = marcar_evento(telefono_cliente, 'confirmar')
                doc = get_doctor_data(doc_id_encontrado)
                
                texto_confirmacion = f"Perfecto, hemos confirmado tu cita para el día de hoy con {doc['nombre']}. Dudas o aclaraciones, comunícate aquí: {doc['wa_link']}"
                enviar_mensaje(telefono_cliente, "text", contenido=texto_confirmacion)
                
                notificar_resumen_doctor(doc_id_encontrado)
                
            elif "no" in texto or "reagendar" in texto:
                doc_id_encontrado = marcar_evento(telefono_cliente, 'reagendar')
                doc = get_doctor_data(doc_id_encontrado)
                
                texto_reagendar = f"Entendido. Para reagendar, comunícate con {doc['nombre']} aquí: {doc['wa_link']}"
                enviar_mensaje(telefono_cliente, "text", contenido=texto_reagendar)
                
                notificar_resumen_doctor(doc_id_encontrado)
    except Exception as e:
        log_debug(f"Error crítico en proceso asíncrono de webhook: {e}")

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    
    # Lanzamos el hilo y respondemos inmediatamente a Meta
    hilo = threading.Thread(target=procesar_webhook_asincrono, args=(data,))
    hilo.start()
    
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
