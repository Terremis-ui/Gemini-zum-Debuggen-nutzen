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
import requests

from google import genai

# ==========================================
# TERREMIS GLOBAL CONFIG & VERSIONING
# ==========================================
VERSION = "v1.1.0_Beta"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "terremis_global_errors.json")
GITHUB_REPO_URL = "https://github.com/Terremis-ui/Gemini-zum-Debuggen-nutzen"

# --- HYBRIDE KI-KONFIGURATION ---
OLLAMA_URL = os.environ.get("OLLAMA_API_URL", "http://10.66.66.1:11434/api/generate")
LOCAL_MODEL = "gemma2-alex"

client = genai.Client()

def ask_local_gemma(prompt, system_instruction):
    """Fragt dein lokales Gemma-Modell mit schnellem Verbindungs-Timeout (Graceful Fallback)."""
    # Wir übergeben die System-Anweisung im Prompt, da Ollama-Modelle das im Basis-Prompt am besten verstehen
    full_prompt = f"System-Anweisung: {system_instruction}\n\nLog-Auszug:\n{prompt}"
    payload = {
        "model": LOCAL_MODEL,
        "prompt": full_prompt,
        "stream": False
    }
    try:
        # 2 Sekunden Connect-Timeout für Tester außerhalb deines Tunnels, 120s für die Generierung
        response = requests.post(OLLAMA_URL, json=payload, timeout=(2, 120))
        if response.status_code == 200:
            return response.json().get("response", "")
        return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        # Tester ist außerhalb deines Netzes -> Gemma wird lautlos übersprungen
        return None

def ask_cloud_gemini(model_id, prompt, system_instruction, gemma_context=""):
    """Fragt die Google Cloud an, falls Gemma Hilfe braucht oder offline ist."""
    from google.genai import types
    
    config = types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
    
    full_prompt = f"Log-Auszug:\n{prompt}"
    if gemma_context:
        full_prompt = (
            f"Unsere lokale KI (Gemma) hat folgendes Vorwissen geliefert, brauchte aber Unterstützung:\n"
            f"--- Context ---\n{gemma_context}\n---------------\n\n"
            f"Bitte optimiere und vervollständige die Lösung für den Nutzer.\n{full_prompt}"
        )
        
    res = client.models.generate_content(model=model_id, contents=full_prompt, config=config)
    return res.text

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
    
    # Wenn alles glattlief, geben wir None zurück, statt Alibi-Zeilen zu senden
    return None

def run_genai(api_key, raw_data, distro, mode):
    git_pull()
    
    # ANSI-Codes direkt bereinigen und kritische Logs filtern
    clean_raw_data = clean_ansi_codes(raw_data)
    input_data = filter_critical_logs(clean_raw_data)
    
    # Wenn input_data None ist, war das Update zu 100% erfolgreich!
    if not input_data:
        print(f"\n\033[1;32m🎉 Terremis {VERSION}: Alles sauber! Keine Fehler im Log gefunden. System läuft stabil.\033[0m")
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

    # 2. Hybride KI-Analyse für neue Fehler
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
    
    current_instruction = instructions.get(distro, "Du bist der Terremis-Assistent. Analysiere diesen Fehler.")
    
    print(f"🤖 [Lokal] Prüfe Verfügbarkeit von {LOCAL_MODEL}...")
    gemma_response = ask_local_gemma(input_data, current_instruction)
    
    final_text = ""
    
    if gemma_response:
        # Prüfen, ob Gemma eskalieren möchte
        trigger_words = ["großen bruder", "gemini flash", "übersteigt meine", "kapazitäten", "kaskade"]
        if any(word in gemma_response.lower() for word in trigger_words):
            print(f"\n⚡ [Kaskade] Gemma eskaliert zu Gemini Cloud für {distro.upper()}...\n")
            final_text = ask_cloud_gemini('gemini-2.5-flash', input_data, current_instruction, gemma_context=gemma_response)
        else:
            print(f"\n✅ [Lokal] Gemma hat die Analyse direkt gelöst.\n")
            final_text = gemma_response
    else:
        # Wenn der Tester nicht in deinem Netzwerk ist oder Gemma offline ist -> Direkt-Routing
        print("🌐 [Info] Lokale KI nicht erreichbar (Tester-Modus). Weiche aus auf Cloud-Routing...\n")
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
        
        for m_id in models_to_try:
            try:
                print(f"[*] [{VERSION}] Kontaktiere {m_id} für {distro.upper()}...")
                final_text = ask_cloud_gemini(m_id, input_data, current_instruction)
                if final_text:
                    break
            except Exception:
                continue

    if final_text:
        clean_text = final_text.replace("```bash", "\033[1;32m[BEFEHL]\033[0m").replace("```", "")
        output_buffer = (
            f"\n\033[1;33m=== TERREMIS KI ANALYSE ({VERSION} | Powered by Hybrid AI) ===\033[0m\n"
            f"\033[1;34mZiel-Distribution:\033[0m {distro.upper()}\n"
            f"------------------------------------------------\n"
            f"{clean_text}\n"
            f"\033[1;33m================================================\033[0m\n"
        )
        open_pager(output_buffer)

    # 3. Interaktives Speichern / Issue-Erstellung
    if final_text and sys.stdout.isatty():
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