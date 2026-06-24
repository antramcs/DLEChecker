# -*- coding: utf-8 -*-
# DLEChecker - Diálogo de búsqueda
# Patrón MVC: Capa View

"""
Diálogo de búsqueda del plugin DLEChecker para NVDA.

Este módulo implementa la vista ``SearchDialog``, un diálogo modal basado en
``wx.Dialog`` cuya única responsabilidad es solicitar al usuario un término
de búsqueda cuando no existe texto seleccionado en la aplicación activa.

Rol en la arquitectura (MVC):
    Pertenece a la **capa View**. No contiene lógica de negocio ni acceso a
    datos; se limita a recoger la entrada del usuario y devolver el resultado
    al controlador a través del valor de retorno modal (``wx.ID_OK`` o
    ``wx.ID_CANCEL``).

Decisiones de diseño relevantes:
    * Se utiliza ``gui.mainFrame`` como ventana padre predeterminada para
      garantizar que el diálogo se integre correctamente con la jerarquía de
      ventanas de NVDA y sea accesible al lector de pantalla.
    * El estilo ``wx.STAY_ON_TOP`` asegura que el diálogo permanezca visible
      incluso cuando NVDA ejecuta en segundo plano.
    * ``wx.TE_PROCESS_ENTER`` permite que la tecla Enter en el campo de texto
      funcione como atajo para confirmar sin necesidad de hacer clic en el
      botón «Consultar».

Dependencias:
    * ``wx`` — framework de interfaz gráfica multiplataforma.
    * ``gui`` — módulo interno de NVDA que expone ``mainFrame`` (la ventana
      principal del lector de pantalla).
"""

import wx
import gui


