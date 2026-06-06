import requests


# Estos datos los sacaremos de la página de Meta
TOKEN = "EAAXdEhil3gMBRbI9ZBYC10vz23ZCcm1ZAvJDxbVDazdibLt2t4zGJoLvZCmucZAFPmezb9msLw2rI6sWLBUcYHHU3H1w0Emrd7DmQ8uZAJsGDrV00ac8LBwWUhOX49ZBuDdR8aKl2AoemdGCJiCev6Sxo2fo4cXBB5GXjRnZCxDWdzkmgQEGRZCNEFvfQCSxrewZDZD"
PHONE_ID = "1120833397777315"

def enviar_confirmacion_pro(telefono, nombre_paciente, hora_cita):
    url = f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
  # Configuración para tu plantilla aprobada
    data = {
        "messaging_product": "whatsapp",
        "to": f"52{telefono}",
        "type": "template",
        "template": {
            "name": "confirmacion_cita", # El nombre exacto que pusiste en el portal
            "language": { "code": "es_MX" },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": nombre_paciente}, # Llena el {{1}}
                        {"type": "text", "text": "mañana"},         # Llena el {{2}}
                        {"type": "text", "text": hora_cita}       # Llena el {{3}}
                    ]
                }
            ]
        }
    }
    
    response = requests.post(url, headers=headers, json=data)
    print(f"Respuesta de Meta: {response.status_code}")
if __name__ == "__main__":
    # Esto solo corre si ejecutas "python confirmador.py" directamente
    # Sirve como una prueba rápida manual
    print("Ejecutando prueba manual estática...")
    enviar_confirmacion_pro("4435403890", "Gera", "10:00 AM")