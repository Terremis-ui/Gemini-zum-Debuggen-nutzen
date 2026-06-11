import os
import sys
import subprocess
import site
import importlib
import argparse
import pydoc
import json

# ==========================================
# TERREMIS GLOBAL CONFIG & VERSIONING
# ==========================================
VERSION = "v1.0.1_Beta"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "terremis_global_errors.json")

def setup_environment():
    try:
        # Installiert das NEUE Google GenAI SDK, falls es fehlt
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "--user", "--break-system-packages", "google-genai"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        importlib.reload(site)
    except:
        pass

def git_pull():
    """Holt die neuesten Fehler-Kommentare der Community vor der Analyse."""
    try:
        # Auch beim Pull erlauben wir SSH ohne interaktive Abfrage
        subprocess.run(["git", "-C", SCRIPT_DIR, "pull"], env={"GIT_SSH_COMMAND": "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

def git_push_update():
    """Pusht den neuen Fehler-Fix sofort ins GitHub-Repo."""
    try:
        print(f"[*] Terremis {VERSION}: Synchronisiere mit GitHub...")
        subprocess.run(["git", "-C", SCRIPT_DIR, "add", DB_FILE], check=True)
        subprocess.run(["git", "-C", SCRIPT_DIR, "commit", "-m", f"chore: neuer Fehler-Fix im Wissensarchiv ({VERSION})"], check=True)
        
        # Der sichere Push über SSH ohne Blockieren!
        subprocess.run(["git", "-C", SCRIPT_DIR, "push"], env={"GIT_SSH_COMMAND": "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"}, check=True)
        
        print("\033[1;32m[✓] Erfolgreich weltweit auf GitHub gepusht!\033[0m")
    except Exception as e:
        print(f"\033[1;31m[-] Git Push fehlgeschlagen: {e}\033[0m")

def filter_critical_logs(raw_terminal_output):
    critical_lines = []
    keywords = ["error", "fail", "failed", "warning", "not found", "invalid", "denied", "conflict", "verletzt", "panic", "segfault", "broken", "fehler"]
    
    for line in raw_terminal_output.splitlines():
        if any(kw in line.lower() for kw in keywords):
            critical_lines.append(line)
            
    if critical_lines:
        return "\n".join(critical_lines[-30:])
    else:
        return "\n".join(raw_terminal_output.splitlines()[-20:])

def run_genai(api_key, raw_data, distro, mode):
    # Vorab-Sync der Community-Datenbank
    git_pull()
    
    input_data = filter_critical_logs(raw_data)
    if not input_data.strip():
        print(f"🎉 Terremis {VERSION}: Alles sauber! Keine kritischen Fehler gefunden.")
        return
    
    db = load_error_db()
    error_key = "".join(input_data.split())
    
    # Prüfen, ob der Fehler bereits im globalen Archiv existiert
    if error_key in db and distro in db[error_key]:
        print(f"\n\033[1;32m[✓] Fehler im globalen Terremis-Archiv gefunden!\033[0m")
        
        if mode == "dev":
            comment = db[error_key][distro].get("comment_en", "No English translation available.")
            title = f"TERREMIS GLOBAL KNOWLEDGE ARCHIVE ({VERSION} | DEVELOPER EN)"
        else:
            comment = db[error_key][distro].get("comment_de", "Keine deutsche Übersetzung vorhanden.")
            title = f"TERREMIS GLOBALES WISSENSARCHIV ({VERSION} | TESTER DE)"
            
        output_buffer = (
            f"\n\033[1;33m=== {title} ===\033[0m\n"
            f"\033[1;34mZiel-Distribution:\033[0m {distro.upper()}\n"
            f"------------------------------------------------\n"
            f"\033[1;31mLog-Auszug:\033[0m\n{input_data}\n\n"
            f"\033[1;32mFIX / COMMENT:\033[0m\n{comment}\n"
            f"\033[1;33m================================================\033[0m\n"
        )
        pydoc.pipepager(output_buffer, cmd='less -R')
        return

    # Ab zu Gemini, falls der Fehler neu ist
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("[-] google-genai Library fehlt.")
        return
    
    client = genai.Client(api_key=api_key)
    models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    
    instructions = {
        "arch": "Du bist der Terremis-Assistent. Analysiere diesen Fehler und gib eine prägnante Lösung für Arch Linux aus.",
        "gentoo": "Du bist der Terremis-Assistent. Analysiere das Problem und gib eine optimierte Gentoo Hardened Lösung aus.",
        "ubuntu": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine schnelle Lösung für Ubuntu aus.",
        "debian": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine stabile Lösung für Debian aus.",
        "opensuse": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine Lösung für openSUSE aus.",
        "fedora": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine moderne Lösung für Fedora aus."
    }
    
    config = types.GenerateContentConfig(system_instruction=instructions[distro], temperature=0.2)
    success = False
    
    for m_id in models_to_try:
        if success: break
        try:
            print(f"[*] [{VERSION}] Kontaktiere {m_id} für {distro.upper()}...")
            res = client.models.generate_content(model=m_id, contents=f"Log-Auszug:\n{input_data}", config=config)
            
            clean_text = res.text.replace("```bash", "\033[1;32m[BEFEHL]\033[0m").replace("```", "")
            output_buffer = (
                f"\n\033[1;33m=== TERREMIS KI ANALYSE ({VERSION} | Powered by Gemini) ===\033[0m\n"
                f"\033[1;34mZiel-Distribution:\033[0m {distro.upper()}\n"
                f"------------------------------------------------\n"
                f"{clean_text}\n"
                f"\033[1;33m================================================\033[0m\n"
            )
            # Wir zwingen 'less', die Tastatur direkt von /dev/tty zu lesen, damit das Scrollen trotz Pipe klappt!
            if sys.stdout.isatty():
                pydoc.pipepager(output_buffer, cmd='less -R < /dev/tty')
            else:
                print(output_buffer)
            success = True
        except Exception as e:
            continue
    
    # Zweisprachiges Eintragen und Git-Push
    if success and sys.stdout.isatty():
        try:
            with open("/dev/tty", "r") as tty:
                print("\n\033[1;36m[?] Neuen Fehler im globalen Repository speichern? (j/n):\033[0m ", end="", flush=True)
                choice = tty.readline().strip().lower()
                
                if choice == 'j':
                    # WICHTIG: Wir holen uns die Kommentare ohne Puffer-Schluckauf
                    print("\033[1;32m-> [DE] Deutscher Kommentar für Tester:\033[0m")
                    comment_de = tty.readline().strip()
                    
                    print("\033[1;34m-> [EN] English comment for Developers:\033[0m")
                    comment_en = tty.readline().strip()
                    
                    # Nur speichern, wenn auch wirklich Text eingegeben wurde!
                    if comment_de or comment_en:
                        if error_key not in db:
                            db[error_key] = {}
                        
                        db[error_key][distro] = {
                            "comment_de": comment_de if comment_de else "Keine Beschreibung hinterlegt.",
                            "comment_en": comment_en if comment_en else "No description available."
                        }
                        
                        save_error_db(db)
                        git_push_update()
        except Exception as e:
            print(f"[-] Fehler bei der Eingabe: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Terremis Gemini CLI Debugger {VERSION}")
    parser.add_argument("--distro", default="arch", choices=["arch", "gentoo", "ubuntu", "debian", "opensuse", "fedora"])
    parser.add_argument("--mode", default="tester", choices=["tester", "dev"], help="Wähle 'tester' für DE oder 'dev' für EN Ausgaben")
    args, unknown = parser.parse_known_args()

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print(f"\033[1;31m[-] Terremis {VERSION}: GEMINI_API_KEY fehlt!\033[0m")
        sys.exit(1)
        
    if not sys.stdin.isatty():
        setup_environment()
        run_genai(key, sys.stdin.read(), args.distro, args.mode)
    else:
        print(f"\033[1;36m[*] Terremis CLI-Debugger {VERSION} bereit.\033[0m")
        print("Anwendung: dmesg | python3 gemini_bootstrap.py")