# ha-echomuse

**Stand vom 28. Oktober 2026:** beide Echo Dot 2 im Homelab verwenden jetzt [TECHO5](https://github.com/ha-homelab/ha-techo5-dot/blob/main/docs/status.md). Die Home-Assistant-Dienste für Haussteuerung und Familienfunktionen aus diesem Repository bleiben im Einsatz. Die EchoMuse-Geräte- und Controller-Anleitungen beschreiben den früheren Betrieb.

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Einen vorhandenen **Echo Dot 2** mit EchoMuse und emOS als Sprachsatelliten für
Home Assistant nutzen. Dieses unabhängige Projekt bietet reproduzierbare
Bereitstellung, Wiederherstellung, lokale Haussteuerung und Betriebsanleitungen.
Es ist keine offizielle EchoMuse-Distribution und keine Universalfirmware für alle Echo-Geräte.

[Dokumentation](docs/README.md) · [Betrieb](docs/operations.md) · [Kompatibilität](docs/compatibility.md) · [Fehlersuche](docs/troubleshooting.md) · [Wiki](https://github.com/ha-homelab/ha-echomuse/wiki)

![Sechs Schritte von der Identifizierung des Echo Dot bis zum überprüften Sprachergebnis; englische Beschriftung](docs/assets/conversion-journey.svg)

**[Visueller Leitfaden: Ablauf und Ergebnis](docs/visual-guide.md)** — Konvertierung, Sprachverarbeitung, gemessene Zeiten, Bluetooth-Rollen und Abnahmeprüfungen. Leitfaden und Grafiken sind auf Englisch; die Verbindungen erklärt die [Architektur](docs/architecture.md).

[Gedichte, Rätsel und Familienfunktionen](docs/family-interaction.md): geprüfte Texte, eigene Geschichten und Musik; Anleitung auf Englisch.

## Funktionen

- Reproduzierbare Vorbereitung mit festgelegten Versionen; **das Build-Skript flasht kein Gerät**.
- Assist über ESPHome, Musiksteuerung, Ansagen, Timer, frühe Sprachausgabe und
  Unterbrechung per Aktivierungswort, sofern die Komponenten dies unterstützen.
- Lokale Ollama-Werkzeuge für Zustände, ausdrücklich erlaubte Gerätesteuerung
  und Recorder-Statistiken sowie begrenzte, nur lesende Energieberichte.
- Ein separater verschlüsselter Bluetooth-Proxy-Endpunkt für BLE-Geräte.
- README-Anleitungen in fünf Sprachen und Sprachauswahl aus einer festen Liste.
  Native Zustandsabfragen sind als englische und russische Beispiele enthalten;
  siehe [Sprachumfang](docs/i18n.md).

## Voraussetzungen

Die dokumentierte Hardware ist **Echo Dot 2 / RS03QR (biscuit)**. Modell, OS,
Partitionen und die gerätespezifische Sicherung vor jeder Änderung am Startsystem
prüfen. Andere Generationen und große Echo-Modelle sind mit dieser Anleitung
nicht validiert. Stabile Stromversorgung, USB-Datenkabel und ein unterstützter
Wiederherstellungsrechner sind nötig; WLAN allein bietet keine Wiederherstellung.

Benötigt werden außerdem Home Assistant, eine Assist-Sprachpipeline und der
EchoMuse Controller. Music Assistant, Plex, Ollama und der Energiedienst sind
für ihre jeweiligen Zusatzfunktionen optional. **Vorlagen mit Platzhaltern nicht unverändert anwenden.**

## Installationsreihenfolge

1. [Kompatibilität](docs/compatibility.md) und die gesamte
   [Migrationsanleitung](docs/migration.md) einschließlich Rückkehr zum alten Stand lesen.
2. [Controller](docs/controller.md) mit privatem persistentem Speicher, TLS und
   individuellen Zugangsdaten für jedes Gerät bereitstellen.
3. [Festgelegte Artefakte](upstream-lock.json) prüfen, das Gerät sichern und sein
   Image mit [build_emos.py](scripts/build_emos.py) vorbereiten. Keine fremde Gerätesicherung verwenden.
4. USB-Installation durchführen, das Gerät im Controller freigeben und seinen
   Sprachendpunkt über **ESPHome** in Home Assistant aufnehmen.
5. Assist-Pipeline, STT-Sprache und TTS-Stimme zuweisen. Bei Bedarf
   [Haussteuerung](docs/home-control.md) und [Energieberichte](docs/energy-assist.md) einrichten.
6. Aktuelle Entitäten in [Lovelace](docs/dashboard.md) einbinden;
   den [BLE-Proxy](docs/bluetooth-proxy.md) separat registrieren.
7. Die [Abnahme](docs/operations.md) für jedes Gerät durchführen, bevor das nächste
   umgestellt wird. Eine Controller-Verbindung beweist noch keine hörbare Antwort.

## Im Alltag

Zur Verwaltung dienen die authentifizierte Weboberfläche des Controllers und
seine root Console: [Zugriff und Zugangsdaten](docs/device-access.md). Das Projekt
richtet keinen universellen SSH-/Telnet-Zugang ein. Wiederherstellung ist ein eigener Ablauf.

Beide Pilot-Dots verwenden jetzt das lokal trainierte **«Привет, Мышка»** statt
Hey Jarvis. Siehe [Training, Installation und Testgrenzen](docs/russian-wake-word.md).
Die Firmware verwendet ein aktives Modell; persönliche Modellgewichte sind
nicht im Repository enthalten. [Sprachfunktionen](docs/voice-features.md) erläutert Streaming
und Unterbrechung. [Musik-Fehlersuche](docs/music-troubleshooting.md) behandelt
fehlende Quelldateien, Pufferung sowie Stoppen und Pausieren am ursprünglichen
Lautsprecher. **iBeacon Tracker** verarbeitet BLE-Signale und ist kein zusätzlicher Proxy.

## Prüfstand und Grenzen

Dokumentierte Testbasis: emOS **0.10**, EchoMuse **2.18.0**, Controller **2.26.0**,
Home Assistant **2026.10.0**. Dies ist ein datierter Stand, keine Aussage über die
neuesten Versionen oder den aktuellen Gerätestatus. Beide Migrationen und russische
Sprachtests aus der Nähe sind belegt; Fernfeld-Erkennung und Langzeitstabilität
haben Grenzen. Siehe [Protokoll](docs/deployment-record.md),
[Sprachvalidierung](docs/russian-voice-validation.md) und [Latenzmessungen](docs/architecture.md).

Die dokumentierte aktuelle russische Stimme ist **Silero Baya**. Hauswerkzeuge
laufen lokal über Ollama, STT verwendet jedoch FCC cloud speech: **die gesamte
Pipeline ist nicht offline**. Andere Sprachen benötigen passende STT-, Modell-
und TTS-Einstellungen und eigene Hörtests. Keine Hausdaten an die optionale
Cloud-Route für allgemeine Fragen senden: [Datengrenzen](docs/home-control.md).

## Mitarbeit und Dokumentation

[CONTRIBUTING.md](CONTRIBUTING.md) beschreibt Tests und Übersetzungen,
[SECURITY.md](SECURITY.md) private Sicherheitsmeldungen, [CI](docs/ci.md) die
Prüfregeln und die [Wiki-Anleitung](docs/wiki.md) die Veröffentlichung aus
überprüften Quelldateien. Aufnahmen, Modelle, Gerätekennungen, Schlüssel, Tokens
und Sicherungen bleiben privat. Detaillierte Betriebsanleitungen sind auf Englisch.

## Upstream und verwandte Projekte

- [EchoMuse](https://github.com/wilbowes/EchoMuse): Gerätesoftware, Controller und emOS.
- [ha-echo-dot](https://github.com/ha-homelab/ha-echo-dot): EchoLocal und Aktivierungswort-Training.
- [ha-echo-show-5](https://github.com/ha-homelab/ha-echo-show-5): separater Echo-Show-Pfad.
- [Repository-Infrastruktur](https://github.com/4alvit/terraform-github-ha-homelab): Terraform.

[LICENSE](LICENSE) gilt für dieses Projekt; Upstream-Komponenten behalten ihre
Lizenzen. Keine Amazon-Firmware, Release-Binärdateien oder persönlichen Sprachmodelle werden verteilt.

[Russische Spracheinstellungen und Stimmenkatalog](docs/speech-settings.md): fünf Silero-Stimmen, Tempo, Tonhöhe, Pausen und Aussprache sind in HA einstellbar. Die Anleitung ist auf Englisch.
