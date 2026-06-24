# -*- coding: utf-8 -*-
# DLEChecker - Controlador principal
# Patrón MVC: Capa Controller

"""
Controlador principal del plugin DLEChecker para NVDA.

Este módulo implementa la capa Controller del patrón MVC. Su responsabilidad
central es orquestar el flujo completo de una consulta al Diccionario de la
Lengua Española (DLE), coordinando la comunicación entre:

- **Modelos** (``DLEService``, ``TextProcessor``): lógica de negocio, peticiones
  HTTP al DLE y validación/limpieza de texto.
- **Vistas** (``SearchDialog``, ``ResultDialog``): diálogos wx para la
  interacción con el usuario a través del lector de pantalla NVDA.

Flujo principal de una búsqueda:
    1. ``handle_search_request`` recibe texto seleccionado o ``None``.
    2. Si hay texto válido → ``_perform_search`` lanza un hilo de fondo.
    3. Si no hay texto → ``_show_search_dialog`` muestra el diálogo de entrada
       mediante ``wx.CallAfter`` (garantía de seguridad de hilos).
    4. ``_search_worker`` ejecuta ``DLEService.search()`` en hilo secundario.
    5. Los resultados se despachan al hilo principal de wx con
       ``wx.CallAfter`` → ``_handle_search_result``.
    6. ``_handle_search_result`` presenta ``ResultDialog`` o un mensaje de error.

Consideraciones de hilos (threading):
    Las peticiones HTTP se ejecutan **siempre** en un hilo daemon para no
    congelar la interfaz de NVDA. Los diálogos wx deben crearse y mostrarse
    **exclusivamente** en el hilo principal de la aplicación (requisito de
    wxPython). ``wx.CallAfter`` actúa como puente seguro entre ambos mundos.

Dependencias:
    - ``wx``: framework de interfaz gráfica subyacente a NVDA.
    - ``ui``: módulo de NVDA para verbalizar mensajes al usuario.
    - ``threading``: hilos nativos de Python para operaciones asíncronas.
    - Paquetes internos ``..models`` y ``..views`` del propio plugin.
"""

import logging
import threading

import wx

import ui

from ..models import DLEService, TextProcessor
from ..views import SearchDialog, ResultDialog

# Logger específico del módulo; hereda la configuración de logging de NVDA
log = logging.getLogger(__name__)


