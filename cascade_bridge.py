import sys
import requests
import json
import os
import select
from google import genai

# --- KONFIGURATION ---
OLLAMA_URL = "http://10.66.66.1:11434/api/generate"
LOCAL_MODEL = "gemma2-alex"

# Neues Gemini SDK initialisieren
client = genai.Client()

def ask_local_gemma(prompt):
    """Fragt dein lokales Gemma-Modell mit scharfgestelltem Log-Analyse-Prompt."""
    
    system_instruction = """Du bist Terremis, ein präziser Log-Analyst für Arch Linux.

    AUFGABE:
    Analysiere das übergebene Log und fasse das Ergebnis kurz zusammen.

    REGELN:
    - Wenn du Fehler, Warnungen oder abgebrochene Dienste findest: Erkläre in 2-3 Sätzen die Ursache und betroffene Komponente. Nenne keine Paketnamen zum Installieren, es sei denn, sie stehen wörtlich im Log.
    - Wenn das Log fehlerfrei ist: Sag einfach kurz in deinen eigenen Worten, dass alles sauber gelaufen ist.
    - Antworte direkt auf Deutsch, ohne Meta-Überschriften oder Prompt-Regeln zu wiederholen."""

    payload = {
        "model": LOCAL_MODEL,
        "system": system_instruction,
        "prompt": prompt,
        "stream": False
    }
    try:
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
    full_prompt = f"""Du bist Gemini Flash, der große Bruder im Kaskaden-System.
Gemma konnte dieses Log nicht lösen oder brauchte Hilfe.
Gemma-Kontext: {gemma_context}

Bitte löse die ursprüngliche Anfrage des Nutzers umfassend und professionell.
Ursprüngliche Anfrage: {prompt}"""

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=full_prompt,
    )
    return response.text

def run_cascade(prompt):
    print(f"🤖 [Lokal] Sende Anfrage an {LOCAL_MODEL}...\n")
    gemma_response = ask_local_gemma(prompt)
    
    trigger_words = ["großen bruder", "gemini flash", "übersteigt meine", "kapazitäten", "kaskade", "gemma-timeout"]
    needs_escalation = any(word in gemma_response.lower() for word in trigger_words)
    
    if needs_escalation:
        print("⚡ [Kaskade] Gemma braucht Hilfe oder Zeitüberschreitung. Eskaliere zu Gemini Flash...\n")
        cloud_response = ask_cloud_gemini(prompt, gemma_context=gemma_response)
        return cloud_response
    else:
        print("✅ [Lokal] Gemma hat die Anfrage direkt gelöst.\n")
        return gemma_response

if __name__ == "__main__":
    pipe_data = ""
    # Liest STDIN aus, wenn Daten reingepiped werden (ohne isatty-Sperre)
    if not sys.stdin.isatty():
        pipe_data = sys.stdin.read().strip()

    user_args = " ".join(sys.argv[1:]).strip()

    if pipe_data and user_args:
        prompt = f"{user_args}\n\nLog-Inhalt:\n{pipe_data}"
        print(run_cascade(prompt))
    elif pipe_data:
        prompt = f"Analysiere folgendes Log:\n{pipe_data}"
        print(run_cascade(prompt))
    elif user_args:
        print(run_cascade(user_args))
    else:
        print("💡 Verwendung: ask \"Deine Frage\" oder journalctl -n 20 | ask")