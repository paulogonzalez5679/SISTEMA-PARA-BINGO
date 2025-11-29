# 🎱 SISTEMA PARA BINGO

Sistema web para la gestión y administración de juegos de bingo, pensado para facilitar la generación, control y seguimiento de cartones, ganadores y partidas. Ideal para eventos, rifas, asociaciones y actividades recreativas.

---

## 📑 Tabla de Contenido

- [Características principales](#características-principales)
- [Instalación](#instalación)
- [Uso](#uso)
- [Configuración adicional](#configuración-adicional)
- [Notas importantes](#notas-importantes)
- [Créditos](#créditos)
- [Licencia](#licencia)

---

## 🚀 Características principales

- Generación masiva de cartones de bingo en formato JSON.
- Registro y control de ganadores.
- Interfaz web intuitiva para visualizar y administrar partidas.
- Carga y gestión de archivos de cartones.
- Exportación de resultados y reportes.
- Soporte para múltiples partidas y eventos.
- Sistema de archivos organizado para cartones, ganadores y archivos subidos.

---

## 🛠️ Instalación

1. **Clona el repositorio:**
   ```bash
   git clone https://github.com/paulogonzalez5679/SISTEMA-PARA-BINGO.git
   cd SISTEMA-PARA-BINGO
   ```

2. **Instala las dependencias:**
   > Requiere Python 3.8+ y pip.
   ```bash
   pip install -r requirements.txt
   ```

3. **Estructura de carpetas:**
   - `jsons/` y `upload/` se incluyen vacías para organización. No borres los archivos `.gitkeep`.
   - `templates/` contiene las vistas HTML.
   - `winners/` almacena los ganadores.

---

## 💻 Uso

1. **Ejecuta la aplicación:**
   ```bash
   python app.py
   ```
   Por defecto, se inicia en `localhost:5000` (puedes cambiar el puerto en la configuración).

2. **Carga de cartones:**
   - Sube archivos JSON de cartones a través de la interfaz web o colócalos en la carpeta `jsons/`.

   ### 🧪 Prueba rápida de auto-asignación (admin)

   - Inicia sesión con un usuario admin (tipo_usuario = 0) en la interfaz de administración.
   - En el panel de usuarios (Admin), intenta reservar tablas con la opción de "Añadir Participante"; el sistema pedirá la cantidad de tablas a reservar y, si es admin, tomará las tablas desde el último código disponible hacia atrás.
   - Verifica en la tabla de cartones que las tablas reservadas aparecen marcadas como reservadas (`stateReserved`) y que en el administrador de usuario aparecen `fromSerial` y `toSerial` con los rangos correctos (podrán estar invertidos si la reserva fue desde el final).

3. **Gestión de partidas:**
   - Accede a la interfaz web para iniciar, controlar y finalizar partidas.
   - Visualiza el historial de ganadores y exporta reportes.

---

## ⚙️ Configuración adicional

- Puedes modificar parámetros en `app.py` para personalizar el puerto, rutas de archivos y otras opciones.
- Para producción, se recomienda usar un servidor WSGI como Gunicorn y configurar variables de entorno para mayor seguridad.

---

## ❗ Notas importantes

- No subas archivos sensibles o datos personales a las carpetas públicas.
- Los archivos en `jsons/` y `upload/` se ignoran por defecto en Git, salvo el archivo `.gitkeep` que mantiene la estructura.
- Revisa la licencia antes de usar el sistema en entornos comerciales.

- Nota sobre auto-asignación de cartones: Solo el usuario con rol admin (tipo_usuario = 0) puede reservar tableros automáticamente. Cuando un admin reserva tableros, el sistema toma las tablas disponibles desde el último código hacia atrás (ej: CARD02000, CARD01999, ...). Esto está pensado para que el admin pueda autoasignarse grandes bloques de cartones desde el final.

---

## 👥 Créditos

Desarrollado por [Paulo Gonzalez](https://github.com/paulogonzalez5679).


---

## 📄 Licencia

Este proyecto está bajo la licencia BSD-3. Consulta el archivo `LICENSE` para más detalles.

---

¡Gracias por usar SISTEMA PARA BINGO! 🎉
