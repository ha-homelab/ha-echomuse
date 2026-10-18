# ha-echomuse

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Convierte un **Echo Dot 2** existente en un satélite de voz de Home Assistant
con EchoMuse y emOS. Este proyecto independiente ofrece despliegues reproducibles,
recuperación, herramientas locales para el hogar y documentación operativa.
No es una distribución oficial de EchoMuse ni un firmware universal para todos los Echo.

[Documentación](docs/README.md) · [Operación](docs/operations.md) · [Compatibilidad](docs/compatibility.md) · [Diagnóstico](docs/troubleshooting.md) · [Wiki](https://github.com/ha-homelab/ha-echomuse/wiki)

![Seis etapas desde identificar el Echo Dot hasta comprobar su respuesta de voz; etiquetas en inglés](docs/assets/conversion-journey.svg)

**[Guía visual: proceso y resultado](docs/visual-guide.md)** — conversión, recorrido de la voz, tiempos medidos, funciones de Bluetooth y comprobaciones. La guía y los gráficos están en inglés; las conexiones se explican en la [arquitectura](docs/architecture.md).

## Funciones

- Preparación reproducible con versiones fijadas; **el constructor no instala firmware en el dispositivo**.
- Assist mediante ESPHome, control de música, anuncios, temporizadores, voz antes
  de terminar la generación e interrupción con la frase de activación, según los componentes.
- Herramientas locales de Ollama para estados, control de dispositivos autorizados
  explícitamente y estadísticas de Recorder; informes de energía limitados y de solo lectura.
- Un endpoint independiente y cifrado de proxy Bluetooth para dispositivos BLE.
- README en cinco idiomas y selección del idioma de respuesta de una lista fija.
  Se incluyen ejemplos nativos de consulta de estado en inglés y ruso;
  consulta la [cobertura de idiomas](docs/i18n.md).

## Requisitos

El modelo documentado es **Echo Dot 2 / RS03QR (biscuit)**. Verifica modelo, sistema,
particiones y copia de recuperación individual antes de modificar el arranque.
Esta guía no valida otras generaciones ni los Echo de tamaño completo. Necesitas
alimentación estable, cable USB de datos y un equipo compatible para recuperación;
Wi-Fi por sí solo no permite recuperar el arranque.

También necesitas Home Assistant, una canalización de voz Assist y EchoMuse
Controller. Music Assistant, Plex, Ollama y el servicio de energía son opcionales
para sus funciones respectivas. **No apliques las plantillas con valores de ejemplo sin configurarlas.**

## Orden de instalación

1. Comprueba la [compatibilidad](docs/compatibility.md) y lee toda la
   [guía de migración](docs/migration.md), incluida la restauración.
2. Despliega el [controlador](docs/controller.md) con almacenamiento persistente
   privado, TLS y credenciales individuales por dispositivo.
3. Verifica los [artefactos fijados](upstream-lock.json), guarda la copia del
   dispositivo y prepara su imagen con [build_emos.py](scripts/build_emos.py).
   No uses la copia de otro dispositivo.
4. Realiza la instalación USB, aprueba el dispositivo en el controlador y registra
   su endpoint de voz en la integración **ESPHome** de Home Assistant.
5. Asigna la canalización Assist, el idioma STT y la voz TTS. Añade si procede
   [control del hogar](docs/home-control.md) e [informes de energía](docs/energy-assist.md).
6. Añade las entidades actuales a [Lovelace](docs/dashboard.md) y registra el
   [proxy BLE](docs/bluetooth-proxy.md) por separado.
7. Completa la [verificación de aceptación](docs/operations.md) de cada unidad
   antes de migrar la siguiente. Estar conectado al controlador no demuestra una respuesta audible.

## Uso cotidiano

Administra el dispositivo mediante la interfaz web autenticada del controlador
y su root Console: [acceso y credenciales](docs/device-access.md). El proyecto no
crea un acceso SSH/Telnet universal; la recuperación tiene su propio procedimiento.

Ambos Dot piloto usan ahora **«Привет, Мышка»**, entrenada localmente, en lugar de
Hey Jarvis. Véanse [entrenamiento, instalación y límites de las pruebas](docs/russian-wake-word.md).
El firmware admite un solo modelo activo; los pesos personales no se incluyen
en el repositorio.
[Funciones de voz](docs/voice-features.md) explica la interrupción y el streaming.
[Diagnóstico de música](docs/music-troubleshooting.md) cubre fuentes ausentes,
buffering y la diferencia entre detener y pausar el reproductor de origen.
**iBeacon Tracker** procesa anuncios BLE; no es otro proxy.

## Verificación y límites

Base de pruebas documentada: emOS **0.10**, EchoMuse **2.18.0**, Controller
**2.26.0** y Home Assistant **2026.10.0**. Es un registro fechado, no una afirmación
sobre las últimas versiones ni el estado actual de los equipos. Se verificaron
ambas migraciones y respuestas en ruso a corta distancia; el reconocimiento
lejano y la fiabilidad prolongada tienen límites. Consulta el
[registro](docs/deployment-record.md), la [validación de voz](docs/russian-voice-validation.md)
y las [mediciones de latencia](docs/architecture.md).

La voz rusa actual del registro es **Silero Baya**. Las herramientas del hogar
usan Ollama local, pero STT emplea FCC cloud speech: **la canalización completa no
funciona sin servicios externos**. Cada idioma adicional necesita STT, modelo y
TTS compatibles y su propia prueba auditiva. No envíes datos del hogar a la ruta
opcional de preguntas generales en la nube: [límites de privacidad](docs/home-control.md).

## Contribuir y mantener la documentación

[CONTRIBUTING.md](CONTRIBUTING.md) explica pruebas y traducciones,
[SECURITY.md](SECURITY.md) los avisos privados de seguridad, [CI](docs/ci.md) las
revisiones y la [guía Wiki](docs/wiki.md) la publicación desde fuentes revisadas.
Grabaciones, modelos, identificadores, claves, tokens y copias deben permanecer
privados. Las instrucciones operativas detalladas se mantienen en inglés.

## Origen y proyectos relacionados

- [EchoMuse](https://github.com/wilbowes/EchoMuse): software, controlador y emOS.
- [ha-echo-dot](https://github.com/ha-homelab/ha-echo-dot): EchoLocal y entrenamiento de activación.
- [ha-echo-show-5](https://github.com/ha-homelab/ha-echo-show-5): procedimiento separado para Echo Show.
- [Infraestructura del repositorio](https://github.com/4alvit/terraform-github-ha-homelab): Terraform.

Consulta [LICENSE](LICENSE). Los componentes externos conservan sus licencias;
no se distribuyen firmware de Amazon, binarios de versiones ni modelos de voz personales.

[Ajustes de voz rusa y catálogo de voces](docs/speech-settings.md): cinco voces Silero, velocidad, tono, pausas y pronunciación configurables en HA. La guía detallada está en inglés.
