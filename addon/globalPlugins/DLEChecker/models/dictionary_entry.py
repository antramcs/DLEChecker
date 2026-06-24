# -*- coding: utf-8 -*-
# DLEChecker - Modelo de datos para entradas del diccionario
# Patrón MVC: Capa Model

"""
Estructuras de datos del dominio para el plugin DLEChecker.

Este módulo define los dos objetos de datos principales que representan
el resultado de una consulta al DLE:

    - Definition: Una acepción individual (ej: "1. f. Edificio para habitar.").
    - DictionaryEntry: La entrada completa de una palabra, que agrupa todas
      sus acepciones, la etimología, y posibles mensajes de error.

Estos objetos son inmutables en la práctica (propiedades de solo lectura)
y se crean en DLEService._parse_html() tras parsear el HTML del DLE.
El controlador los usa para generar el texto que se muestra al usuario.

Ejemplo de flujo:
    DLEService.search("casa")
        → DLEService._parse_html(html)
            → crea Definition(content="Edificio para habitar.", number=1,
                              category="f.", synonyms=["vivienda", "hogar"],
                              antonyms=[])
            → crea DictionaryEntry(word="casa", definitions=[...],
                                   etymology="Del lat. casa 'choza'.")
        → el controlador llama entry.to_formatted_text() para mostrar al usuario.
"""


class Definition:
    """Representa una acepción individual de una palabra del diccionario.

    Cada acepción del DLE tiene:
        - Un número ordinal (1, 2, 3...).
        - Una categoría gramatical (f., m., adj., tr., interj., etc.).
        - El texto descriptivo de la definición.
        - Opcionalmente, una lista de sinónimos y/o antónimos.

    Las propiedades devuelven copias de las listas internas para evitar
    modificaciones accidentales desde fuera de la clase (encapsulación).

    Ejemplo de salida formateada (to_formatted_text()):
        "1. f. Edificio para habitar. Una casa de ocho plantas.
           Sinónimos: vivienda, inmueble, domicilio
           Antónimos: (no aplica en este caso)"

    Attributes:
        _number (int): Número ordinal de la acepción (1-based).
        _content (str): Texto de la definición sin número ni abreviaturas.
        _category (str): Categoría gramatical abreviada (ej: "f.", "adj.").
        _synonyms (list[str]): Lista de sinónimos asociados a esta acepción.
        _antonyms (list[str]): Lista de antónimos asociados a esta acepción.
    """

    def __init__(self, content, number=0, category="", synonyms=None, antonyms=None):
        """Inicializa una acepción del diccionario.

        Args:
            content (str): Texto de la definición. Se recortan espacios
                sobrantes con strip(). Si es None o vacío, se almacena "".
            number (int): Número ordinal de la acepción (1, 2, 3...).
                Por defecto 0 para acepciones sin numerar.
            category (str): Categoría gramatical abreviada según la RAE
                (ej: "f." para femenino, "adj." para adjetivo, "interj."
                para interjección). Se recortan espacios.
            synonyms (list[str] | None): Lista de sinónimos. Si es None,
                se inicializa como lista vacía.
            antonyms (list[str] | None): Lista de antónimos. Si es None,
                se inicializa como lista vacía.
        """
        self._content = content.strip() if content else ""
        self._number = number
        self._category = category.strip() if category else ""
        # Se usa "if not None" en vez de "or []" porque una lista vacía []
        # es un valor válido y distinto de None (parámetro no proporcionado).
        self._synonyms = synonyms if synonyms is not None else []
        self._antonyms = antonyms if antonyms is not None else []

    @property
    def content(self):
        """str: Texto de la definición, sin número ordinal ni abreviaturas."""
        return self._content

    @property
    def number(self):
        """int: Número ordinal de la acepción (1, 2, 3...)."""
        return self._number

    @property
    def category(self):
        """str: Categoría gramatical abreviada (ej: 'f.', 'adj.', 'interj.')."""
        return self._category

    @property
    def synonyms(self):
        """list[str]: Copia de la lista de sinónimos.

        Se devuelve una copia para preservar la encapsulación: el código
        externo no puede modificar la lista interna del objeto.
        """
        return list(self._synonyms)

    @property
    def antonyms(self):
        """list[str]: Copia de la lista de antónimos.

        Se devuelve una copia por el mismo motivo que en synonyms.
        """
        return list(self._antonyms)

    def has_synonyms(self):
        """Comprueba si esta acepción tiene sinónimos asociados.

        Returns:
            bool: True si la lista de sinónimos contiene al menos un elemento.
        """
        return len(self._synonyms) > 0

    def has_antonyms(self):
        """Comprueba si esta acepción tiene antónimos asociados.

        Returns:
            bool: True si la lista de antónimos contiene al menos un elemento.
        """
        return len(self._antonyms) > 0

    def to_formatted_text(self):
        """Genera una representación textual legible de la acepción.

        Formato de salida:
            "N. CATEGORÍA Texto de la definición.
               Sinónimos: sin1, sin2, sin3
               Antónimos: ant1, ant2"

        Las líneas de sinónimos/antónimos solo aparecen si existen.

        Returns:
            str: Texto formateado listo para mostrar al usuario o para
                lectura por el sintetizador de voz de NVDA.
        """
        parts = []
        # Añadir número ordinal si existe (ej: "1. ")
        if self._number > 0:
            parts.append("{}. ".format(self._number))
        # Añadir categoría gramatical si existe (ej: "f. ")
        if self._category:
            parts.append("{} ".format(self._category))
        # Añadir el texto principal de la definición
        parts.append(self._content)
        # Añadir sinónimos en línea aparte con indentación
        if self._synonyms:
            parts.append("\n   Sinónimos: {}".format(", ".join(self._synonyms)))
        # Añadir antónimos en línea aparte con indentación
        if self._antonyms:
            parts.append("\n   Antónimos: {}".format(", ".join(self._antonyms)))
        return "".join(parts)

    def __repr__(self):
        """Representación para depuración, muestra los primeros 50 chars del contenido."""
        return "Definition(number={}, category='{}', content='{}')".format(
            self._number, self._category, self._content[:50]
        )


