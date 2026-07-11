# Terremis Gemini CLI Debugger (v1.2.0_Beta)

Ein universelles Python-Skript, um Systemfehler, Logdateien oder Paketmanager-Probleme mithilfe der Gemini-API direkt im Terminal zu analysieren. 

*Ursprünglich für eine Gentoo Hardened Live-ISO entwickelt, unterstützt das Tool jetzt die wichtigsten Distributionen über ein einfaches Argument und verfügt über eine intelligente, lokale Fehler-Statistik.*

## 💡 Tipp für die Hosentasche
Am einfachsten ist es, die `gemini_bootstrap.py` direkt mit auf einen **Multiboot-USB-Stick** (z. B. mit Ventoy) zu packen. So hast du das Skript bei jeder Rettungs- oder Installations-ISO sofort griffbereit.

---

## 🔧 Voraussetzungen & Einrichtung

1. **API-Key erstellen:** Hol dir einen kostenlosen API-Key im [Google AI Studio](https://aistudio.google.com/).
2. **Key dauerhaft hinterlegen:** Setze den Key in deiner `~/.bashrc`, damit er immer geladen ist:
   ```bash
   export GEMINI_API_KEY="DEIN_API_KEY_HIER"
   ```

🚀 Nutzung & Argumente
Du kannst jeden beliebigen Befehl, Log oder Fehler-Output über eine Pipe direkt an das Skript übergeben. Standardmäßig filtert Terremis kosmetisches Rauschen (wie bekannte apt-CLI-Warnungen) automatisch heraus und schlägt nur bei echten Fehlern an.

Best Practice: Der update-Alias
Um dein System-Update vollautomatisch abzusichern, empfiehlt es sich, einen Alias in der ~/.bashrc anzulegen. Durch tee /dev/tty siehst du den normalen Output live, während Terremis im Hintergrund aufpasst.

Für Arch Linux:
```bash 
alias update='sudo pacman -Syu 2>&1 | tee /dev/tty | python3 ~/Dokumente/GitHub/Gemini-zum-Debuggen-nutzen/gemini_bootstrap.py --distro arch'
```

Für Debian GNU/Linux:
```bash 
alias update='sudo apt-get update 2>&1 | tee /dev/tty | python3 ~/Gemini-zum-Debuggen-nutzen/gemini_bootstrap.py --distro debian && sudo apt-get dist-upgrade -y 2>&1 | tee /dev/tty | python3 ~/Gemini-zum-Debuggen-nutzen/gemini_bootstrap.py --distro debian'
```
Passe die Pfade für dein System an. 


🎛️ Die "Big Six" Support-Argumente
Wenn du eine andere Distribution reparierst, hänge einfach das passende --distro Argument hinten an:

Gentoo Hardened: dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro gentoo

Debian / Linux Mint: dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro debian

Arch Linux: dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro arch

openSUSE: dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro opensuse

Ubuntu: dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro ubuntu

Fedora: dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro fedora

🧪 Beta-Features
📊 Hybrider Modus & Fehler-Statistik
Terremis versucht im Hintergrund zuerst, eine lokale Instanz über Ollama (gemma2-alex) zu erreichen. Schlägt dies fehl, schaltet das System automatisch und unterbrechungsfrei auf die Cloud-API um. Bekannte Fehler werden in der terremis_global_errors.json registriert und mit einem Zähler versehen.

🇩🇪 Normaler Tester (Deutsche Ausgabe):
```bash 
cat log.txt | python3 gemini_bootstrap.py --distro arch --mode tester
```
Gibt eine deutsche Erklärung aus und zeigt den Titel TERREMIS GLOBALES WISSENSARCHIV (TESTER DE).

🇺🇸 Entwickler-Modus (Englische Ausgabe):
```bash 
cat log.txt | python3 gemini_bootstrap.py --distro arch --mode dev
```
Schaltet um auf DEVELOPER EN und liefert die englische Analyse – ideal für das direkte Erstellen von GitHub-Issues oder zum Debuggen im Quellcode.


