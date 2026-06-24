# -*- coding: utf-8 -*-
# DLEChecker - Diálogo de resultados
# Patrón MVC: Capa View

"""
Diálogo de resultados del plugin DLEChecker para NVDA.

Este módulo implementa la vista ``ResultDialog``, un diálogo modal basado en
``wx.Dialog`` que presenta al usuario las definiciones obtenidas del
Diccionario de la Lengua Española (DLE) de la Real Academia Española.

Rol en la arquitectura (MVC):
    Pertenece a la **capa View**. Su responsabilidad se limita a mostrar el
    contenido recibido del controlador y delegar las acciones del usuario
    (leer, copiar, cerrar) mediante callbacks o métodos del propio diálogo.
    No realiza llamadas de red ni procesamiento de datos.

Características principales:
    * Área de texto multilínea de solo lectura (``wx.TE_READONLY``) con
      soporte de texto enriquecido (``wx.TE_RICH2``) y scroll horizontal.
    * Botón **Leer**: invoca un callback proporcionado por el controlador que
      utiliza el sintetizador de voz de NVDA (``speech.speakMessage``) para
      leer el contenido en voz alta.
    * Botón **Copiar**: copia el texto completo al portapapeles del sistema
      operativo usando ``wx.TheClipboard``.
    * Botón **Salir**: cierra el diálogo devolviendo ``wx.ID_CLOSE``.
    * Tecla **Escape**: atajo de teclado para cerrar, capturado a través de
      ``EVT_CHAR_HOOK``.

Decisiones de diseño:
    * ``wx.STAY_ON_TOP`` y ``Raise()`` garantizan que el diálogo permanezca
      visible cuando NVDA se ejecuta sin ventana propia en primer plano.
    * ``wx.MAXIMIZE_BOX`` permite al usuario maximizar el diálogo para
      consultar definiciones extensas cómodamente.
    * El callback de lectura se inyecta desde el controlador (inversión de
      dependencias) para mantener la vista desacoplada de ``speech``.

Dependencias:
    * ``wx`` — framework de interfaz gráfica multiplataforma.
    * ``gui`` — módulo interno de NVDA que expone ``mainFrame`` (la ventana
      principal del lector de pantalla).
"""

import wx
import gui


