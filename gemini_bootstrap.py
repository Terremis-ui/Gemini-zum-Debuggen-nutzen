import os
import sys
import subprocess
import site
import importlib
import argparse
import json
import shutil
import re
import urllib.parse
import webbrowser
import requests
import platform
from pathlib import Path
from google import genai

# ==========================================
# TERREMIS GLOBAL CONFIG & VERSIONING
# ==========================================
VERSION = "v1.2.0_Beta"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Vereint zu einer einzigen, sicheren JSON-Datenbank
DB_FILE = os.path.join(SCRIPT_DIR, "terremis_global_errors.json")
GITHUB_REPO_URL = "https://github.com/Terremis-ui/Gemini-zum-Debuggen-nutzen"

# --- HYBRIDE KI-KONFIGURATION ---
OLLAMA_URL = os.environ.get("OLLAMA_API_URL", "http://10.66.66.1:11434/api/generate")
LOCAL_MODEL = "gemma2-alex"

client = genai.Client()

def ask_local_gemma(prompt, system_instruction):
    """Fragt dein lokales Gemma-Modell mit schnellem Verbindungs-Timeout."""
    full_prompt = f"System-Anweisung: {system_instruction}\n\nLog-Auszug:\n{prompt}"
    payload = {
        "model": LOCAL_MODEL,
        "prompt": full_prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=(2, 120))
        if response.status_code == 200:
            return response.json().get("response", "")
        return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return None

def ask_cloud_gemini_stream(model_id, prompt, system_instruction, gemma_context=""):
    """Fragt die Google Cloud an und gibt die Antwort LIVE im Terminal aus (Streaming)."""
    from google.genai import types
    
    config = types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
    
    full_prompt = f"Log-Auszug:\n{prompt}"
    if gemma_context:
        full_prompt = (
            f"Unsere lokale KI (Gemma) hat folgendes Vorwissen geliefert, brauchte aber Unterstützung:\n"
            f"--- Context ---\n{gemma_context}\n---------------\n\n"
            f"Bitte optimiere und vervollständige die Lösung für den Nutzer.\n{full_prompt}"
        )
        
    print(f"\n\033[1;33m=== TERREMIS KI ANALYSE (Powered by Gemini | {VERSION} | Live Stream) ===\033[0m")
    
    full_response_text = ""
    try:
        response_stream = client.models.generate_content_stream(model=model_id, contents=full_prompt, config=config)
        for chunk in response_stream:
            if chunk.text:
                text_chunk = chunk.text.replace("```bash", "\033[1;32m[BEFEHL]\033[0m").replace("```", "")
                print(text_chunk, end="", flush=True)
                full_response_text += chunk.text
        print("\n\033[1;33m================================================\033[0m\n")
    except Exception as e:
        print(f"\n\033[1;31m[-] Fehler beim Streaming von {model_id}: {e}\033[0m\n")
        return None

    return full_response_text


def detect_os():
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    return line.split("=")[1].strip().strip('"').lower()
    if os.path.exists("/etc/arch-release"):
        return "arch"
    elif os.path.exists("/etc/debian_version"):
        return "debian"
    return "unknown"


def sanitize_config(content: str) -> str:
    # Schwärzt alles wie EXPORT GEMINI_API_KEY="AIzaSy...", PASSWORD="...", etc.
    patterns = [
        r"(?i)(api[_-]?key|token|secret|password|passphrase|auth|key|gpg|luks)\s*[:=]\s*[\"']?[^\"'\s\n]+[\"']?",
        r"AIzaSy[a-zA-Z0-9_-]{33}",  # Spezifisches Muster für Google API Keys
    ]

    sanitized = content
    for pattern in patterns:
        sanitized = re.sub(
            pattern, r"\1=[REDACTED]", sanitized, flags=re.IGNORECASE
        )

    return sanitized


