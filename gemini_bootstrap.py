import os
import sys
import subprocess
import site
import importlib
import argparse
import json
import re
import urllib.parse
import webbrowser

# ==========================================
# TERREMIS GLOBAL CONFIG & VERSIONING
# ==========================================
VERSION = "v1.1.0_Beta"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "terremis_global_errors.json")
GITHUB_REPO_URL = "https://github.com/Terremis-ui/Gemini-zum-Debuggen-nutzen"

def clean_ansi_codes(text):
    """Filtert alle \u001b[...m und Steuerzeichen sauber heraus."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def setup_environment():
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "--user", "--break-system-packages", "google-genai"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        importlib.reload(site)
    except:
        pass

def git_pull():
    """Holt die neuesten Fehler-Kommentare anonym via HTTPS."""
    try:
        print(f"[*] Terremis {VERSION}: Synchronisiere globales Wissensarchiv...")
        subprocess.run(
            ["git", "-C", SCRIPT_DIR, "pull", "origin", "main"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            timeout=10
        )
    except:
        print("[*] Offline-Modus: Lokale Wissensdatenbank wird verwendet.")

def git_push_update():
    """Pusht Änderungen ins GitHub-Repo (Nur für dich als Dev via SSH)."""
    try:
        status = subprocess.run(["git", "-C", SCRIPT_DIR, "status", "--porcelain", DB_FILE], capture_output=True, text=True)
        if not status.stdout.strip():
            print("[*] Keine Änderungen am Wissensarchiv festgestellt. Push übersprungen.")
            return

        print(f"[*] Terremis {VERSION}: Pushe Updates zu GitHub...")
        subprocess.run(["git", "-C", SCRIPT_DIR, "add", DB_FILE], check=True)
        subprocess.run(["git", "-C", SCRIPT_DIR, "commit", "-m", f"chore: neuer Fehler-Fix im Wissensarchiv ({VERSION})"], check=True)
        
        subprocess.run(
            ["git", "-C", SCRIPT_DIR, "push"], 
            env={"GIT_SSH_COMMAND": "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"}, 
            check=True
        )
        print("\033[1;32m[✓] Erfolgreich weltweit auf GitHub gepusht!\033[0m")
    except Exception as e:
        print(f"\033[1;31m[-] Git Push fehlgeschlagen (Vermutlich Tester-Modus ohne SSH-Key): {e}\033[0m")

def load_error_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_error_db(db):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[-] Fehler beim Speichern der Datenbank: {e}")

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

def open_pager(text):
    if sys.stdout.isatty():
        try:
            with open("/dev/tty", "r") as tty:
                subprocess.run(["less", "-R"], input=text, text=True, stdin=tty)
        except:
            print(text)
    else:
        print(text)

def create_github_issue(error_log, comment_de, comment_en, distro):
    """Erstellt einen vorausgefüllten GitHub-Issue-Link für Tester."""
    issue_title = f"[Terremis Error] Neuer Fehler in {distro.upper()}"
    issue_body = (
        f"### Terremis Debugger Report ({VERSION})\n\n"
        f"**Distribution:** {distro.upper()}\n\n"
        f"#### Kritischer Log-Auszug:\n"
        f"```text\n{error_log}\n```\n\n"
        f"#### Vorgeschlagene Beschreibung (DE):\n> {comment_de}\n\n"
        f"#### Suggested Description (EN):\n> {comment_en}\n"
    )
    
    # URL-safe encoden
    title_encoded = urllib.parse.quote(issue_title)
    body_encoded = urllib.parse.quote(issue_body)
    
    url = f"{GITHUB_REPO_URL}/issues/new?title={title_encoded}&body={body_encoded}"
    
    print("\n\033[1;36m[*] Öffne GitHub im Browser, um den Issue zu erstellen...\033[0m")
    webbrowser.open(url)

def optimize_error_db(api_key):
    """Liest die JSON-Datenbank ein und lässt Gemini das Format optimieren."""
    db = load_error_db()
    if not db:
        print("[-] Datenbank leer oder nicht gefunden.")
        return

    print(f"[*] Starte globale Optimierung der Datenbank mit Gemini...")
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    
    system_instruction = (
        "Du bist ein Datenbank-Optimierer für das Terremis-Archiv. "
        "Erhalte einen Fehler-Eintrag und strukturiere ihn in sauberes JSON. "
        "Ergänze fehlende Übersetzungen (DE/EN), korrigiere Rechtschreibfehler "
        "und extrahiere falls möglich einen konkreten Befehl als 'suggested_fix'."
    )
    config = types.GenerateContentConfig(
        system_instruction=system_instruction, 
        temperature=0.1,
        response_mime_type="application/json"
    )

    optimized_db = {}
    for error_hash, distros in db.items():
        optimized_db[error_hash] = {}
        for distro, data in distros.items():
            print(f"[*] Optimiere Eintrag für {distro}...")
            prompt = f"Strukturiere diesen Eintrag: {json.dumps(data)}"
            try:
                res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
                optimized_db[error_hash][distro] = json.loads(res.text)
            except Exception as e:
                print(f"[-] Fehler bei Eintrag {error_hash}: {e}")
                optimized_db[error_hash][distro] = data

    save_error_db(optimized_db)
    print("\033[1;32m[✓] Datenbank erfolgreich optimiert und sauber formatiert!\033[0m")

def run_genai(api_key, raw_data, distro, mode):
    git_pull()
    
    # ANSI-Codes direkt bereinigen und kritische Logs filtern
    clean_raw_data = clean_ansi_codes(raw_data)
    input_data = filter_critical_logs(clean_raw_data)
    
    if not input_data.strip():
        print(f"🎉 Terremis {VERSION}: Alles sauber! Keine kritischen Fehler gefunden.")
        return
    
    db = load_error_db()
    error_key = "".join(input_data.split())
    
    # 1. Bekannten Fehler aus Archiv laden
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
        open_pager(output_buffer)
        return

    # 2. KI-Analyse für neue Fehler
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
        "debian-testing": "Du bist der Terremis-Assistent. Analysiere den Fehler für Debian Testing/Unstable (Rolling). Achte auf Paket-Sperren oder unvollständige Abhängigkeiten.",
        "mint": "Du bist der Terremis-Assistent. Analysiere den Fehler für Linux Mint. Berücksichtige die Ubuntu/Debian-Basis und die Cinnamon/MATE-Desktop-Umgebung.",
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
            open_pager(output_buffer)
            success = True
        except Exception as e:
            continue

    # 3. Interaktives Speichern / Issue-Erstellung
    if success and sys.stdout.isatty():
        try:
            with open("/dev/tty", "r") as tty:
                print("\n\033[1;36m[?] Neuen Fehler im globalen Repository melden/speichern? (j/n):\033[0m ", end="", flush=True)
                if tty.readline().strip().lower() == 'j':
                    
                    print("\033[1;32m-> [DE] Deutscher Kommentar für das Archiv/Issue:\033[0m")
                    comment_de = tty.readline().strip()
                    
                    print("\033[1;34m-> [EN] English comment for Developers:\033[0m")
                    comment_en = tty.readline().strip()
                    
                    # Wenn DU es ausführst (SSH vorhanden), direkt in DB speichern und pushen
                    if os.path.exists(os.path.expanduser("~/.ssh/id_rsa")) or os.path.exists(os.path.expanduser("~/.ssh/id_ed25519")):
                        if comment_de or comment_en:
                            if error_key not in db:
                                db[error_key] = {}
                            db[error_key][distro] = {
                                "comment_de": comment_de if comment_de else "Keine deutsche Beschreibung.",
                                "comment_en": comment_en if comment_en else "No English description."
                            }
                            save_error_db(db)
                            git_push_update()
                    else:
                        # Wenn ein TESTER es ausführt, ab zu GitHub Issues!
                        create_github_issue(input_data, comment_de, comment_en, distro)
                        
        except Exception as e:
            print(f"[-] Fehler bei der Eingabe: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Terremis Gemini CLI Debugger {VERSION}")
    parser.add_argument("--distro", default="arch", choices=["arch", "gentoo", "ubuntu", "debian","debian-testing", "mint", "opensuse", "fedora"])
    parser.add_argument("--mode", default="tester", choices=["tester", "dev"], help="Wähle 'tester' für DE oder 'dev' für EN Ausgaben")
    parser.add_argument("--optimize", action="store_true", help="Optimiert und bereinigt die globale JSON-Datenbank")
    args, unknown = parser.parse_known_args()

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print(f"\033[1;31m[-] Terremis {VERSION}: GEMINI_API_KEY fehlt!\033[0m")
        sys.exit(1)
        
    if args.optimize:
        optimize_environment = True
        setup_environment()
        optimize_error_db(key)
        sys.exit(0)
        
    if not sys.stdin.isatty():
        setup_environment()
        run_genai(key, sys.stdin.read(), args.distro, args.mode)
    else:
        print(f"\033[1;36m[*] Terremis CLI-Debugger {VERSION} bereit.\033[0m")
        print("Anwendung: dmesg | python3 gemini_bootstrap.py")