class DLEController:
    """Controlador central que coordina la lógica entre modelos y vistas.

    Gestiona el ciclo de vida completo de una consulta al DLE, desde la
    obtención del término hasta la presentación de resultados. Todo el
    trabajo pesado (peticiones de red) se delega a un hilo secundario,
    mientras que la interacción con el usuario ocurre siempre en el hilo
    principal de wx.

    Flujo resumido:
        1. Recibir término (texto seleccionado o diálogo de entrada).
        2. Validar y limpiar el término mediante ``TextProcessor``.
        3. Lanzar ``DLEService.search()`` en hilo daemon.
        4. Recibir el resultado (``DictionaryEntry``) y mostrarlo.

    Attributes:
        _dle_service (DLEService): Instancia única del servicio de consulta
            al DLE. Encapsula toda la lógica de red y parsing HTML.
        _is_searching (bool): Bandera de guarda que impide lanzar búsquedas
            concurrentes. Se activa al iniciar una búsqueda y se desactiva
            en el bloque ``finally`` del worker, garantizando su liberación
            incluso ante excepciones.

    Ejemplo de uso (desde el ``GlobalPlugin``):
        >>> controller = DLEController()
        >>> controller.handle_search_request("amanecer")
        # Verbaliza "Buscando 'amanecer' en el DLE..." y lanza hilo de fondo.
    """

    def __init__(self):
        """Inicializa el controlador con las dependencias necesarias.

        Crea una instancia de ``DLEService`` y establece la bandera de
        búsqueda en curso a ``False``, indicando que el controlador está
        listo para aceptar solicitudes.
        """
        # Servicio de consultas al DLE — se reutiliza en todas las búsquedas
        self._dle_service = DLEService()
        # Bandera de guarda: evita múltiples búsquedas simultáneas que
        # podrían saturar la red o confundir al usuario con respuestas mezcladas
        self._is_searching = False

    def handle_search_request(self, selected_text=None):
        """Punto de entrada principal: maneja una solicitud de búsqueda.

        Decide la estrategia de búsqueda según la disponibilidad de texto
        seleccionado:
        - **Con texto válido**: se limpia y se busca directamente.
        - **Con texto inválido** (caracteres especiales, números, etc.):
          se informa al usuario del problema.
        - **Sin texto**: se abre el diálogo de búsqueda manual.

        Si ya hay una búsqueda en curso (``_is_searching == True``), se
        rechaza la solicitud con un mensaje de aviso para evitar peticiones
        concurrentes que podrían causar condiciones de carrera.

        Args:
            selected_text (str | None): Texto seleccionado por el usuario
                en la aplicación activa. Puede ser ``None`` si no había
                selección, o una cadena vacía/con solo espacios.
        """
        if self._is_searching:
            # Protección contra búsquedas concurrentes: si el hilo anterior
            # aún no ha terminado, se rechaza cortésmente la nueva solicitud
            # Translators: Mensaje cuando ya hay una búsqueda en curso
            ui.message(_("Ya hay una búsqueda en curso. Por favor, espere."))
            return

        if selected_text and selected_text.strip():
            # Rama 1: hay texto seleccionado no vacío — intentar búsqueda directa
            # Primero se limpia (eliminar espacios, normalizar) y luego se valida
            clean_text = TextProcessor.clean(selected_text)
            if TextProcessor.is_valid(clean_text):
                # El texto pasó la validación → lanzar búsqueda en hilo de fondo
                self._perform_search(clean_text)
            else:
                # El texto contiene caracteres no válidos (números, símbolos, etc.)
                # Translators: Mensaje cuando el texto seleccionado no es válido
                ui.message(_(
                    "El texto seleccionado no contiene una palabra válida para buscar."
                ))
        else:
            # Rama 2: sin texto seleccionado → abrir diálogo de entrada manual
            self._show_search_dialog()

    def _show_search_dialog(self):
        """Muestra el diálogo de búsqueda manual y procesa la respuesta.

        Se utiliza ``wx.CallAfter`` para garantizar que la creación y
        presentación del diálogo ocurra en el hilo principal de wx, ya que
        wxPython no es thread-safe y crear widgets desde hilos secundarios
        puede provocar fallos silenciosos o crashes.

        El diálogo es modal: bloquea la interacción hasta que el usuario
        acepta o cancela. El recurso ``dialog`` se destruye en el bloque
        ``finally`` para evitar fugas de memoria de objetos wx.

        Raises:
            No lanza excepciones al exterior; los errores de validación
            se comunican al usuario mediante ``ui.message``.
        """
        def _show():
            """Función interna ejecutada en el hilo principal de wx."""
            dialog = SearchDialog()
            try:
                result = dialog.ShowModal()
                if result == wx.ID_OK:
                    # El usuario pulsó Aceptar — obtener el término ingresado
                    term = dialog.get_search_term()
                    if term and TextProcessor.is_valid(term):
                        # Término válido: limpiar y lanzar búsqueda
                        clean_term = TextProcessor.clean(term)
                        self._perform_search(clean_term)
                    elif term:
                        # El usuario ingresó algo, pero no es válido
                        # (p.ej. contiene números o caracteres especiales)
                        # Translators: Mensaje cuando el término ingresado no es válido
                        ui.message(_(
                            "El término '{}' no es válido. "
                            "Introduce una palabra con solo letras."
                        ).format(term))
                    # Si term es vacío y el usuario pulsó OK, simplemente
                    # se cierra el diálogo sin acción adicional
            finally:
                # Liberar el recurso nativo del diálogo wx para evitar
                # fugas de memoria — siempre se ejecuta, incluso si hay error
                dialog.Destroy()

        # wx.CallAfter encola _show en el bucle de eventos principal,
        # garantizando que el diálogo se cree en el hilo correcto de wx
        wx.CallAfter(_show)

    def _perform_search(self, word):
        """Inicia la búsqueda de una palabra en un hilo secundario daemon.

        Este método actúa como lanzador: activa la bandera de búsqueda en
        curso, notifica al usuario que la búsqueda ha comenzado y crea un
        hilo daemon que ejecutará ``_search_worker``.

        El hilo se marca como ``daemon=True`` para que no impida el cierre
        de NVDA si el usuario lo cierra mientras hay una búsqueda activa.
        Se le asigna un nombre descriptivo (``DLEChecker-Search``) para
        facilitar la depuración con herramientas de profiling.

        Args:
            word (str): Palabra a buscar en el DLE. Se espera que ya haya
                sido limpiada por ``TextProcessor.clean()`` y validada por
                ``TextProcessor.is_valid()``.
        """
        # Activar la bandera de guarda antes de lanzar el hilo para evitar
        # que una segunda pulsación rápida del atajo lance otra búsqueda
        self._is_searching = True

        # Informar al usuario de que la búsqueda ha comenzado; esto le da
        # retroalimentación auditiva inmediata mientras espera el resultado
        # Translators: Mensaje de progreso al buscar una palabra
        ui.message(_("Buscando '{}' en el DLE...").format(word))

        # Crear y lanzar el hilo de fondo para la petición HTTP
        search_thread = threading.Thread(
            target=self._search_worker,
            args=(word,),
            daemon=True,
            name="DLEChecker-Search"
        )
        search_thread.start()

    def _search_worker(self, word):
        """Worker que ejecuta la búsqueda HTTP en un hilo secundario.

        Este método se ejecuta **fuera** del hilo principal de wx. Realiza
        la petición de red a través de ``DLEService.search()`` y, al
        finalizar, despacha el resultado o el error de vuelta al hilo
        principal mediante ``wx.CallAfter``.

        El bloque ``finally`` garantiza que ``_is_searching`` se restablezca
        a ``False`` sin importar si la búsqueda tuvo éxito o falló. Esto
        es crucial para que el controlador no quede en un estado bloqueado
        permanentemente tras un error de red.

        Args:
            word (str): Palabra a buscar en el DLE.

        Raises:
            No propaga excepciones al exterior. Cualquier excepción se captura
            y se despacha al hilo principal como error manejado mediante
            ``_handle_error``.
        """
        try:
            # Ejecutar la petición HTTP al DLE (operación bloqueante)
            entry = self._dle_service.search(word)
            # Despachar el resultado al hilo principal para mostrar el diálogo;
            # wx.CallAfter es necesario porque no se pueden manipular widgets
            # wx desde un hilo secundario
            wx.CallAfter(self._handle_search_result, entry)
        except Exception as e:
            # Capturar cualquier error de red, parsing, timeout, etc.
            log.error("Error en hilo de búsqueda: %s", e)
            # Despachar el error al hilo principal para informar al usuario
            wx.CallAfter(self._handle_error, word, e)
        finally:
            # Restablecer la bandera de guarda: siempre se ejecuta,
            # incluso si hubo excepción, para desbloquear nuevas búsquedas
            self._is_searching = False

    def _handle_search_result(self, entry):
        """Maneja el resultado de una búsqueda exitosa en el hilo principal.

        Evalúa el contenido del objeto ``DictionaryEntry`` devuelto por el
        servicio y decide qué acción tomar:

        - **Error en la entrada**: la propia entrada contiene un mensaje de
          error (p.ej. servidor no disponible) → se verbaliza el error.
        - **Sin definiciones**: la palabra no existe en el DLE →
          se notifica al usuario.
        - **Con definiciones**: se formatea el contenido y se muestra en
          ``ResultDialog``.

        Este método se invoca siempre desde ``wx.CallAfter``, por lo que se
        ejecuta de forma segura en el hilo principal de wx.

        Args:
            entry (DictionaryEntry): Objeto con los resultados de la búsqueda.
                Contiene la palabra buscada, las definiciones encontradas
                y, opcionalmente, un mensaje de error.
        """
        if entry.has_error():
            # El servicio devolvió un error controlado (p.ej. error HTTP);
            # el mensaje ya viene formateado y localizado desde el modelo
            ui.message(entry.error_message)
            return

        if entry.is_empty():
            # La palabra fue encontrada pero no tiene definiciones,
            # o simplemente no existe en el diccionario
            # Translators: Mensaje cuando no se encuentran definiciones
            ui.message(_(
                "No se encontraron definiciones para '{}'."
            ).format(entry.word))
            return

        # Caso exitoso: formatear las definiciones para su presentación
        # y mostrarlas en el diálogo de resultados
        formatted_text = entry.to_formatted_text()
        self._show_result_dialog(entry.word, formatted_text)

    def _show_result_dialog(self, word, content):
        """Muestra el diálogo modal con los resultados de la búsqueda.

        Crea una instancia de ``ResultDialog`` con el título que incluye
        la palabra buscada y el contenido formateado. Se proporciona un
        callback de lectura para que el diálogo pueda solicitar la
        verbalización de texto mediante el sintetizador de NVDA.

        El diálogo se destruye en el bloque ``finally`` para liberar
        los recursos nativos de wx y evitar fugas de memoria.

        Args:
            word (str): Palabra consultada, utilizada para componer el
                título del diálogo (p.ej. "DLE: amanecer").
            content (str): Texto formateado con las definiciones,
                acepciones, etimología y demás información del DLE.
        """
        # Translators: Título del diálogo de resultado con la palabra consultada
        title = _("DLE: {}").format(word)

        # Crear el diálogo de resultados pasando el callback de lectura,
        # lo que permite al diálogo verbalizar secciones de texto bajo demanda
        dialog = ResultDialog(
            title=title,
            content=content,
            on_read_callback=self._read_text
        )
        try:
            dialog.ShowModal()
        finally:
            # Destruir el diálogo para liberar recursos wx nativos
            dialog.Destroy()

    def _handle_error(self, word, error):
        """Maneja un error ocurrido durante la búsqueda en hilo de fondo.

        Construye un mensaje de error legible para el usuario combinando
        la palabra que se estaba buscando con la descripción de la excepción.
        Se invoca siempre desde ``wx.CallAfter``, por lo que es seguro
        interactuar con ``ui.message`` aquí.

        Args:
            word (str): Palabra que se estaba buscando cuando ocurrió el error.
            error (Exception): Excepción capturada durante la búsqueda.
                Puede ser ``ConnectionError``, ``Timeout``, ``HTTPError``,
                o cualquier otra excepción no prevista.
        """
        # Translators: Mensaje genérico de error durante la búsqueda
        error_message = _(
            "Error al buscar '{}': {}"
        ).format(word, str(error))
        ui.message(error_message)

    @staticmethod
    def _read_text(text):
        """Lee un fragmento de texto usando el sintetizador de voz de NVDA.

        Método estático que sirve como callback para ``ResultDialog``.
        Permite que el diálogo de resultados solicite la verbalización
        de secciones específicas del contenido sin depender directamente
        del módulo ``ui`` de NVDA, manteniendo así la separación de capas.

        Args:
            text (str | None): Texto a verbalizar. Si es ``None`` o vacío,
                no se realiza ninguna acción para evitar que el sintetizador
                emita un sonido sin contenido.
        """
        if text:
            # ui.message encola el texto en el sintetizador de voz activo
            # de NVDA y lo verbaliza de forma no bloqueante
            ui.message(text)