def collect_system_configs():
    target_files = [
        "/etc/os-release",
        "/etc/mkinitcpio.conf",
        "/etc/pacman.conf",
    ]

    config_summary = []
    for file_path in target_files:
        p = Path(file_path)
        if p.exists() and p.is_file():
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")

                # 1. Kommentare & Leerzeilen filtern
                lines = [
                    line
                    for line in content.splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                clean_text = "\n".join(lines[:30])

                # 2. Sicherheitshalber ALLES Schwärzen, was nach Keys aussieht
                safe_text = sanitize_config(clean_text)

                config_summary.append(f"=== {p.name} ===\n{safe_text}")
            except Exception:
                pass

    return "\n\n".join(config_summary)

def clean_ansi_codes(text):
    """Filtert alle \u001b[...m und Steuerzeichen sauber heraus."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)

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

def load_error_db():
    """Lädt das Archiv atomar und fängt JSON-Fehler ab."""
    target_path = Path(DB_FILE)
    if not target_path.exists() or target_path.stat().st_size == 0:
        return {}
    try:
        with open(target_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("[!] Datenbank beschädigt. Versuche Backup zu laden...")
        bak_path = target_path.with_suffix('.json.bak')
        if bak_path.exists():
            shutil.copy2(bak_path, target_path)
            with open(target_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

def save_error_db_safely(data):
    """Speichert die Fehlerdatenbank atomar mit automatischem Backup."""
    target_path = Path(DB_FILE)
    backup_path = target_path.with_suffix('.json.bak')
    temp_path = target_path.with_suffix('.json.tmp')
    
    try:
        if target_path.exists():
            shutil.copy2(target_path, backup_path)
        
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        os.replace(temp_path, target_path)
    except Exception as e:
        print(f"[❌] Kritischer Fehler beim Speichern der DB: {e}")
        if backup_path.exists():
            shutil.copy2(backup_path, target_path)
            print("[✓] Altes Backup wurde wiederhergestellt.")

def clean_error_message(msg):
    """Kürzt riesige, wiederkehrende Log-Ketten (wie den Firejail/Widevine-Block)."""
    msg = msg.strip()
    
    # Erkennt sich wiederholende Firejail/Chrome-Meldungen im selben Block
    if "archfirejail" in msg and "libwidevinecdm.so" in msg:
        return "archfirejail: ERROR: media/cdm/cdm_module.cc - libwidevinecdm.so: Kann die Shared-Object-Datei nicht öffnen: Die Operation ist nicht erlaubt"
        
    if len(msg) > 200:
        return msg[:197] + "..."
    return msg

def git_push_update():
    """Pusht Änderungen ins GitHub-Repo (Nur via SSH)."""
    try:
        status = subprocess.run(["git", "-C", SCRIPT_DIR, "status", "--porcelain", DB_FILE], capture_output=True, text=True)
        if not status.stdout.strip():
            print("[*] Keine Änderungen am Wissensarchiv festgestellt. Push übersprungen.")
            return

        print(f"[*] Terremis {VERSION}: Pushe Updates zu GitHub...")
        subprocess.run(["git", "-C", SCRIPT_DIR, "add", DB_FILE], check=True)
        subprocess.run(["git", "-C", SCRIPT_DIR, "commit", "-m", f"chore: update fehler-counter/fixes im archiv ({VERSION})"], check=True)
        
        subprocess.run(
            ["git", "-C", SCRIPT_DIR, "push"],  
            env={"GIT_SSH_COMMAND": "ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"},  
            check=True
        )
        print("\033[1;32m[✓] Erfolgreich weltweit auf GitHub gepusht!\033[0m")
    except Exception as e:
        print(f"\033[1;31m[-] Git Push fehlgeschlagen: {e}\033[0m")

def filter_critical_logs(raw_terminal_output):
    critical_lines = []
    keywords = ["error", "fail", "failed", "warning", "not found", "invalid", "denied", "conflict", "verletzt", "panic", "segfault", "broken", "fehler", "e:"]
    
    for line in raw_terminal_output.splitlines():
        if "stable cli interface" in line.lower():
            continue
            
        if any(kw in line.lower() for kw in keywords):
            critical_lines.append(line)
            
    if critical_lines:
        return "\n".join(critical_lines[-30:])
    return None

def open_pager(text):
    print(text)

def run_genai(api_key, raw_data, distro, mode):
    git_pull()
    
    clean_raw_data = clean_ansi_codes(raw_data)
    input_data = filter_critical_logs(clean_raw_data)
    
    if not input_data:
        print(f"\n\033[1;32m🎉 Terremis {VERSION}: Alles sauber! Keine Fehler im Log gefunden. System läuft stabil.\033[0m")
        return
    
    db = load_error_db()
    
    # JETZT NEU: Nutzt die Bereinigungsfunktion, um den JSON-Key sauber zu halten!
    error_key = clean_error_message(input_data)
    
    # --- ZÄHLER-LOGIK START ---
    if error_key not in db:
        db[error_key] = {}
        
    if distro not in db[error_key]:
        db[error_key][distro] = {
            "comment_de": "Bisher nicht dokumentiert.",
            "comment_en": "Not documented yet.",
            "counter": 0
        }
    
    if "counter" not in db[error_key][distro]:
        db[error_key][distro]["counter"] = 0
        
    db[error_key][distro]["counter"] += 1
    current_count = db[error_key][distro]["counter"]
    
    print(f"\n\033[1;36m[*] Terremis Statistik: Dieser Fehler trat auf {distro.upper()} bereits {current_count}x auf.\033[0m")
    # --- ZÄHLER-LOGIK ENDE ---

    # 1. Bekannten Fehler aus Archiv laden
    if db[error_key][distro].get("comment_de") != "Bisher nicht dokumentiert.":
        print(f"\n\033[1;32m[✓] Bekannter Fehler im globalen Terremis-Archiv gefunden!\033[0m")
        if mode == "dev":
            comment = db[error_key][distro].get("comment_en", "No English translation available.")
            title = f"TERREMIS GLOBAL KNOWLEDGE ARCHIVE ({VERSION} | DEVELOPER EN)"
        else:
            comment = db[error_key][distro].get("comment_de", "Keine deutsche Übersetzung vorhanden.")
            title = f"TERREMIS GLOBALES WISSENSARCHIV ({VERSION} | TESTER DE)"
            
        output_buffer = (
            f"\n\033[1;33m=== {title} ===\033[0m\n"
            f"\033[1;34mZiel-Distribution:\033[0m {distro.upper()} | \033[1;36mHäufigkeit:\033[0m {current_count}x\n"
            f"------------------------------------------------\n"
            f"\033[1;31mLog-Auszug:\033[0m\n{input_data}\n\n"
            f"\033[1;32mFIX / COMMENT:\033[0m\n{comment}\n"
            f"\033[1;33m================================================\033[0m\n"
        )
        open_pager(output_buffer)
        
        save_error_db_safely(db)
        if os.path.exists(os.path.expanduser("~/.ssh/id_rsa")) or os.path.exists(os.path.expanduser("~/.ssh/id_ed25519")):
            git_push_update()
        return

    # 2. Hybride KI-Analyse für neue Fehler
    instructions = {
        "arch": "Du bist der Terremis-Assistent. Analysiere diesen Fehler und gib eine prägnante Lösung für Arch Linux aus.",
        "gentoo": "Du bist der Terremis-Assistent. Analysiere das Problem und gib eine optimierte Gentoo Hardened Lösung aus.",
        "ubuntu": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine schnelle Lösung für Ubuntu aus.",
        "debian": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine stabile Lösung für Debian aus.",
        "debian-testing": "Du bist der Terremis-Assistent. Analysiere den Fehler für Debian Testing/Unstable. Achte auf Paket-Sperren.",
        "mint": "Du bist der Terremis-Assistent. Analysiere den Fehler für Linux Mint.",
        "opensuse": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine Lösung für openSUSE aus.",
        "fedora": "Du bist der Terremis-Assistent. Analysiere den Fehler und gib eine moderne Lösung für Fedora aus."
    }
    
    base_instruction = instructions.get(distro, "Du bist der Terremis-Assistent. Analysiere diesen Fehler.")
    current_instruction = f"{base_instruction} Hinweis für den Kontext: Dieser Fehler trat auf diesem System-Typ bereits {current_count}-mal auf."
    
    print(f"🤖 [Lokal] Prüfe Verfügbarkeit von {LOCAL_MODEL}...")
    gemma_response = ask_local_gemma(input_data, current_instruction)
    
    final_text = ""
    
    if gemma_response:
        trigger_words = ["großen bruder", "gemini flash", "übersteigt meine", "kapazitäten", "kaskade"]
        if any(word in gemma_response.lower() for word in trigger_words):
            print(f"\n⚡ [Kaskade] Gemma eskaliert zu Gemini Cloud for {distro.upper()}...\n")
            final_text = ask_cloud_gemini_stream('gemini-2.5-flash', input_data, current_instruction, gemma_context=gemma_response)
        else:
            print(f"\n✅ [Lokal] Gemma hat die Analyse direkt gelöst.\n")
            final_text = gemma_response
            clean_text = final_text.replace("```bash", "\033[1;32m[BEFEHL]\033[0m").replace("```", "")
            print(f"\n\033[1;33m=== TERREMIS KI ANALYSE (Lokal) ===\033[0m\n{clean_text}\n\033[1;33m===================================\033[0m\n")
    else:
        print("🌐 [Info] Lokale KI nicht erreichbar. Weiche aus auf Cloud-Streaming...\n")
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-3.6-flash', 'gemini-3.5-flash-lite']
        
        for m_id in models_to_try:
            final_text = ask_cloud_gemini_stream(m_id, input_data, current_instruction)
            if final_text:
                break

    # 3. Interaktives Speichern / JSON Update
    if final_text and sys.stdout.isatty():
        try:
            with open("/dev/tty", "r") as tty:
                print("\n\033[1;36m[?] Fehler-Lösung im globalen Repository dokumentieren? (j/n):\033[0m ", end="", flush=True)
                if tty.readline().strip().lower() == 'j':
                    
                    print("\033[1;32m-> [DE] Deutscher Kommentar für das Archiv:\033[0m")
                    comment_de = tty.readline().strip()
                    
                    print("\033[1;34m-> [EN] English comment for Developers:\033[0m")
                    comment_en = tty.readline().strip()
                    
                    db[error_key][distro]["comment_de"] = comment_de if comment_de else "Keine deutsche Beschreibung."
                    db[error_key][distro]["comment_en"] = comment_en if comment_en else "No English description."
                    
                    save_error_db_safely(db)
                    
                    if os.path.exists(os.path.expanduser("~/.ssh/id_rsa")) or os.path.exists(os.path.expanduser("~/.ssh/id_ed25519")):
                        git_push_update()
                    else:
                        print("[*] Tester-Modus: JSON lokal aktualisiert (Counter +1). Kein Push-Recht.")
                else:
                    save_error_db_safely(db)
                    
        except Exception as e:
            print(f"[-] Fehler bei der Eingabe/Speicherung: {e}")
    else:
        # Falls via Pipe ausgeführt (nicht-interaktiv): Speichere zumindest den neuen Zähler ab!
        save_error_db_safely(db)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Terremis Hybrid AI Bootstrapper")
    parser.add_argument("--distro", type=str, default="arch", help="Ziel-Distribution (default: arch)")
    parser.add_argument("--mode", type=str, default="tester", help="Modus: dev oder tester (default: tester)")
    args = parser.parse_args()
    
    api_key = os.environ.get("GEMINI_API_KEY")
    raw_data = sys.stdin.read()  # Erst hier kommen die Daten rein!
    
    # 1. Automatisch OS, Kernel & Configs erfassen
    detected_os = detect_os()
    kernel_version = platform.release()
    configs = collect_system_configs()
    
    # System-Kontext zusammenbauen
    full_payload = f"[System: {detected_os} | Kernel: {kernel_version}]\n[Configs:\n{configs}]\n\n{raw_data}"
    
    # Optional: Nutze das erkannte OS als Fallback, falls kein --distro übergeben wurde
    active_distro = args.distro if args.distro != "arch" else detected_os
    
    # 2. Jetzt die Logik ausführen (mit full_payload statt nur raw_data)
    run_genai(api_key, full_payload, active_distro, args.mode)