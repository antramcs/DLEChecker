# -*- coding: utf-8 -*-
# DLEChecker - Plugin global para NVDA
# Patrón MVC: Punto de entrada / Integración con NVDA

"""
Punto de entrada del plugin DLEChecker para NVDA.

Este módulo es el ``__init__.py`` del paquete ``DLEChecker`` y actúa como
punto de entrada que NVDA carga automáticamente al descubrir un directorio
dentro de ``globalPlugins/``. Su responsabilidad principal es:

1. **Preparar el entorno**: inyectar el directorio ``libs/`` en ``sys.path``
   **antes** de cualquier importación interna, para que las dependencias
   empaquetadas (BeautifulSoup, cloudscraper, etc.) estén disponibles
   sin necesidad de instalación global.
2. **Definir el GlobalPlugin**: clase que NVDA instancia para registrar
   gestos de teclado y delegar la lógica al controlador MVC.

Arquitectura MVC del plugin:
    - **Model** (``models/``): ``DLEService``, ``DictionaryEntry``,
      ``TextProcessor`` — lógica de negocio, peticiones HTTP y parsing.
    - **View** (``views/``): ``SearchDialog``, ``ResultDialog`` — diálogos
      wx accesibles para la interacción con el usuario.
    - **Controller** (``controllers/``): ``DLEController`` — orquestación
      del flujo de búsqueda entre modelos y vistas.

Uso:
    Seleccionar una palabra en cualquier aplicación y pulsar
    la combinación de teclas que se asigne para buscar su definición en el DLE.
    Si no hay texto seleccionado, se abrirá un diálogo de búsqueda manual.

Dependencias externas:
    - ``globalPluginHandler``: API de NVDA para plugins globales.
    - ``api``: API de NVDA para acceder al objeto enfocado.
    - ``textInfos``: API de NVDA para manipulación de información textual.
    - ``ui``: API de NVDA para verbalizar mensajes al usuario.

Nota sobre el orden de importaciones:
    La inyección de ``libs/`` en ``sys.path`` DEBE ocurrir antes de
    ``from .controllers import DLEController``, ya que los controladores
    importan modelos que a su vez dependen de bibliotecas empaquetadas
    en ``libs/`` (como ``bs4`` o ``cloudscraper``).
"""

import os
import sys
import logging

import globalPluginHandler
import api
import textInfos
import ui
import scriptHandler

# Logger específico del módulo; hereda la configuración de logging de NVDA,
# lo que permite filtrar los mensajes de este plugin por nombre de módulo
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Preparación del entorno: inyección del directorio libs/ en sys.path
# ─────────────────────────────────────────────────────────────────────────────

# Determinar la ruta absoluta del directorio raíz del plugin.
# Se usa __file__ en lugar de rutas relativas para que funcione
# independientemente del directorio de trabajo actual de NVDA.
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

# Construir la ruta al directorio libs/ donde se empaquetan las dependencias
# de terceros (bs4, cloudscraper, etc.) que no forman parte de NVDA.
# Se inserta al INICIO de sys.path (posición 0) para que tenga prioridad
# sobre posibles versiones instaladas globalmente, garantizando que se usen
# las versiones compatibles empaquetadas con el plugin.
_LIBS_DIR = os.path.join(_PLUGIN_DIR, "libs")
if os.path.isdir(_LIBS_DIR) and _LIBS_DIR not in sys.path:
    sys.path.insert(0, _LIBS_DIR)

