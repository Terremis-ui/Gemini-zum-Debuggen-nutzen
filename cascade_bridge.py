import requests
import json
import os
from google import genai

# --- KONFIGURATION ---
OLLAMA_URL = "http://10.66.66.1:11434/api/generate"
LOCAL_MODEL = "gemma2-alex"

# Neues Gemini SDK initialisieren (zieht den KEY automatisch aus os.environ["GEMINI_API_KEY"])
client = genai.Client()

def ask_local_gemma(prompt):
    """Fragt dein lokales Gemma-Modell auf dem VPS mit erhöhtem Timeout."""
    payload = {
        "model": LOCAL_MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        # Timeout auf 120 Sekunden erhöht, falls der VPS schwer schuften muss
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            return f"Fehler von Ollama: {response.status_code}"
    except requests.exceptions.Timeout:
        return "Gemma-Timeout: Die Aufgabe war zu komplex für die vorgegebene Zeit. (Eskalation einleiten)"
    except requests.exceptions.RequestException as e:
        return f"Verbindung zu Gemma fehlgeschlagen: {e}"

def ask_cloud_gemini(prompt, gemma_context=""):
    """Fragt Gemini Flash über das topaktuelle genai-SDK."""
    full_prompt = f"""
    Ein Nutzer hat eine komplexe Anfrage gestellt. Unsere lokale, kleine KI (Gemma) 
    konnte die Aufgabe nicht rechtzeitig oder vollständig lösen.
    
    Bisheriger Status von Gemma:
    ---
    {gemma_context}
    ---
    
    Bitte löse die ursprüngliche Anfrage des Nutzers umfassend und professionell.
    Ursprüngliche Anfrage: {prompt}
    """
    
    # Nutzung des neuen SDKs und des aktuellen Modells
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=full_prompt,
    )
    return response.text

def run_cascade(prompt):
    print(f"🤖 [Lokal] Sende Anfrage an {LOCAL_MODEL}...")
    gemma_response = ask_local_gemma(prompt)
    
    # Trigger-Wörter für geplante Eskalation ODER automatischer Timeout-Abfang
    trigger_words = ["großen bruder", "gemini flash", "übersteigt meine", "kapazitäten", "kaskade", "gemma-timeout"]
    needs_escalation = any(word in gemma_response.lower() for word in trigger_words)
    
    if needs_escalation:
        print("\n⚡ [Kaskade] Gemma braucht Hilfe oder Zeitüberschreitung. Eskaliere zu Gemini Flash...\n")
        cloud_response = ask_cloud_gemini(prompt, gemma_context=gemma_response)
        return cloud_response
    else:
        print("\n✅ [Lokal] Gemma hat die Anfrage direkt gelöst.\n")
        return gemma_response

import sys

# ... (Deine Funktionen ask_local_gemma, ask_cloud_gemini und run_cascade bleiben genau wie sie sind) ...

if __name__ == "__main__":
    # Prüfen, ob der Nutzer eine Frage per Argument übergeben hat
    if len(sys.argv) > 1:
        # Verbindet alle übergebenen Argumente zu einem einzigen Prompt-String
        user_prompt = " ".join(sys.argv[1:])
        print(run_cascade(user_prompt))
    else:
        print("💡 Verwendung: ask \"Deine Frage hier\"")
        print("Beispiel: ask \"Schreibe ein Python-Skript für Backups\"")
