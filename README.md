# MangusTracker 🕵️‍♂️🥭

<p align="center">
  <img src="https://raw.githubusercontent.com/alejandroasc96/MangusTracker/main/img/magusTracker.png" alt="MangusTracker Logo" width="350">
</p>

> **MangusTracker** es tu espía personal y discreto en Discord. Este bot de rastreo te notifica al instante (vía Mensaje Directo) cuando tus usuarios seleccionados se conectan a un canal de voz, manteniéndote siempre al tanto sin que nadie más lo sepa.

---

## 📖 ¿Cómo funciona?

El funcionamiento es sencillo pero potente, diseñado para la discreción y el control personal. Todo se gestiona mediante cómodos **Comandos de Barra (`/slash commands`)**, y las notificaciones te llegan en privado.

### Flujo de Uso Princpial:

1.  **Rastreo Silencioso:** Tú decides a quién quieres rastrear usando el comando `/tracker`. El bot comienza a vigilar a ese usuario en el servidor actual.
2.  **Notificaciones Privadas:** Cuando el usuario rastreado entra a *cualquier* canal de voz del servidor, MangusTracker te envía un Mensaje Directo (MD) inmediato. ¡El usuario rastreado nunca sabrá que está siendo vigilado!
3.  **Control Total:** Tú gestionas tu lista de rastreo. Nadie más puede ver a quién estás vigilando, ni siquiera los administradores del servidor. Todo es privado entre tú y el bot.

---

## 🛠️ Comandos Disponibles

Utiliza estos comandos de barra directamente en cualquier canal de texto del servidor:

| Comando | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `/config_global` | **Configura tu horario** (0-23h) para recibir avisos. | `/config_global inicio:9 fin:21` |
| `/tracker @usuario` | **Empieza a rastrear** a un miembro del servidor. | `/tracker usuario:@Nombre` |
| `/tracker_remove @usuario` | **Deja de rastrear** a un usuario específico. | `/tracker_remove usuario:@Nombre` |
| `/tracker_list` | Muestra tu **horario y lista** de rastreos actual. | `/tracker_list` |
| `/tracker_off` | **Pausa** las notificaciones en este servidor. | `/tracker_off` |
| `/tracker_on` | **Reactiva** las notificaciones en este servidor. | `/tracker_on` |
| `/tracker_clear` | **Elimina todos** tus rastreos en el servidor. | `/tracker_clear` |
| `/tracker_help` | Muestra el **menú de ayuda** detallado. | `/tracker_help` |

> *Nota: Todas las respuestas a estos comandos son efímeras (solo tú puedes verlas).*

---

## ⚙️ Características Técnicas

* **100% Privado:** Las notificaciones y la gestión de la base de datos de rastreo son totalmente privadas y se entregan por MD.
* **Comandos de Barra:** Integración total con la interfaz moderna de Discord.
* **Optimizado:** Utiliza caché local y persistencia asíncrona (`aiofiles` + `json`) para un rendimiento ligero y eficiente.
* **Seguro:** Diseñado para manejar tokens y datos de forma segura (con `.env` para el desarrollo local).

---

## ⚠️ Próximamente...

Este bot está en continuo desarrollo. Próximamente añadiremos:

* [ ] Integración con Docker para un despliegue sencillo.
* [ ] Scripts de instalación automática para servidores Linux y Windows.
* [ ] ...y mucho más.

---

<p align="center">
  <em>Desarrollado con ❤️ por y para la comunidad.</em>
</p>
