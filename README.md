# Terremis Gemini CLI Debugger

Ein universelles Python-Skript, um Systemfehler, Logdateien oder Paketmanager-Probleme mithilfe der Gemini-API direkt im Terminal zu analysieren. 

*Ursprünglich für eine Gentoo Hardened Live-ISO entwickelt, unterstützt das Tool jetzt die sechs wichtigsten Distributionen über ein einfaches Argument.*

## Tipp für die Hosentasche
Am einfachsten ist es, die `gemini_bootstrap.py` direkt mit auf einen **Multiboot-USB-Stick** (z. B. mit Ventoy) zu packen. So hast du das Skript bei jeder Rettungs- oder Installations-ISO sofort griffbereit.

## Voraussetzungen & Einrichtung

1. **API-Key erstellen:** Hol dir einen kostenlosen API-Key im [Google AI Studio](https://aistudio.google.com/).
2. **Key exportieren:** Setze den Key in deinem Terminal als Umgebungsvariable:
   ```bash
   export GEMINI_API_KEY="DEIN_API_KEY_HIER"
   ``` 
Nutzung & Argumente
Du kannst jeden beliebigen Befehl oder Fehler-Output über eine Pipe direkt an das Skript übergeben. Standardmäßig ist das Skript auf Arch Linux eingestellt.

# Standard-Nutzung (für Arch Linux):
dein_befehl 2>&1 | python3 gemini_bootstrap.py

Die "Big Six" Support-Argumente
Wenn du eine andere Distribution nutzt, hänge einfach das passende --distro Argument hinten an:

# Für Gentoo Hardened:
```bash
dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro gentoo
```

# Für Debian GNU/Linux:
```bash
dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro debian
```

# Für openSUSE:
```bash
dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro opensuse
```

# Für Ubuntu:
```bash
dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro ubuntu
```

# Für Fedora:
```bash
dein_befehl 2>&1 | python3 gemini_bootstrap.py --distro fedora
```