# IMPORTANTE: esta importación debe estar DESPUÉS de la inyección de libs/
# en sys.path, ya que DLEController → DLEService → dependencias empaquetadas
from .controllers import DLEController


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    """Plugin global de NVDA para consultar el Diccionario de la Lengua Española.

    Esta clase es el punto de integración con la API de NVDA. Se encarga
    exclusivamente de:

        - **Obtención de texto seleccionado**: acceder al objeto enfocado y
      extraer la selección activa del usuario.
    - **Delegación al controlador**: toda la lógica de negocio (validación,
      búsqueda HTTP, presentación de resultados) se delega a ``DLEController``,
      manteniendo esta clase lo más delgada posible según el patrón MVC.

    Ciclo de vida:
        - ``__init__``: NVDA llama a este método al cargar el plugin. Se
          instancia el controlador y se registran los gestos.
        - ``terminate``: NVDA llama a este método al descargar el plugin
          (cierre de NVDA o recarga de plugins). Se liberan recursos.

    Attributes:
        _controller (DLEController): Instancia del controlador principal.
            Se crea una sola vez en ``__init__`` y se reutiliza durante
            toda la vida del plugin.

    Ejemplo:
        El usuario selecciona la palabra "efímero" en un navegador web y
        pulsa la combinación de teclas asignada. El flujo es:
            1. NVDA invoca ``script_check_dle_term``.
            2. ``_get_selected_text`` obtiene "efímero" del buffer virtual.
            3. ``_controller.handle_search_request("efímero")`` lanza la
               búsqueda en un hilo de fondo y muestra el resultado.
    """

    def __init__(self):
        """Inicializa el plugin global y crea el controlador MVC.

        Llama al constructor padre de ``globalPluginHandler.GlobalPlugin``,
        que se encarga del registro de gestos definidos en ``__gestures``.
        Luego instancia ``DLEController``, que a su vez crea el servicio
        de consultas al DLE.
        """
        # Inicializar la clase base de NVDA — registra los gestos y
        # establece el plugin en el sistema de plugins globales
        super(GlobalPlugin, self).__init__()
        # Crear el controlador MVC que gestionará toda la lógica de búsqueda
        self._controller = DLEController()
        log.info("DLEChecker plugin cargado correctamente (arquitectura MVC)")

    def terminate(self):
        """Limpieza al desactivar o descargar el plugin.

        NVDA invoca este método cuando el plugin se descarga (cierre de
        NVDA, recarga de complementos o desinstalación). Se registra la
        descarga y se llama al método padre para la limpieza estándar.
        """
        log.info("DLEChecker plugin descargado")
        # Llamar al terminate del padre para que NVDA realice su propia
        # limpieza (desregistro de gestos, liberación de recursos internos)
        super(GlobalPlugin, self).terminate()

    @scriptHandler.script(
        description=_(
            "Consulta la definición de la palabra seleccionada en el "
            "Diccionario de la Lengua Española (DLE)."
        ),
        category=_("DLEChecker"),
    )
    def script_check_dle_term(self, gesture):
        """Script principal: busca la definición de una palabra en el DLE.

        Este método obtiene el texto actualmente seleccionado y lo
        envía al controlador. Si no hay selección, el controlador mostrará
        un diálogo de búsqueda manual.

        El nombre del método sigue la convención de NVDA: ``script_`` +
        nombre del script.

        Args:
            gesture (inputCore.InputGesture): Objeto que describe el gesto
                de teclado que activó el script. No se utiliza directamente
                en la lógica, pero es requerido por la API de scripts de NVDA.
        """
        # Obtener el texto seleccionado del objeto enfocado actual
        selected_text = self._get_selected_text()
        # Delegar toda la lógica al controlador — este decidirá si buscar
        # directamente o mostrar el diálogo de búsqueda manual
        self._controller.handle_search_request(selected_text)

    def _get_selected_text(self):
        """Obtiene el texto actualmente seleccionado en la aplicación enfocada.

        Implementa una estrategia de dos niveles para extraer la selección:

        1. **TreeInterceptor** (prioridad alta): si el objeto enfocado tiene
           un ``treeInterceptor`` con capacidad ``TextInfo`` (típico en
           buffers virtuales de navegadores web, documentos PDF, etc.),
           se obtiene la selección desde ahí. Esto es necesario porque en
           modo exploración de NVDA, el texto seleccionado vive en el
           interceptor del árbol, no en el objeto enfocado directamente.

        2. **FocusObject** (fallback): si no hay ``treeInterceptor`` o
           este no soporta ``TextInfo``, se obtiene la selección
           directamente del objeto enfocado (controles de edición nativos,
           terminales, etc.).

        Returns:
            str: Texto seleccionado por el usuario. Cadena vacía si no hay
                selección activa, si el objeto no soporta selección de texto,
                o si ocurre cualquier error durante la extracción.

        Raises:
            No propaga excepciones al exterior. Todos los errores se capturan
            internamente:
            - ``RuntimeError``, ``NotImplementedError``, ``AttributeError``:
              el objeto no soporta la operación de selección — es un caso
              normal (p.ej. botones, iconos del escritorio).
            - Cualquier otra excepción: se registra como warning en el log
              para diagnóstico sin interrumpir al usuario.
        """
        try:
            # Obtener el objeto enfocado actual en NVDA (ventana, control, etc.)
            obj = api.getFocusObject()
            # Obtener el interceptor de árbol del objeto; en navegadores web
            # y documentos, este interceptor gestiona el buffer virtual
            tree_interceptor = obj.treeInterceptor

            if hasattr(tree_interceptor, "TextInfo"):
                # El interceptor soporta TextInfo → estamos en un buffer virtual
                # (modo exploración en navegador, documento PDF, etc.).
                # La selección se obtiene del interceptor, no del objeto nativo,
                # porque el buffer virtual mantiene su propio estado de selección.
                info = tree_interceptor.makeTextInfo(textInfos.POSITION_SELECTION)
            else:
                # Sin interceptor o sin capacidad TextInfo → fallback al objeto
                # enfocado nativo (campo de texto, terminal, editor, etc.)
                info = obj.makeTextInfo(textInfos.POSITION_SELECTION)

            # Extraer el texto de la selección
            selected = info.text
            # Devolver el texto seleccionado o cadena vacía si es None/vacío
            return selected if selected else ""

        except (RuntimeError, NotImplementedError, AttributeError):
            # Excepciones esperadas: el objeto no soporta selección de texto.
            # Es un caso normal (p.ej. el foco está en un botón o en el
            # escritorio), por lo que no se registra como error.
            return ""
        except Exception as e:
            # Excepción inesperada: registrar para diagnóstico pero no
            # interrumpir al usuario; simplemente se trata como "sin selección"
            log.warning("Error al obtener texto seleccionado: %s", e)
            return ""