class SearchDialog(wx.Dialog):
    """Diálogo modal para que el usuario introduzca un término de búsqueda.

    Se muestra cuando el usuario activa el atajo de teclado del plugin y no
    hay texto seleccionado en la aplicación activa. Contiene un campo de
    texto con soporte para la tecla Enter y botones estándar de confirmación
    y cancelación.

    El flujo típico de uso es:

    Ejemplo::

        dlg = SearchDialog(title="Buscar en el DLE")
        if dlg.ShowModal() == wx.ID_OK:
            termino = dlg.get_search_term()
            # …procesar el término…
        dlg.Destroy()

    Attributes:
        _text_ctrl (wx.TextCtrl | None): Control de entrada de texto donde el
            usuario escribe el término a buscar. Es ``None`` hasta que
            ``_setup_ui`` lo inicializa.
    """

    def __init__(self, parent=None, title="", message=""):
        """Inicializa el diálogo de búsqueda y construye la interfaz gráfica.

        Si no se proporciona un padre explícito, se utiliza ``gui.mainFrame``
        para que el diálogo herede el contexto de accesibilidad de NVDA y
        aparezca correctamente ante el lector de pantalla.

        Args:
            parent (wx.Window | None): Ventana padre del diálogo. Si es
                ``None``, se asigna automáticamente ``gui.mainFrame`` como
                padre, lo cual es necesario para que el foco y la lectura de
                pantalla funcionen correctamente en NVDA.
            title (str): Título que se muestra en la barra de título del
                diálogo. Si está vacío, se usa una cadena traducible por
                defecto.
            message (str): Texto descriptivo que se muestra encima del campo
                de entrada, indicando al usuario qué debe escribir. Si está
                vacío, se usa una cadena traducible por defecto.
        """
        # Usar gui.mainFrame como padre cuando no se proporciona uno explícito.
        # Esto es necesario para la correcta integración con la jerarquía de
        # ventanas de NVDA y para que el lector de pantalla anuncie el diálogo.
        if parent is None:
            parent = gui.mainFrame

        if not title:
            # Translators: Título del diálogo de búsqueda
            title = _("Consultar en el DLE")
        if not message:
            # Translators: Mensaje del diálogo de búsqueda
            message = _("Introduce la palabra que deseas consultar:")

        # Se combina DEFAULT_DIALOG_STYLE con RESIZE_BORDER (permite al usuario
        # redimensionar) y STAY_ON_TOP (mantiene el diálogo por encima de todas
        # las ventanas, imprescindible cuando NVDA no tiene ventana propia
        # visible y el diálogo podría quedar oculto).
        super(SearchDialog, self).__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP
        )

        # Se inicializa a None y se asigna en _setup_ui para evitar accesos
        # prematuros antes de que el control exista realmente en pantalla.
        self._text_ctrl = None
        self._setup_ui(message)
        self._bind_events()
        # Raise() fuerza que la ventana pase al primer plano del escritorio,
        # complementando STAY_ON_TOP en escenarios donde el foco está en
        # otra aplicación.
        self.Raise()

    def _setup_ui(self, message):
        """Configura la interfaz de usuario del diálogo.

        Construye el layout vertical con tres bloques:

        1. Etiqueta de texto estático con el mensaje descriptivo.
        2. Campo de texto editable (``wx.TextCtrl``) con estilo
           ``TE_PROCESS_ENTER`` para capturar la tecla Enter.
        3. Barra de botones estándar (Consultar / Cancelar).

        El diseño utiliza ``wx.BoxSizer(wx.VERTICAL)`` para apilar los
        elementos de arriba abajo, y ``SetSizerAndFit`` para que el diálogo
        ajuste automáticamente su tamaño al contenido mínimo.

        Args:
            message (str): Texto descriptivo que se muestra como etiqueta
                encima del campo de entrada, orientando al usuario sobre
                qué debe escribir.
        """
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Etiqueta estática que describe la acción esperada al usuario.
        # wx.EXPAND hace que ocupe todo el ancho disponible para que la
        # etiqueta se lea correctamente con lectores de pantalla.
        label = wx.StaticText(self, label=message)
        main_sizer.Add(label, 0, wx.ALL | wx.EXPAND, 10)

        # Campo de texto donde el usuario escribe la palabra a buscar.
        # TE_PROCESS_ENTER permite interceptar la tecla Enter para enviar
        # el formulario directamente, sin necesidad de hacer clic en el
        # botón «Consultar». El ancho mínimo de 300 px ofrece espacio
        # cómodo para palabras largas o frases compuestas.
        self._text_ctrl = wx.TextCtrl(
            self,
            style=wx.TE_PROCESS_ENTER,
            size=(300, -1)
        )
        main_sizer.Add(self._text_ctrl, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        # Línea separadora horizontal entre el campo de texto y los botones,
        # para mejorar la organización visual del diálogo.
        main_sizer.Add(wx.StaticLine(self), 0, wx.ALL | wx.EXPAND, 5)

        # Barra de botones estándar del diálogo. StdDialogButtonSizer
        # organiza los botones según las convenciones del sistema operativo
        # (orden y alineación nativos).
        button_sizer = wx.StdDialogButtonSizer()

        # Translators: Botón para realizar la consulta
        # El carácter '&' define 'C' como tecla aceleradora (Alt+C).
        ok_button = wx.Button(self, wx.ID_OK, _("&Consultar"))
        # SetDefault marca este botón como el que se activa al pulsar Enter
        # en cualquier parte del diálogo que no capture explícitamente Enter.
        ok_button.SetDefault()
        button_sizer.AddButton(ok_button)

        # Translators: Botón para cancelar la consulta
        cancel_button = wx.Button(self, wx.ID_CANCEL, _("&Cancelar"))
        button_sizer.AddButton(cancel_button)

        # Realize() finaliza la disposición de los botones según las reglas
        # de diseño del sistema operativo.
        button_sizer.Realize()
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # SetSizerAndFit asigna el sizer y redimensiona el diálogo al
        # tamaño mínimo necesario para contener todos los elementos.
        self.SetSizerAndFit(main_sizer)
        # Centrar en pantalla para que el diálogo aparezca en una posición
        # predecible independientemente de la resolución del monitor.
        self.CenterOnScreen()

        # Establecer el foco en el campo de texto para que el usuario pueda
        # empezar a escribir inmediatamente sin necesidad de hacer clic.
        self._text_ctrl.SetFocus()

    def _bind_events(self):
        """Vincula los eventos de la interfaz a sus manejadores.

        Actualmente solo vincula el evento ``EVT_TEXT_ENTER`` del campo de
        texto, que se dispara cuando el usuario pulsa Enter dentro de él.
        Esto permite confirmar la búsqueda rápidamente con el teclado.
        """
        # Vincular Enter en el campo de texto a _on_enter, que cierra el
        # diálogo con wx.ID_OK si hay un término válido escrito.
        self._text_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_enter)

    def _on_enter(self, event):
        """Manejador para la tecla Enter en el campo de texto.

        Cierra el diálogo con resultado ``wx.ID_OK`` solo si el usuario ha
        introducido al menos un carácter no vacío. Esto evita enviar
        consultas vacías al servicio del DLE.

        Args:
            event (wx.CommandEvent): Evento de tipo ``EVT_TEXT_ENTER``
                generado por el campo de texto. No se propaga (no se
                llama a ``event.Skip()``) porque el diálogo se cierra
                directamente.
        """
        # Solo cerrar el diálogo si hay texto real (no espacios en blanco).
        # get_search_term() ya aplica strip(), así que basta con evaluar
        # la veracidad de la cadena resultante.
        if self.get_search_term():
            self.EndModal(wx.ID_OK)

    def get_search_term(self):
        """Obtiene el término de búsqueda introducido por el usuario.

        Devuelve la cadena limpia (sin espacios al inicio ni al final) que
        el usuario ha escrito en el campo de texto. El controlador utiliza
        este valor para lanzar la consulta al DLE.

        Returns:
            str: Texto introducido con espacios sobrantes eliminados.
                Devuelve una cadena vacía si el control aún no ha sido
                inicializado o si el usuario no ha escrito nada.
        """
        if self._text_ctrl:
            return self._text_ctrl.GetValue().strip()
        return ""

    def set_search_term(self, text):
        """Establece un texto inicial en el campo de búsqueda.

        Útil cuando el controlador desea precargar un término (por ejemplo,
        una búsqueda anterior) para que el usuario pueda editarlo o
        confirmarlo directamente. Tras establecer el texto, se selecciona
        todo el contenido para que el usuario pueda reemplazarlo con solo
        empezar a escribir.

        Args:
            text (str): Texto a colocar en el campo de búsqueda. Si es
                vacío o ``None``, no se realiza ninguna acción para evitar
                sobrescribir contenido ya existente con un valor nulo.
        """
        if self._text_ctrl and text:
            self._text_ctrl.SetValue(text)
            # Seleccionar todo el texto para que el usuario pueda
            # reemplazarlo fácilmente escribiendo encima.
            self._text_ctrl.SelectAll()
