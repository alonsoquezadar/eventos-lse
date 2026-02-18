import os.path
import base64
import email # <--- La librería clave para el nuevo enfoque
import json
import re # Para limpiar el HTML
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import google.generativeai as genai

# CONFIGURACIÓN
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
REMITENTE = "a.a.quezada@lse.ac.uk"

def obtener_newsletter_robusto():
    print("🚀 [PASO 1] Iniciando autenticación...")
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    print("🚀 [PASO 2] Conectando con Gmail...")
    service = build('gmail', 'v1', credentials=creds)
    
    query = f"from:{REMITENTE}"
    print(f"  - Buscando último correo de {REMITENTE}...")
    results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
    messages = results.get('messages', [])

    if not messages:
        print("  - ❌ No se encontró nada.")
        return None

    print("🚀 [PASO 3] Descargando y procesando el correo (Enfoque RAW)...")
    
    # 1. Pedimos el formato RAW en lugar de FULL
    msg_id = messages[0]['id']
    msg_raw = service.users().messages().get(userId='me', id=msg_id, format='raw').execute()
    
    # 2. Decodificamos de forma segura manejando el padding
    msg_bytes = base64.urlsafe_b64decode(msg_raw['raw'].encode('ASCII'))
    
    # 3. Usamos la librería nativa de Python para analizar el correo
    mime_msg = email.message_from_bytes(msg_bytes)
    
    cuerpo = ""
    # msg.walk() recorre todas las partes del correo sin romper el código
    for part in mime_msg.walk():
        content_type = part.get_content_type()
        if content_type == 'text/plain':
            cuerpo = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            break # Si encontramos texto plano, paramos. Es lo más limpio.
        elif content_type == 'text/html':
            # Si solo hay HTML, lo guardamos pero seguimos buscando por si hay texto plano
            cuerpo = part.get_payload(decode=True).decode('utf-8', errors='ignore')

    print(f"  - ✅ Extracción exitosa. Limpiando código HTML...")
    
    # Limpiamos las etiquetas HTML (<br>, <div>, etc.) para que la IA lea solo texto
    texto_limpio = re.sub('<[^<]+>', ' ', cuerpo)
    # Reemplazamos múltiples espacios por uno solo
    texto_limpio = re.sub(' +', ' ', texto_limpio).strip()
    
    return texto_limpio

def procesar_ia_robusto(texto):
    print(f"🚀 [PASO 4] Enviando texto limpio a Gemini AI ({len(texto)} caracteres)...")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Extrae los eventos académicos del siguiente texto. 
    Devuelve ÚNICAMENTE un array JSON válido con las claves: titulo, fecha, hora, lugar, link.
    Texto: {texto[:10000]}
    """
    
    try:
        start_time = time.time()
        response = model.generate_content(prompt)
        print(f"  - IA respondió en {round(time.time() - start_time, 2)} segundos.")
        
        json_limpio = response.text.strip().removeprefix('```json').removesuffix('```').strip()
        
        # Validamos que sea JSON real antes de guardarlo
        datos_json = json.loads(json_limpio)
        
        with open('eventos_lse.json', 'w', encoding='utf-8') as f:
            json.dump(datos_json, f, indent=4, ensure_ascii=False)
            
        print("✅ PROCESO COMPLETADO EXITOSAMENTE.")
        print("Datos guardados en 'eventos_lse.json'.")
        
    except json.JSONDecodeError:
        print("❌ Error: La IA no devolvió un JSON válido. Respuesta cruda:")
        print(response.text)
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    content = obtener_newsletter_robusto()
    if content:
        procesar_ia_robusto(content)