class DictionaryEntry:
    """Representa la entrada completa de una palabra en el diccionario.

    Agrupa toda la información que el DLE devuelve para una palabra consultada:
    todas sus acepciones (objetos Definition), la etimología, y un posible
    mensaje de error si la consulta falló.

    Una entrada puede estar en tres estados:
        1. Exitosa: tiene definiciones, sin error. bool(entry) == True.
        2. Vacía: no tiene definiciones ni error. is_empty() == True.
        3. Con error: tiene un mensaje de error. has_error() == True.

    Ejemplo de uso:
        >>> entry = DictionaryEntry(word="casa", definitions=[...],
        ...                         etymology="Del lat. casa 'choza'.")
        >>> if entry:
        ...     print(entry.to_formatted_text())
        >>> if entry.has_error():
        ...     print(entry.error_message)

    Attributes:
        _word (str): Palabra consultada (normalizada).
        _definitions (list[Definition]): Lista de acepciones encontradas.
        _etymology (str): Etimología de la palabra, o "" si no existe.
        _error_message (str): Mensaje de error si la consulta falló, o "".
    """

    def __init__(self, word, definitions=None, etymology="", error_message=""):
        """Inicializa una entrada del diccionario.

        Args:
            word (str): Palabra consultada. Se recortan espacios.
            definitions (list[Definition] | None): Lista de acepciones.
                Si es None, se inicializa como lista vacía.
            etymology (str): Texto de la etimología (ej: "Del lat. casa 'choza'.").
                Se recortan espacios. Si no hay etimología, dejar vacío.
            error_message (str): Mensaje descriptivo del error que ocurrió
                durante la búsqueda. Vacío si la búsqueda fue exitosa.
        """
        self._word = word.strip() if word else ""
        self._definitions = definitions if definitions is not None else []
        self._etymology = etymology.strip() if etymology else ""
        self._error_message = error_message

    @property
    def word(self):
        """str: Palabra que fue consultada en el DLE."""
        return self._word

    @property
    def definitions(self):
        """list[Definition]: Copia de la lista de acepciones encontradas.

        Se devuelve una copia para preservar la encapsulación.
        """
        return list(self._definitions)

    @property
    def etymology(self):
        """str: Etimología de la palabra, o cadena vacía si no está disponible."""
        return self._etymology

    @property
    def error_message(self):
        """str: Mensaje de error de la consulta, o cadena vacía si fue exitosa."""
        return self._error_message

    @property
    def definition_count(self):
        """int: Cantidad de acepciones encontradas para la palabra."""
        return len(self._definitions)

    def is_empty(self):
        """Comprueba si la entrada no contiene ninguna definición.

        Returns:
            bool: True si no se encontraron acepciones para la palabra.
        """
        return len(self._definitions) == 0

    def has_error(self):
        """Comprueba si la consulta produjo un error.

        Returns:
            bool: True si hay un mensaje de error (la consulta falló).
        """
        return bool(self._error_message)

    def add_definition(self, definition):
        """Añade una acepción a la entrada del diccionario.

        Se usa internamente durante el parseo del HTML para construir
        la entrada de forma incremental.

        Args:
            definition (Definition): Objeto Definition a añadir.

        Raises:
            TypeError: Si el argumento no es una instancia de Definition.
                Esto previene que se añadan objetos incorrectos por error.
        """
        if not isinstance(definition, Definition):
            raise TypeError("Se esperaba una instancia de Definition, se recibió {}".format(
                type(definition).__name__
            ))
        self._definitions.append(definition)

    def to_formatted_text(self):
        """Genera un texto completo y legible con toda la información de la entrada.

        Formato de salida:
            Definiciones de: casa
            ========================================
            Etimología: Del lat. casa 'choza'.

            1. f. Edificio para habitar.
               Sinónimos: vivienda, inmueble
            2. f. piso (‖ vivienda).
            ...

        Si la entrada tiene error, devuelve solo el mensaje de error.
        Si está vacía, devuelve un mensaje indicándolo.

        Returns:
            str: Texto formateado para mostrar al usuario o leer con NVDA.
        """
        # Si hubo un error en la consulta, devolver solo el mensaje de error
        if self.has_error():
            return self._error_message

        # Si no hay definiciones, informar al usuario
        if self.is_empty():
            return "No se encontraron definiciones para '{}'.".format(self._word)

        lines = []
        # Encabezado con la palabra consultada
        lines.append("Definiciones de: {}".format(self._word))
        lines.append("=" * 40)

        # Etimología (solo si está disponible)
        if self._etymology:
            lines.append("Etimología: {}".format(self._etymology))
            lines.append("")  # Línea en blanco para separar de las definiciones

        # Cada definición se formatea con su método to_formatted_text()
        for definition in self._definitions:
            lines.append(definition.to_formatted_text())

        return "\n".join(lines)

    def __repr__(self):
        """Representación para depuración con resumen del estado."""
        return "DictionaryEntry(word='{}', definitions={}, has_error={})".format(
            self._word, self.definition_count, self.has_error()
        )

    def __bool__(self):
        """Permite usar la entrada en contextos booleanos (ej: if entry: ...).

        Una entrada es "verdadera" si tiene definiciones y no tiene error.
        Esto facilita verificaciones rápidas como:
            entry = service.search("casa")
            if entry:
                mostrar_resultados(entry)

        Returns:
            bool: True si hay al menos una definición y no hay error.
        """
        return not self.is_empty() and not self.has_error()
