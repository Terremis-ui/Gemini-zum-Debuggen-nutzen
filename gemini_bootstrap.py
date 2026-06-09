import os
import sys
import subprocess
import site
import importlib
import argparse

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
    """Filtert den Input, um Quota/Tokens zu sparen!"""
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

def run_genai(api_key, raw_data, distro):
    try:
        from google import genai
    except ImportError:
        print("[-] google-genai Library fehlt.")
        return
    
    client = genai.Client(api_key=api_key)
    
    # Daten intelligent kürzen vor dem Senden!
    input_data = filter_input_data(raw_data)
    
    # Aktuelle Wunsch-Modelle im neuen SDK
    models_to_try = [
        'models/gemini-2.0-flash',
        'models/gemini-pro-latest',
        'models/gemini-flash-latest',
        'models/gemini-2.5-flash'
    ]
    
    # Dynamische System-Instructions für die "Big Six"
    instructions = {
        "arch": "Du bist der Terremis-Assistent. Analysiere diesen Pacman-, KDE- oder Code-Fehler und gib eine prägnante, verständliche Lösung für Arch Linux aus.",
        "gentoo": "Du bist der Terremis-Assistent. Analysiere das Portage- oder Systemproblem und gib eine optimierte Gentoo Hardened Installationsanweisung aus.",
        "ubuntu": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine prägnante, schnelle Lösung für Ubuntu und den Paketmanager apt aus.",
        "debian": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine stabile, sichere Lösung für Debian GNU/Linux und den Paketmanager apt aus.",
        "opensuse": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine Lösung für openSUSE und den Paketmanager zypper unter Berücksichtigung der Sicherheitsstandards aus.",
        "fedora": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine prägnante, moderne Lösung für Fedora und den Paketmanager dnf aus."
    }
    
    system_instruction = instructions[distro]
    
    success = False
    for m_id in models_to_try:
        if success: break
        try:
            print(f"[*] Kontaktiere {m_id} für {distro.upper()}...")
            res = client.models.generate_content(
                model=m_id, 
                contents=f"Log-Auszug:\n{input_data}",
                config={'system_instruction': system_instruction}
            )
            # Hier ist das Branding! 😉
            print(f"\n=== TERREMIS KI ANALYSE (Powered by Gemini) ===")
            print(f"Ziel-Distribution: {distro.upper()}")
            print("------------------------------------------------")
            print(res.text)
            print("================================================")
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
    # Argument-Parser für die Distro-Auswahl
    parser = argparse.ArgumentParser(description="Terremis Gemini CLI Debugger")
    parser.add_argument(
        "--distro", 
        default="arch", 
        choices=["arch", "gentoo", "ubuntu", "debian", "opensuse", "fedora"], 
        help="Wähle deine Linux-Distribution für maßgeschneiderte Lösungen (Standard: arch)"
    )
    args, unknown = parser.parse_known_args()

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("[-] GEMINI_API_KEY fehlt!"); sys.exit(1)
        
    if not sys.stdin.isatty():
        setup_environment()
        run_genai(key, sys.stdin.read(), args.distro)