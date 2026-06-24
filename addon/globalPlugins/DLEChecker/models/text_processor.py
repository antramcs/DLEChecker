# -*- coding: utf-8 -*-
# DLEChecker - Procesamiento y limpieza de texto
# Patrón MVC: Capa Model

"""
Utilidades estáticas para limpieza, normalización y validación de texto de entrada.

Este módulo proporciona la clase ``TextProcessor``, que contiene métodos estáticos
encargados de sanear el texto introducido por el usuario antes de enviarlo como
consulta al servicio de scraping del DLE (Diccionario de la Lengua Española).

Rol en la arquitectura:
    Forma parte de la capa Model del patrón MVC. Es utilizada por el controlador
    del plugin (capa Controller) para preprocesar la selección de texto del usuario
    en NVDA antes de pasarla al servicio ``DLEService`` para la consulta.

Operaciones principales:
    - **Limpieza** (``clean``): Elimina caracteres no válidos para una búsqueda
      en el DLE, conservando letras españolas acentuadas, ñ, espacios y guiones.
    - **Normalización Unicode** (``clean``): Aplica normalización NFC para
      garantizar que los caracteres acentuados se representen como un solo
      punto de código (ej: ``á`` como U+00E1, no como ``a`` + U+0301).
      Esto es crítico para el español, donde los acentos alteran el significado.
    - **Validación** (``is_valid``): Verifica que el texto limpio cumple con
      las restricciones de longitud antes de realizar la consulta.
    - **Extracción** (``extract_first_word``): Permite obtener solo la primera
      palabra cuando el usuario selecciona una frase completa.
    - **Truncamiento** (``truncate``): Corta el texto a la longitud máxima
      permitida como medida de seguridad.

Dependencias:
    - ``re``: Para patrones de expresiones regulares (limpieza de caracteres).
    - ``unicodedata``: Para normalización Unicode NFC.

Ejemplo de uso:
    >>> from models.text_processor import TextProcessor
    >>> TextProcessor.clean("  ¡Hola, mundo! 123 ")
    'hola mundo'
    >>> TextProcessor.is_valid("casa")
    True
    >>> TextProcessor.is_valid("")
    False
    >>> TextProcessor.extract_first_word("buenas tardes amigo")
    'buenas'
"""

import re
import unicodedata


