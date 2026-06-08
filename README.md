# Gemini-zum-Debuggen-nutzen "Arch Linux"

Ein kleines Python-Skript, um Systemfehler, Logdateien oder Paketmanager-Probleme mithilfe der Gemini-API direkt im Terminal zu analysieren. Ursprünglich war das Tool dafür gedacht, optimale Gentoo-Installationsanweisungen auszugeben, weshalb es auch direkt in einer Live-ISO erfolgreich getestet wurde.

## Voraussetzungen & Einrichtung

1. **API-Key erstellen:** Hol dir einen kostenlosen API-Key im [Google AI Studio](https://aistudio.google.com/).
2. **Key exportieren:** Setze den Key in deinem Terminal als Umgebungsvariable:
```bash
   export GEMINI_API_KEY="DEIN_API_KEY_HIER"
```
Alternativ kannst du den Key auch direkt im Python-Skript in der Zeile key = os.getenv("GEMINI_API_KEY") hinterlegen.

# Beispiel für die Konsole (leitet Standard- und Fehler-Output weiter):
dein_befehl 2>&1 | python3 ~/Downloads/gemini_bootstrap.py

Anpassung für andere Distributionen
Das Skript ist aktuell für Arch Linux optimiert. Wenn du eine andere Distribution (wie Ubuntu, Fedora etc.) nutzt, passe einfach im Quellcode die system_instruction an:

system_instruction = (
    "Du bist der Terremis-Assistent. Analysiere diesen Pacman-, KDE- oder Code-Fehler "
    "und gib eine prägnante, verständliche Lösung für Arch Linux aus."
)
