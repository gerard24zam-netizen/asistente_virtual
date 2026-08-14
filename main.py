import os
import json
import re
import requests
import datetime
import pytz
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

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def log(msg):
    print(f"DEBUG: {msg}", flush=True)

def obtener_servicio_calendar():
    try:
        creds_json = os.environ.get('GOOGLE_TOKEN_JSON')
        if not creds_json:
            return None
        info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        log(f"Error calendar: {e}")
        return None

calendario = obtener_servicio_calendar()

def limpiar_telefono(tel):
    return "".join(filter(str.isdigit, str(tel)))[-10:]

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
    except Exception as e:
        log(f"Error enviando mensaje: {e}")
        return None

@app.route('/')
def home():
    return "API Activa", 200

@app.route('/ejecutar-proceso-diario', methods=['POST'])
def procesar_desde_supabase():
    if not supabase or not calendario:
        return jsonify({"error": "Falta configuración de Supabase o Google Calendar"}), 500

    try:
        response = supabase.table("Doctores").select("*").execute()
        doctores = response.data if response.data else []
    except Exception as e:
        log(f"Error consultando Supabase: {e}")
        return jsonify({"error": str(e)}), 500

    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora = datetime.datetime.now(zona_mexico)
    inicio = ahora.replace(hour=0, minute=0, second=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = ahora.replace(hour=23, minute=59, second=59).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')

    total_enviados = 0

    for doc in doctores:
        cal_id = doc.get("calendar_id") or doc.get("email")
        if not cal_id:
            continue

        doc_nombre = doc.get("name") or doc.get("nombre") or "Dr. Gerardo"
        doc_ocupacion = doc.get("ocupation") or "Atención Psicológica"

        try:
            eventos = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute().get('items', [])
        except Exception as e:
            log(f"Error leyendo calendario {cal_id}: {e}")
            continue

        for evento in eventos:
            titulo = evento.get('summary', '')
            descripcion = evento.get('description', '')
            
            if "✅" in titulo or "❌" in titulo:
                continue

            texto = f"{titulo} {descripcion}"
            digitos = "".join(filter(str.isdigit, texto))
            
            if len(digitos) >= 10:
                telefono_paciente = "52" + digitos[-10:]
                
                nombre_paciente = re.sub(r'\d+', '', titulo).strip()
                if not nombre_paciente or len(nombre_paciente) < 2:
                    nombre_paciente = "Paciente"

                start_dt = evento.get('start', {}).get('dateTime', '')
                hora_str = "10:00 am"
                if start_dt:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(start_dt).astimezone(zona_mexico)
                        hora_str = dt_obj.strftime('%I:%M %p').lower()
                    except:
                        pass

                params = [
                    {"type": "text", "text": nombre_paciente},
                    {"type": "text", "text": doc_ocupacion},
                    {"type": "text", "text": "de hoy"},
                    {"type": "text", "text": hora_str},
                    {"type": "text", "text": doc_nombre}
                ]

                resp = enviar_mensaje(telefono_paciente, "template", template_params=params)
                if resp and resp.status_code < 400:
                    total_enviados += 1
                    log(f"Recordatorio enviado a {telefono_paciente}")

    return jsonify({"status": "ok", "enviados": total_enviados}), 200

def marcar_evento_calendario(telefono_recibido, accion):
    tel_buscado = limpiar_telefono(telefono_recibido)
    if not supabase or not calendario:
        return None, None
    
    try:
        response = supabase.table("Doctores").select("*").execute()
        doctores = response.data if response.data else []
    except:
        doctores = [{"calendar_id": "gerard24zam@gmail.com", "nombre": "Dr. Gerardo", "wa_link": "https://wa.me/527226293417"}]

    zona_mexico = pytz.timezone('America/Mexico_City')
    ahora_mexico = datetime.datetime.now(zona_mexico)
    inicio = ahora_mexico.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    fin = ahora_mexico.replace(hour=23, minute=59, second=59, microsecond=0).astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
    
    simbolo = "✅" if accion == 'confirmar' else "❌"

    for doc in doctores:
        cal_id = doc.get("calendar_id") or doc.get("email")
        if not cal_id:
            continue
        try:
            eventos_result = calendario.events().list(calendarId=cal_id, timeMin=inicio, timeMax=fin, singleEvents=True).execute()
            for evento in eventos_result.get('items', []):
                titulo = evento.get('summary', '')
                descripcion = evento.get('description', '')
                texto_completo = f"{titulo} {descripcion}"
                
                if tel_buscado in limpiar_telefono(texto_completo):
                    titulo_limpio = titulo.replace(' ✅', '').replace(' ❌', '').replace('✅', '').replace('❌', '').strip()
                    nombre_paciente = re.sub(r'\d+', '', titulo_limpio).strip()
                    if not nombre_paciente or len(nombre_paciente) < 2:
                        nombre_paciente = titulo_limpio if titulo_limpio else "Paciente"

                    if simbolo in titulo:
                        return doc, nombre_paciente
                    
                    nuevo_titulo = f"{titulo_limpio} {simbolo}"
                    
                    calendario.events().patch(
                        calendarId=cal_id, 
                        eventId=evento['id'], 
                        body={'summary': nuevo_titulo}
                    ).execute()
                    log(f"¡Calendario actualizado con {simbolo} para el evento: {nuevo_titulo}!")
                    return doc, nombre_paciente
        except Exception as e:
            log(f"Error actualizando calendario {cal_id}: {e}")
    return None, None

def procesar_webhook_asincrono(data):
    try:
        val = data['entry'][0]['changes'][0]['value']
        if 'messages' in val:
            msg = val['messages'][0]
            telefono_cliente = msg.get('from')
            
            texto = ""
            if msg.get('type') == 'button':
                texto = msg.get('button', {}).get('text', '').lower()
            elif msg.get('type') == 'text':
                texto = msg.get('text', {}).get('body', '').lower()
            
            log(f"Mensaje recibido de {telefono_cliente}: {texto}")

            if any(k in texto for k in ["si", "sí", "confirmo", "confirmar"]):
                doc, nombre_paciente = marcar_evento_calendario(telefono_cliente, 'confirmar')
                if doc:
                    doc_nombre = doc.get("name") or doc.get("nombre") or "Doctor"
                    wa_link = doc.get("wa_link") or doc.get("link") or ""
                    respuesta_texto = f"Perfecto, hemos confirmado tu cita para el día de hoy con {doc_nombre}. Dudas o aclaraciones, comunícate aquí: {wa_link}"
                    enviar_mensaje(telefono_cliente, "text", contenido=respuesta_texto)
                    
                    tel_doc = "".join(filter(str.isdigit, str(wa_link)))
                    if tel_doc:
                        enviar_mensaje(tel_doc, "text", contenido=f"✅ El paciente {nombre_paciente} ha confirmado su cita de hoy.")

            elif any(k in texto for k in ["no", "reagendar", "cancelar"]):
                doc, nombre_paciente = marcar_evento_calendario(telefono_cliente, 'reagendar')
                if doc:
                    doc_nombre = doc.get("name") or doc.get("nombre") or "Doctor"
                    wa_link = doc.get("wa_link") or doc.get("link") or ""
                    respuesta_texto = f"Entendido. Para reagendar, comunícate con {doc_nombre} aquí: {wa_link}"
                    enviar_mensaje(telefono_cliente, "text", contenido=respuesta_texto)
                    
                    tel_doc = "".join(filter(str.isdigit, str(wa_link)))
                    if tel_doc:
                        enviar_mensaje(tel_doc, "text", contenido=f"❌ El paciente {nombre_paciente} indicó que necesita reagendar su cita de hoy.")
    except Exception as e:
        log(f"Error en webhook asíncrono: {e}")

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Forbidden", 403
    
    data = request.get_json()
    hilo = threading.Thread(target=procesar_webhook_asincrono, args=(data,))
    hilo.start()
    return "OK", 200

if __name__ == '__main__':
    app.run(port=5000)
