import os
from flask import Flask, request
import asistente_total

app = Flask(__name__)

# CONFIGURACIÓN (REEMPLAZA POR TU TOKEN REAL)
VERIFY_TOKEN = "EAAXdEhil3gMBRjKZCho9kNZBWc1IgIY0fH0FliaG2FkPj8kWIdAYthZCbkVecL0VDUYk14LBMYWbTobDTg3fC99zZAP170M5ImxwpCgFxmcDSlQNDTHnYEZCYoQsgsNVmXSOFMVzcfqny2lfCQgpa4S9EFZBvhwKmq1lzC2WrxEwxvYm9uZAMOGVJaaJ8tUEjHkUwZDZD" 

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. VERIFICACIÓN DE META (Esto arregla el error de conexión)
    if request.method == 'GET':
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Token incorrecto", 403

    # 2. PROCESAMIENTO DE MENSAJES (POST)
    if request.method == 'POST':
        data = request.json
        try:
            # Extraer info
            telefono = data['entry'][0]['changes'][0]['value']['messages'][0]['from']
            texto = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            
            # Ejecutar lógica
            service = asistente_total.obtener_servicio_google()
            asistente_total.marcar_confirmado(telefono, service, texto)
            
            return "OK", 200
        except Exception as e:
            return "Error interno", 500

if __name__ == '__main__':
    app.run()