class ResultDialog(wx.Dialog):
    """Diálogo modal para mostrar las definiciones encontradas en el DLE.

    Presenta el resultado de la consulta en un área de texto de solo lectura
    y ofrece botones para leer el contenido con el sintetizador de voz de
    NVDA, copiarlo al portapapeles o cerrar el diálogo.

    El flujo típico de uso es:

    Ejemplo::

        def leer_en_voz_alta(texto):
            import speech
            speech.speakMessage(texto)

        dlg = ResultDialog(
            content="casa: Edificio para habitar.",
            on_read_callback=leer_en_voz_alta,
        )
        dlg.ShowModal()
        dlg.Destroy()

    Attributes:
        DEFAULT_WIDTH (int): Ancho predeterminado del diálogo en píxeles.
        DEFAULT_HEIGHT (int): Alto predeterminado del diálogo en píxeles.
        _text_ctrl (wx.TextCtrl | None): Control de texto multilínea de solo
            lectura donde se muestran las definiciones. Es ``None`` hasta
            que ``_setup_ui`` lo inicializa.
        _content (str): Texto completo del resultado de la consulta. Se
            almacena por separado del control para poder acceder a él sin
            depender del estado del widget.
        _on_read_callback (callable | None): Función que el controlador
            proporciona para leer el texto en voz alta. Recibe un único
            argumento ``str`` con el contenido a leer. Si es ``None``, el
            botón «Leer» no realizará ninguna acción.
        _read_button (wx.Button): Botón que activa la lectura del contenido
            mediante el sintetizador de voz.
        _copy_button (wx.Button): Botón que copia el contenido al portapapeles.
        _close_button (wx.Button): Botón que cierra el diálogo.
    """

    # Dimensiones por defecto del diálogo en píxeles.
    # Se eligen valores que ofrecen espacio suficiente para definiciones
    # de longitud media sin ocupar toda la pantalla.
    DEFAULT_WIDTH = 600
    DEFAULT_HEIGHT = 400

    def __init__(self, parent=None, title="", content="", on_read_callback=None):
        """Inicializa el diálogo de resultados y construye la interfaz gráfica.

        Si no se proporciona un padre explícito, se utiliza ``gui.mainFrame``
        para asegurar la correcta integración con la jerarquía de ventanas
        de NVDA y la accesibilidad del lector de pantalla.

        Args:
            parent (wx.Window | None): Ventana padre del diálogo. Si es
                ``None``, se asigna automáticamente ``gui.mainFrame``.
            title (str): Título que se muestra en la barra de título del
                diálogo. Si está vacío, se usa una cadena traducible por
                defecto (``"Resultado del DLE"``).
            content (str): Texto con las definiciones obtenidas del DLE que
                se mostrarán en el área de texto de solo lectura.
            on_read_callback (callable | None): Función invocada al pulsar el
                botón «Leer». Debe aceptar un argumento ``str`` con el texto
                a leer. Habitualmente envuelve ``speech.speakMessage`` de
                NVDA. Si es ``None``, el botón no realizará ninguna acción.
        """
        # Usar gui.mainFrame como padre por defecto para heredar el contexto
        # de accesibilidad de NVDA (anuncios del lector de pantalla, etc.).
        if parent is None:
            parent = gui.mainFrame

        if not title:
            # Translators: Título del diálogo de resultados
            title = _("Resultado del DLE")

        # Se incluyen varios estilos complementarios:
        # - DEFAULT_DIALOG_STYLE: barra de título, botón de cierre, etc.
        # - RESIZE_BORDER: permite redimensionar para definiciones largas.
        # - MAXIMIZE_BOX: habilita el botón de maximizar en la barra.
        # - STAY_ON_TOP: impide que el diálogo quede oculto detrás de otras
        #   ventanas, especialmente importante cuando NVDA no tiene ventana
        #   propia visible en primer plano.
        super(ResultDialog, self).__init__(
            parent,
            title=title,
            size=(self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.STAY_ON_TOP
        )

        # Almacenar el contenido como atributo para poder acceder a él
        # desde los manejadores de eventos sin depender del widget de texto.
        self._content = content
        self._text_ctrl = None
        # Guardar el callback de lectura inyectado por el controlador.
        # Se usa inversión de dependencias: la vista no importa 'speech',
        # sino que recibe la función de lectura desde fuera.
        self._on_read_callback = on_read_callback
        self._setup_ui()
        self._bind_events()
        self._center_dialog()
        # Raise() fuerza que la ventana pase al primer plano del escritorio,
        # complementando STAY_ON_TOP en escenarios multitarea.
        self.Raise()

    def _setup_ui(self):
        """Configura la interfaz de usuario del diálogo de resultados.

        Construye el layout vertical con tres secciones:

        1. Área de texto multilínea de solo lectura con el contenido de las
           definiciones.
        2. Línea separadora horizontal.
        3. Fila horizontal de botones (Leer, Copiar, Salir).

        Se utiliza un ``wx.BoxSizer(wx.VERTICAL)`` como sizer principal y
        un ``wx.BoxSizer(wx.HORIZONTAL)`` para los botones.
        """
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Área de texto de solo lectura para mostrar las definiciones.
        # - TE_MULTILINE: permite varias líneas (necesario para definiciones
        #   extensas con múltiples acepciones).
        # - TE_READONLY: impide la edición por parte del usuario.
        # - TE_RICH2: habilita texto enriquecido (soporte de fuentes y
        #   colores) por si en el futuro se quiere resaltar acepciones.
        # - HSCROLL: añade barra de scroll horizontal para líneas largas.
        # El proportion=1 en Add hace que el control se expanda verticalmente
        # y ocupe todo el espacio disponible.
        self._text_ctrl = wx.TextCtrl(
            self,
            value=self._content,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL
        )
        main_sizer.Add(self._text_ctrl, 1, wx.ALL | wx.EXPAND, 10)

        # Línea separadora horizontal entre el área de texto y los botones.
        main_sizer.Add(wx.StaticLine(self), 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        # Panel de botones dispuestos horizontalmente.
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Translators: Botón para leer las definiciones con el lector de pantalla.
        # El carácter '&' define 'L' como tecla aceleradora (Alt+L).
        self._read_button = wx.Button(self, label=_("&Leer"))
        button_sizer.Add(self._read_button, 0, wx.ALL, 5)

        # Translators: Botón para copiar las definiciones al portapapeles.
        # El carácter '&' define 'C' como tecla aceleradora (Alt+C).
        self._copy_button = wx.Button(self, label=_("&Copiar"))
        button_sizer.Add(self._copy_button, 0, wx.ALL, 5)

        # Translators: Botón para cerrar el diálogo.
        # Se usa wx.ID_CLOSE como ID estándar para que el sistema operativo
        # lo reconozca como botón de cierre nativo.
        self._close_button = wx.Button(self, wx.ID_CLOSE, _("&Salir"))
        # SetDefault marca «Salir» como botón por defecto, de forma que
        # pulsar Enter en cualquier parte del diálogo (excepto donde se
        # capture explícitamente) cierra la ventana.
        self._close_button.SetDefault()
        button_sizer.Add(self._close_button, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        self.SetSizer(main_sizer)

    def _bind_events(self):
        """Vincula los eventos de los botones y del teclado a sus manejadores.

        Se conectan los tres botones a sus respectivos callbacks y se
        intercepta ``EVT_CHAR_HOOK`` a nivel de diálogo para capturar la
        tecla Escape antes de que llegue a otros widgets.
        """
        self._read_button.Bind(wx.EVT_BUTTON, self._on_read)
        self._copy_button.Bind(wx.EVT_BUTTON, self._on_copy)
        self._close_button.Bind(wx.EVT_BUTTON, self._on_close)
        # EVT_CHAR_HOOK se dispara antes que cualquier otro evento de
        # teclado, lo que permite interceptar Escape de forma global
        # en el diálogo sin importar qué widget tenga el foco.
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _on_read(self, event):
        """Manejador del botón «Leer».

        Invoca el callback de lectura proporcionado por el controlador,
        pasándole el contenido completo de las definiciones. El callback
        típicamente llama a ``speech.speakMessage()`` de NVDA para que el
        sintetizador de voz lea el texto en voz alta.

        No se realiza ninguna acción si no hay callback configurado o si
        el contenido está vacío, evitando llamadas innecesarias al
        sintetizador.

        Args:
            event (wx.CommandEvent): Evento de clic del botón. No se
                propaga porque la acción se gestiona íntegramente aquí.
        """
        # Verificar ambas condiciones: que exista un callback y que haya
        # contenido real para leer. Esto evita invocar el sintetizador
        # con una cadena vacía.
        if self._on_read_callback and self._content:
            self._on_read_callback(self._content)

    def _on_copy(self, event):
        """Manejador del botón «Copiar».

        Copia el contenido completo de las definiciones al portapapeles del
        sistema operativo usando la API de wx. El portapapeles se abre y
        cierra explícitamente para seguir las buenas prácticas de wx y
        evitar bloqueos del recurso compartido.

        Args:
            event (wx.CommandEvent): Evento de clic del botón. No se
                propaga porque la acción se gestiona íntegramente aquí.
        """
        # Comprobar que hay contenido y que el portapapeles puede abrirse.
        # wx.TheClipboard.Open() puede fallar si otra aplicación lo tiene
        # bloqueado; en ese caso simplemente no se copia.
        if self._content and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self._content))
            wx.TheClipboard.Close()

    def _on_close(self, event):
        """Manejador del botón «Salir».

        Cierra el diálogo modal devolviendo ``wx.ID_CLOSE`` como código de
        retorno. El controlador puede inspeccionar este valor si necesita
        distinguir entre distintas formas de cerrar el diálogo.

        Args:
            event (wx.CommandEvent): Evento de clic del botón o evento
                sintético generado por el manejador de teclado.
        """
        self.EndModal(wx.ID_CLOSE)

    def _on_key(self, event):
        """Manejador global de atajos de teclado del diálogo.

        Intercepta las pulsaciones de tecla a nivel de diálogo (antes de
        que lleguen a los widgets hijos) para ofrecer atajos de teclado
        adicionales. Actualmente solo captura la tecla **Escape** para
        cerrar el diálogo, imitando el comportamiento estándar de los
        diálogos del sistema operativo.

        Las teclas no reconocidas se propagan con ``event.Skip()`` para
        que los widgets hijos puedan procesarlas normalmente.

        Args:
            event (wx.KeyEvent): Evento de teclado capturado por
                ``EVT_CHAR_HOOK``.
        """
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_ESCAPE:
            # Delegar en _on_close para centralizar la lógica de cierre
            # en un único punto, facilitando el mantenimiento.
            self._on_close(event)
        else:
            # Propagar el evento al widget que tiene el foco para que
            # funcionen correctamente las teclas de navegación, copia
            # (Ctrl+C nativa), etc.
            event.Skip()

    def _center_dialog(self):
        """Centra el diálogo en la pantalla del usuario.

        Calcula manualmente la posición centrada a partir de la resolución
        del monitor y las dimensiones actuales del diálogo. Se usa
        ``max(0, …)`` para evitar coordenadas negativas en pantallas
        pequeñas donde el diálogo podría ser más grande que el área visible.
        """
        # Obtener las dimensiones del monitor primario.
        display_width, display_height = wx.GetDisplaySize()
        dialog_width, dialog_height = self.GetSize()

        # Calcular las coordenadas x e y para centrar horizontalmente
        # y verticalmente. La división entera (//) es suficiente y evita
        # posiciones en subpíxeles.
        x = (display_width - dialog_width) // 2
        y = (display_height - dialog_height) // 2

        # Asegurar que las coordenadas no sean negativas para no posicionar
        # el diálogo fuera de la pantalla visible.
        self.SetPosition((max(0, x), max(0, y)))

    def set_content(self, content):
        """Actualiza el contenido mostrado en el diálogo.

        Permite al controlador cambiar dinámicamente el texto de las
        definiciones después de la creación del diálogo, por ejemplo al
        navegar entre varias definiciones o al recibir resultados
        actualizados.

        Args:
            content (str): Nuevo texto a mostrar en el área de texto de
                solo lectura. Reemplaza completamente el contenido anterior.
        """
        # Actualizar tanto el atributo interno como el widget visual.
        # Se mantienen sincronizados para que get_content() y el texto
        # visible siempre coincidan.
        self._content = content
        if self._text_ctrl:
            self._text_ctrl.SetValue(content)

    def get_content(self):
        """Obtiene el contenido actual del diálogo.

        Devuelve el texto almacenado internamente, que siempre está
        sincronizado con lo que se muestra en el área de texto gracias
        a ``set_content``.

        Returns:
            str: Texto completo de las definiciones actualmente mostradas
                en el diálogo.
        """
        return self._content
