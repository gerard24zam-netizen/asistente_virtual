from flask import Flask, request
import asistente_total # Asumo que aquí tienes tu lógica de Google

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def webhook():
    # 1. Si es GET, es una prueba de conexión (Salud del servidor)
    if request.method == 'GET':
        return 'Servidor Activo', 200

    # 2. Si es POST, es un mensaje de WhatsApp
    if request.method == 'POST':
        data = request.get_json()
        
        # Aquí extraemos los datos básicos (ajusta según la estructura de tu JSON)
        try:
            # Ejemplo: capturar teléfono y texto del botón/mensaje
            telefono = data['entry'][0]['changes'][0]['value']['messages'][0]['from']
            texto = data['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']
            
            # Llamamos a tu lógica de Google que ya tenías
            service = asistente_total.obtener_servicio_google()
            asistente_total.marcar_confirmado(telefono, service, texto)
            
            return 'Procesado', 200
        except Exception as e:
            print(f"Error procesando el mensaje: {e}")
            return 'Error', 500

if __name__ == '__main__':
    app.run(port=5000)
