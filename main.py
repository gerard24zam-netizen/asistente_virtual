from flask import Flask, request
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN ---
DOCTOR_PHONE_NUMBER = "5217226293417" # Número del doctor
URL_GOOGLE_WEBAPP = "https://script.google.com/macros/s/AKfycbwVkPIYpllxegZaPvJACGNSSOwty5mcBxNTY_MMPgySMN-VuVjjVknRqUWYBShJPZJ3zQ/exec" # URL de Google

# --- 1. LÓGICA DE CALENDARIO (Con la limpieza de strings para evitar errores) ---
def actualizar_google_calendar(telefono, estatus):
    # Estatus esperado: "confirmado" o "cancelado"
    # Esto prepara el título para Google Apps Script
    payload = {
        "telefono": telefono, # El sistema limpiará los números allá
        "estatus": estatus    # Esto permite que Google ponga ✅ o ❌
    }
    try:
        response = requests.post(URL_GOOGLE_WEBAPP, json=payload)
        return response.status_code
    except Exception as e:
        print(f"Error conectando a Calendar: {e}")
        return None

# --- 2. LÓGICA DE NOTIFICACIÓN AL DOCTOR ---
def notificar_al_doctor(nombre_paciente, telefono, estatus):
    mensaje = f"🔔 *Notificación de Cita*\n\nPaciente: {nombre_paciente}\nTel: {telefono}\nRespondió: *{estatus.upper()}*"
    # AQUÍ DEBE IR TU LÓGICA DE ENVÍO DE WHATSAPP (Meta API)
    # Ejemplo: enviar_mensaje_meta(DOCTOR_PHONE_NUMBER, mensaje)
    print(f"Enviando notificación: {mensaje}")

# --- 3. WEBHOOK PRINCIPAL (Procesador de respuestas de Meta) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    
    # Aquí va la lógica que ya tienes para interpretar la respuesta del paciente
    # (Lo que ya tienes hecho para detectar si dio clic en "Confirmar" o "Cancelar")
    # Ejemplo de extracción (debes asegurar que coincida con tu JSON actual):
    nombre_paciente = data.get('nombre') 
    telefono = data.get('telefono')
    estatus = data.get('estatus') # Debe ser "confirmado" o "cancelado"
    
    # --- PROCESAMIENTO INTEGRAL ---
    
    # A. Actualizar Google Calendar (con la palomita o equis)
    actualizar_google_calendar(telefono, estatus)
    
    # B. Notificar al doctor (la nueva función)
    notificar_al_doctor(nombre_paciente, telefono, estatus)
    
    # C. (Opcional) Aquí tu lógica para enviar un mensaje de confirmación 
    # de vuelta al paciente usando tu plantilla aprobada de Meta
    # enviar_plantilla_meta(telefono, "confirmacion_cita")
    
    return "ok", 200

if __name__ == '__main__':
    app.run(port=5000)
