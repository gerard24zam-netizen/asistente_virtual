import datetime
from googleapiclient.discovery import build

# --- CREDENCIALES DE GOOGLE ---
# (Mantén tu código actual aquí, no lo borres. Solo asegúrate de que retorne el 'service')
def obtener_servicio_google():
    # ... tu código de token_dict, scopes, creds ...
    pass # Quita este 'pass' y asegúrate de que termine con: return build('calendar', 'v3', credentials=creds)

# --- FUNCIONES AUXILIARES ---
def limpiar_telefono(tel):
    # Extrae solo los números para evitar errores por espacios o guiones
    return "".join(filter(str.isdigit, str(tel)))

# --- MOTOR PRINCIPAL DE ACTUALIZACIÓN ---
def marcar_confirmado(telefono_recibido, service, respuesta_texto):
    
    # 1. IDENTIFICAR LA RESPUESTA (Compatible con los botones de Meta)
    texto_limpio = respuesta_texto.strip().lower()
    emoji = None
    
    # Usamos palabras clave para ignorar el acento de "Sí" y el punto final "."
    if "confirm" in texto_limpio:
        emoji = "✅"
    elif "reagendar" in texto_limpio:
        emoji = "❌"
    
    if not emoji:
        print(f"Respuesta ignorada (no es confirmación ni reagenda): {respuesta_texto}")
        return

    # 2. BUSCAR LA CITA EN EL CALENDARIO
    tel_buscado = limpiar_telefono(telefono_recibido)
    
    # IMPORTANTE PARA LA APP: Buscamos desde las 00:00 hrs de hoy. 
    # Así, si confirman tarde, el sistema sigue encontrando la cita de la mañana.
    hoy_inicio = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
    
    # NOTA FUTURA PARA MULTI-DOCTOR: 'primary' cambiará dinámicamente al ID del doctor
    eventos_result = service.events().list(
        calendarId='primary', 
        timeMin=hoy_inicio, 
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    eventos = eventos_result.get('items', [])

    # 3. PROCESAR Y ACTUALIZAR
    for event in eventos:
        titulo_actual = event.get('summary', '')
        titulo_limpio = limpiar_telefono(titulo_actual)
        
        # Si el teléfono del paciente está dentro del título del evento
        if tel_buscado in titulo_limpio and tel_buscado != "":
            
            # Limpiamos el título quitando emojis anteriores por si el paciente cambia de opinión
            titulo_base = titulo_actual.replace("✅", "").replace("❌", "").strip()
            
            # Construimos el nuevo título con el estado actualizado
            nuevo_titulo = f"{emoji} {titulo_base}"
            event['summary'] = nuevo_titulo
            
            # Ejecutamos el guardado en Google Calendar
            service.events().update(
                calendarId='primary', 
                eventId=event['id'], 
                body=event
            ).execute()
            
            print(f"ÉXITO: Cita actualizada a -> {nuevo_titulo}")
            print(f"LINK EXACTO DEL EVENTO: {event.get('htmlLink')}")
            return # Terminamos el proceso tras la primera coincidencia exitosa
            
    print(f"Alerta: No se encontró ninguna cita hoy para el teléfono {tel_buscado}")
