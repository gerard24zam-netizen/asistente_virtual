from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# ==========================================
# 1. CONFIGURACIONES PRINCIPALES
# ==========================================
# Debes colocar tus credenciales exactas dentro de las comillas
META_TOKEN = "EAAXdEhil3gMBR0uiujuuAvK5nqaj8A9boQQ7Yd59u0Xa8GF86XVtJl2k7EWLecDPk74CCtBbu0VH2cOIL8DW9zd4h3Mbv3sdbmReK473770t9TDfyDZCqJhomFBbxc0kSu5zgpZAy4cWMNnssZAyZB81Gb6c9dfmwfrzTYGjy6oOIc7d7Px8vTATQ9cwHKROmwZDZD"
TELEFONO_ID_META = "1120833397777315"  # El ID numérico de tu línea de WhatsApp
VERIFY_TOKEN = "TOKEN_SECRETO_META"    # El que configuraste en el panel de Meta para el Webhook
GOOGLE_WEBAPP_URL = "https://script.google.com/macros/s/AKfycbwVkPIYpllxegZaPvJACGNSSOwty5mcBxNTY_MMPgySMN-VuVjjVknRqUWYBShJPZJ3zQ/exec"  # La URL del script que actualiza el calendario

# ==========================================
# 2. FUNCIÓN: ACTUALIZAR GOOGLE CALENDAR
# ==========================================
def actualizar_calendario(telefono, estatus):
    """Envía la orden a Google para colocar la ✅ o la ❌"""
    payload = {"telefono": telefono, "estatus": estatus}
    try:
        requests.post(GOOGLE_WEBAPP_URL, json=payload, timeout=5)
    except Exception as e:
        print(f"Error conectando a Google: {e}")

# ==========================================
# 3. FUNCIÓN: ENVIAR PLANTILLA DE META
# ==========================================
def enviar_plantilla_meta(telefono_destino, nombre_plantilla):
    """confirmacion_cita"""
    url = f"https://graph.facebook.com/v17.0/{TELEFONO_ID_META}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Estructura oficial requerida por Meta
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono_destino,
        "type": "template",
        "template": {
            "name": "confirmacion_cita",
            "language": {
                "code": "es_MX"  # Ajusta a "es" si tu plantilla no está en español de México
            }
        }
    }
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"Error enviando plantilla a Meta: {e}")

# ==========================================
# 4. RUTAS DEL WEBHOOK (NÚCLEO DEL ASISTENTE)
# ==========================================

# A. Verificación del Webhook (Requisito de seguridad de Meta)
@app.route('/webhook', methods=['GET'])
def verificar_token():
    hub_mode = request.args.get('hub.mode')
    hub_verify_token = request.args.get('hub.verify_token')
    hub_challenge = request.args.get('hub.challenge')
    
    if hub_mode == 'subscribe' and hub_verify_token == VERIFY_TOKEN:
        return hub_challenge, 200
    return "Fallo de autenticacion", 403

# B. Recepción y procesamiento de respuestas del paciente
@app.route('/webhook', methods=['POST'])
def recibir_mensajes():
    try:
        body = request.get_json()
        
        # Validamos que el JSON provenga de WhatsApp
        if body.get('object'):
            if (body.get('entry') and 
                body['entry'][0].get('changes') and 
                body['entry'][0]['changes'][0].get('value') and 
                body['entry'][0]['changes'][0]['value'].get('messages')):
                
                # Extraemos la información crítica del paciente
                mensaje_info = body['entry'][0]['changes'][0]['value']['messages'][0]
                telefono_paciente = mensaje_info.get('from')
                
                # Verificamos si el paciente presionó un botón interactivo
                if mensaje_info.get('type') == 'interactive':
                    tipo_interactivo = mensaje_info['interactive'].get('type')
                    
                    if tipo_interactivo == 'button_reply':
                        # Obtenemos el ID exacto del botón que el paciente seleccionó
                        id_boton = mensaje_info['interactive']['button_reply'].get('id')
                        
                        # --- LÓGICA DE NEGOCIO ---
                        
                        # CASO 1: EL PACIENTE CONFIRMA LA CITA
                        if id_boton == "payload_confirmar": 
                            # 1. Avisamos al calendario para poner la ✅
                            actualizar_calendario(telefono_paciente, "confirmado")
                            # 2. Disparamos la plantilla preaprobada de agradecimiento/confirmación
                            enviar_plantilla_meta(telefono_paciente, "nombre_plantilla_confirmacion")
                            
                        # CASO 2: EL PACIENTE CANCELA LA CITA
                        elif id_boton == "payload_cancelar":
                            # 1. Avisamos al calendario para poner la ❌
                            actualizar_calendario(telefono_paciente, "cancelado")
                            # 2. Disparamos la plantilla de cancelación al paciente
                            enviar_plantilla_meta(telefono_paciente, "nombre_plantilla_cancelacion")

        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        print(f"Error crítico en el webhook: {e}")
        # Retornamos 200 a Meta para que no bloquee el webhook por errores internos
        return jsonify({"status": "error"}), 200

# ==========================================
# 5. RUTA PARA RECORDATORIOS AUTOMÁTICOS 
# ==========================================
@app.route('/recordatorios', methods=['POST'])
def detonar_recordatorio(): 
    # Dentro de tu def detonar_recordatorio():
enviar_plantilla_meta(telefono, "confirmacion_cita")
    try:
        data = request.get_json()
        telefono = str(data.get('telefono')).strip() # Limpiamos espacios
        
        if telefono:
            # BLINDAJE: Si el número tiene 10 dígitos, le agregamos el 52 de México
            if len(telefono) == 10:
                telefono = "52" + telefono
                
            # Disparamos la plantilla
            enviar_plantilla_meta(telefono, "AQUI_EL_NOMBRE_DE_TU_PLANTILLA")
            print(f"Intento de envío de recordatorio al: {telefono}") # Registro para logs
            
        return jsonify({"status": "recordatorio procesado"}), 200
    except Exception as e:
        print(f"Error procesando recordatorio: {e}")
        return jsonify({"status": "error"}), 500
        
if __name__ == '__main__':
    app.run(port=5000)