class TextProcessor:
    """Procesador de texto para limpiar y normalizar entradas del usuario.

    Clase puramente utilitaria (todos sus métodos son estáticos) que encapsula
    las reglas de saneamiento de texto específicas para consultas al DLE.
    No se instancia: se usa directamente como ``TextProcessor.clean(texto)``.

    Las reglas de limpieza están diseñadas para el idioma español:
    - Se conservan letras acentuadas (á, é, í, ó, ú), la diéresis (ü),
      la eñe (ñ), espacios y guiones.
    - Se eliminan signos de puntuación, números, emojis y otros caracteres
      especiales que no forman parte de un término de búsqueda válido.

    Attributes:
        _ALLOWED_CHARS_PATTERN (re.Pattern): Expresión regular compilada que
            identifica caracteres NO permitidos (todo lo que no sea letra
            española, espacio o guion). Se usa con ``sub()`` para eliminarlos.
        _MULTI_SPACE_PATTERN (re.Pattern): Expresión regular compilada que
            detecta secuencias de uno o más espacios en blanco consecutivos,
            para normalizarlos a un único espacio.
        MAX_TERM_LENGTH (int): Longitud máxima permitida para un término de
            búsqueda (100 caracteres). Límite de seguridad para evitar
            consultas excesivamente largas al DLE.
        MIN_TERM_LENGTH (int): Longitud mínima requerida para un término de
            búsqueda (1 carácter). Previene consultas vacías.

    Ejemplo:
        >>> TextProcessor.clean("  ¡Hola, mundo! ")
        'hola mundo'
        >>> TextProcessor.is_valid("casa")
        True
        >>> TextProcessor.is_valid("")
        False
        >>> TextProcessor.extract_first_word("buenos días")
        'buenos'
    """

    # Patrón que identifica caracteres NO permitidos en una consulta al DLE.
    # Usa clase de caracteres negada [^...] para capturar todo excepto:
    # - Letras minúsculas con acentos y diéresis del español (a-z, á, é, í, ó, ú, ü, ñ)
    # - Espacios en blanco (\s)
    # - Guiones (\-)  — necesarios para palabras compuestas como "hispano-americano"
    # La bandera IGNORECASE extiende la coincidencia a sus equivalentes mayúsculas
    _ALLOWED_CHARS_PATTERN = re.compile(r"[^a-záéíóúüñ\s\-]", re.IGNORECASE)

    # Patrón para detectar secuencias de espacios en blanco múltiples.
    # Se usa para colapsar "hola    mundo" en "hola mundo", mejorando
    # la calidad del texto antes de enviarlo como consulta
    _MULTI_SPACE_PATTERN = re.compile(r"\s+")

    # Límite superior de longitud: previene consultas abusivas o accidentales
    # al DLE (ej: el usuario selecciona un párrafo entero por error)
    MAX_TERM_LENGTH = 100

    # Límite inferior de longitud: al menos 1 carácter útil tras la limpieza
    MIN_TERM_LENGTH = 1

    @staticmethod
    def clean(text):
        """Limpia el texto de entrada eliminando caracteres no válidos para el DLE.

        Aplica una cadena de transformaciones diseñada para convertir texto
        arbitrario del usuario en un término de búsqueda válido para el DLE:

        1. **Normalización Unicode NFC**: Convierte secuencias descompuestas
           (ej: ``a`` + acento combinante) en su forma precompuesta (ej: ``á``).
           Esto es esencial para el español porque los acentos deben preservarse
           y el DLE espera la forma precompuesta.
        2. **Conversión a minúsculas**: El DLE no distingue mayúsculas/minúsculas.
        3. **Eliminación de caracteres no permitidos**: Se eliminan números,
           signos de puntuación (¡!, ¿?, etc.), emojis y cualquier carácter que
           no sea letra española, espacio o guion.
        4. **Normalización de espacios**: Secuencias de espacios múltiples se
           reducen a uno solo.
        5. **Strip final**: Se eliminan espacios al inicio y final.

        Args:
            text (str | None): Texto a limpiar. Puede ser ``None`` o cadena vacía,
                en cuyo caso se retorna cadena vacía sin procesamiento.

        Returns:
            str: Texto limpio y normalizado, listo para ser usado como término
                de búsqueda en el DLE. Cadena vacía si la entrada era nula o vacía.
        """
        # Guardia temprana: retornar vacío si no hay texto
        if not text:
            return ""

        # Paso 1: Normalización Unicode NFC (Canonical Decomposition followed by
        # Canonical Composition). Crítico para el español porque los acentos pueden
        # venir descompuestos desde ciertas fuentes (ej: macOS, algunos editores).
        # NFC garantiza que "á" sea U+00E1, no "a" + U+0301.
        cleaned = unicodedata.normalize("NFC", text)

        # Paso 2: Convertir a minúsculas para uniformidad en la consulta
        cleaned = cleaned.lower()

        # Paso 3: Eliminar todos los caracteres que no son letras españolas,
        # espacios ni guiones. Esto descarta puntuación, números, emojis, etc.
        cleaned = TextProcessor._ALLOWED_CHARS_PATTERN.sub("", cleaned)

        # Paso 4: Colapsar múltiples espacios consecutivos en uno solo.
        # Necesario porque la eliminación de caracteres puede dejar huecos
        # (ej: "hola, mundo" → "hola mundo" → necesita normalizar el espacio doble)
        cleaned = TextProcessor._MULTI_SPACE_PATTERN.sub(" ", cleaned)

        # Paso 5: Eliminar espacios sobrantes al inicio y final
        cleaned = cleaned.strip()

        return cleaned

    @staticmethod
    def normalize(text):
        """Normaliza el texto a minúsculas preservando todos los caracteres.

        A diferencia de ``clean()``, este método **no elimina** caracteres
        especiales ni signos de puntuación. Solo aplica conversión a minúsculas
        y eliminación de espacios sobrantes al inicio y final. Es útil cuando
        se necesita una versión normalizada del texto para comparaciones internas
        sin perder información.

        Args:
            text (str | None): Texto a normalizar. Puede ser ``None`` o cadena
                vacía, en cuyo caso se retorna cadena vacía.

        Returns:
            str: Texto en minúsculas sin espacios sobrantes al inicio y final.
                Cadena vacía si la entrada era nula o vacía.
        """
        if not text:
            return ""
        return text.lower().strip()

    @staticmethod
    def is_valid(text):
        """Verifica si el texto es apto para realizar una búsqueda en el DLE.

        Primero limpia el texto con ``clean()`` y luego verifica que la longitud
        resultante esté dentro de los límites permitidos (entre ``MIN_TERM_LENGTH``
        y ``MAX_TERM_LENGTH``). Esto evita enviar consultas vacías (después de
        limpiar todo era basura) o excesivamente largas al servicio del DLE.

        Args:
            text (str | None): Texto a validar. Puede ser ``None`` o cadena vacía.

        Returns:
            bool: ``True`` si el texto limpio tiene entre ``MIN_TERM_LENGTH`` y
                ``MAX_TERM_LENGTH`` caracteres (inclusive); ``False`` en caso
                contrario o si el texto es nulo/vacío.
        """
        # Guardia temprana para valores falsy (None, "", 0, etc.)
        if not text:
            return False

        # Validar sobre el texto ya limpio, no sobre el original,
        # porque lo que importa es lo que realmente se enviará al DLE
        cleaned = TextProcessor.clean(text)
        return (
            len(cleaned) >= TextProcessor.MIN_TERM_LENGTH
            and len(cleaned) <= TextProcessor.MAX_TERM_LENGTH
        )

    @staticmethod
    def extract_first_word(text):
        """Extrae la primera palabra del texto después de limpiarlo.

        Útil cuando el usuario selecciona accidentalmente una frase completa
        o un fragmento de texto largo en NVDA, pero solo necesitamos consultar
        la primera palabra en el DLE. El texto se limpia primero con ``clean()``
        para asegurar que la palabra extraída sea válida.

        Args:
            text (str | None): Texto del cual extraer la primera palabra. Puede
                ser ``None`` o cadena vacía.

        Returns:
            str: Primera palabra del texto limpio. Cadena vacía si el texto
                es nulo, vacío, o no contiene palabras válidas tras la limpieza.
        """
        if not text:
            return ""

        # Limpiar primero para asegurar que solo queden caracteres válidos
        cleaned = TextProcessor.clean(text)
        # split() sin argumentos divide por cualquier espacio en blanco y
        # descarta cadenas vacías automáticamente
        words = cleaned.split()
        # Retornar la primera palabra si existe, o cadena vacía
        return words[0] if words else ""

    @staticmethod
    def truncate(text, max_length=None):
        """Trunca el texto a una longitud máxima especificada.

        Medida de seguridad para garantizar que ningún texto exceda el límite
        establecido antes de ser procesado o enviado al DLE. Si el texto ya
        es más corto que ``max_length``, se retorna sin modificar.

        Se aplica ``strip()`` al resultado truncado para evitar que el corte
        deje un espacio suelto al final (ej: "hola m" → "hola m" se limpia
        a "hola m", pero podría quedar "hola " → "hola").

        Args:
            text (str | None): Texto a truncar. Si es ``None`` o vacío, se
                retorna cadena vacía.
            max_length (int | None): Longitud máxima deseada en caracteres.
                Si es ``None``, se usa ``MAX_TERM_LENGTH`` (100) como valor
                por defecto.

        Returns:
            str: Texto truncado a ``max_length`` caracteres como máximo,
                sin espacios sobrantes al final. Cadena vacía si la entrada
                era nula o vacía.
        """
        # Usar el límite de clase si no se proporcionó uno explícito
        if max_length is None:
            max_length = TextProcessor.MAX_TERM_LENGTH

        # Si el texto es nulo/vacío o ya cumple el límite, retornar sin modificar
        if not text or len(text) <= max_length:
            return text or ""

        # Truncar y limpiar espacio residual al final del corte
        return text[:max_length].strip()
