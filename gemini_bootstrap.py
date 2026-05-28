import os
import sys
import subprocess
import site
import importlib

def setup_environment():
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "--user", "--break-system-packages", "google-genai"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        importlib.reload(site)
    except:
        pass

def filter_input_data(raw_text):
    """Filtert den Input, um Quota/Tokens zu sparen, genau wie in deiner Mail geplant!"""
    lines = raw_text.splitlines()
    
    # Schlüsselwörter für Stolpersteine
    keywords = ["error", "fail", "failed", "warning", "not found", "invalid", "denied", "conflict", "verletzt"]
    
    # Extrahiere nur Zeilen, die ein Schlüsselwort enthalten
    filtered_lines = [line for line in lines if any(kw in line.lower() for kw in keywords)]
    
    # Wenn Fehler gefunden wurden, nimm die letzten 30. Wenn alles sauber war, nimm die letzten 20 Zeilen vom Log.
    if filtered_lines:
        return "\n".join(filtered_lines[-30:])
    else:
        return "\n".join(lines[-20:])

def run_genai(api_key, raw_data):
    try:
        from google import genai
    except ImportError:
        print("[-] google-genai Library fehlt.")
        return
    
    client = genai.Client(api_key=api_key)
    
    # Daten intelligent kürzen vor dem Senden!
    input_data = filter_input_data(raw_data)
    
    models_to_try = [
        'models/gemini-2.0-flash',
        'models/gemini-pro-latest',
        'models/gemini-flash-latest',
        'models/gemini-2.5-flash'
    ]
    
    # Hier ist deine neue Terremis-Persönlichkeit für den Guide:
    system_instruction = (
        "Du bist der Terremis-Assistent. Analysiere diesen Pacman-, KDE- oder Code-Fehler "
        "und gib eine prägnante, verständliche Lösung für Arch Linux aus."
    )
    
    success = False
    for m_id in models_to_try:
        if success: break
        try:
            print(f"[*] Kontaktiere {m_id}...")
            res = client.models.generate_content(
                model=m_id, 
                contents=f"Log-Auszug:\n{input_data}",
                config={'system_instruction': system_instruction}
            )
            print(f"\n=== KI-INSTALLATIONSPLAN ===\n{res.text}\n")
            success = True
        except Exception as e:
            err = str(e)
            if "429" in err:
                print(f"[-] {m_id}: Quota voll (Warte kurz...).")
            else:
                print(f"[-] {m_id} fehlgeschlagen: {err[:50]}...")
            continue
    
    if not success:
        print("[-] Alle Versuche gescheitert. Bitte 30 Sek. warten (Rate Limit).")

if __name__ == "__main__":
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("[-] GEMINI_API_KEY fehlt!"); sys.exit(1)
    if not sys.stdin.isatty():
        setup_environment()
        run_genai(key, sys.stdin.read())