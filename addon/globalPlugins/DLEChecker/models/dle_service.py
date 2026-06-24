# -*- coding: utf-8 -*-
# DLEChecker - Servicio de consulta al DLE
# Patrón MVC: Capa Model
# Este módulo forma parte del patrón Modelo-Vista-Controlador (MVC) y encapsula
# toda la lógica de acceso a datos del Diccionario de la Lengua Española.

"""
Módulo de servicio para la consulta del Diccionario de la Lengua Española (DLE).

Este módulo implementa la capa de acceso a datos del complemento DLEChecker para
NVDA, encargándose de realizar peticiones HTTP al sitio web del DLE de la Real
Academia Española (https://dle.rae.es) y de transformar las respuestas HTML en
objetos de dominio (DictionaryEntry / Definition) que el resto de la aplicación
puede consumir sin conocer los detalles del scraping.

Rol en la arquitectura (MVC):
    Este módulo pertenece a la capa **Model**. Su responsabilidad exclusiva es
    obtener y parsear datos del DLE. No contiene lógica de presentación ni de
    interfaz de usuario.

Dependencias externas:
    - **cloudscraper**: Se utiliza en lugar de ``requests`` o ``urllib`` porque
      el sitio dle.rae.es emplea protección anti-bot de Cloudflare. cloudscraper
      resuelve los desafíos JavaScript de Cloudflare de forma transparente.
    - **BeautifulSoup** (bs4): Parser HTML utilizado con el backend ``html.parser``
      (incluido en la biblioteca estándar de Python) para extraer datos del DOM.

Dependencias internas:
    - ``dictionary_entry.DictionaryEntry``: Objeto de dominio que representa una
      entrada completa del diccionario (palabra, etimología, definiciones).
    - ``dictionary_entry.Definition``: Objeto de dominio para cada acepción
      individual (contenido, número, categoría gramatical, sinónimos, antónimos).
    - ``text_processor.TextProcessor``: Utilidad para limpiar y validar el texto
      de entrada del usuario antes de enviarlo al DLE.

Estructura HTML del DLE (referencia 2025):
    El HTML devuelto por dle.rae.es sigue esta jerarquía simplificada::

        <article>
            <div class="n2 c-text-intro">Etimología...</div>
            <ol class="c-definitions">
                <li class="j" id="...">
                    <div class="c-definitions__item" role="definition">
                        <div>
                            <span class="n_acep">1. </span>
                            <abbr class="d" title="...">interj.</abbr>
                            Texto de la definición.
                        </div>
                    </div>
                    <div class="c-definitions__item-footer">
                        <div class="c-word-list">
                            <abbr class="sin-header-inline">Sin.:</abbr>
                            <span class="sin">sinónimo1</span>, ...
                        </div>
                    </div>
                </li>
                ...
            </ol>
        </article>

Jerarquía de excepciones:
    - ``DLEServiceError`` (base)
        - ``DLEConnectionError``: Problemas de red o respuestas HTTP inesperadas.
        - ``DLEParsingError``: El HTML recibido no cumple la estructura esperada.
        - ``DLENotFoundError``: La palabra buscada no existe en el DLE.
"""

import os
import sys
import logging
import re

# --- Configuración del path para dependencias empaquetadas ---
# El complemento distribuye sus dependencias (cloudscraper, bs4, etc.) dentro de
# una carpeta "libs" junto al paquete principal.  Se agrega al inicio de sys.path
# para que Python las encuentre antes que cualquier versión del sistema, evitando
# conflictos de versiones con otras extensiones de NVDA.
_libs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "libs")
if _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

# cloudscraper sustituye a requests porque dle.rae.es emplea Cloudflare
import cloudscraper
# BeautifulSoup se usa con html.parser (stdlib) para parsear el DOM del DLE
from bs4 import BeautifulSoup

from .dictionary_entry import DictionaryEntry, Definition
from .text_processor import TextProcessor

# Logger del módulo — utiliza la jerarquía estándar de logging de Python para que
# el nivel de detalle se controle desde la configuración global de la aplicación.
log = logging.getLogger(__name__)


# =============================================================================
# Jerarquía de excepciones del servicio DLE
# =============================================================================
# Se utiliza una jerarquía propia para que los consumidores del servicio puedan
# capturar errores a distintos niveles de granularidad:
#   - ``DLEServiceError`` atrapa CUALQUIER error del servicio.
#   - Las subclases permiten tratamiento específico (reintento en conexión,
#     mensaje amigable en "no encontrada", etc.).


class DLEServiceError(Exception):
    """Excepción base para todos los errores del servicio DLE.

    Hereda directamente de ``Exception``. Cualquier código que desee capturar
    genéricamente todos los errores producidos por ``DLEService`` puede hacer
    ``except DLEServiceError``.

    Ejemplo:
        >>> try:
        ...     entry = servicio.search("xyznoexiste")
        ... except DLEServiceError as e:
        ...     print(f"Error del DLE: {e}")
    """
    pass


class DLEConnectionError(DLEServiceError):
    """Error de conexión al servidor del DLE.

    Se lanza cuando la petición HTTP no se puede completar con éxito. Posibles
    causas incluyen:
        - Sin conexión a Internet.
        - Tiempo de espera agotado (timeout).
        - Código de respuesta HTTP distinto de 200 y 404.
        - Cloudflare bloquea la solicitud.
    """
    pass


class DLEParsingError(DLEServiceError):
    """Error al parsear la respuesta HTML del DLE.

    Se lanza cuando BeautifulSoup no puede interpretar el contenido HTML recibido
    o cuando la estructura del DOM no coincide con la esperada. Esto puede ocurrir
    si la RAE modifica el diseño de la página del DLE.
    """
    pass


class DLENotFoundError(DLEServiceError):
    """La palabra consultada no fue encontrada en el DLE.

    Se lanza tanto cuando el servidor responde con HTTP 404 como cuando el HTML
    contiene el mensaje explícito "La entrada no se encuentra en el Diccionario".
    """
    pass


class DLEService:
    """Servicio principal para consultar definiciones en el Diccionario de la Lengua Española.

    Esta clase encapsula todo el ciclo de vida de una consulta al DLE:

    1. **Validación**: Limpia y valida la palabra de entrada con ``TextProcessor``.
    2. **Petición HTTP**: Descarga el HTML de la página de la palabra usando
       ``cloudscraper`` (necesario para evadir la protección Cloudflare del sitio).
    3. **Parsing HTML**: Extrae etimología, definiciones, categorías gramaticales,
       sinónimos y antónimos del DOM con ``BeautifulSoup``.
    4. **Construcción del modelo**: Devuelve un objeto ``DictionaryEntry`` listo
       para ser consumido por la capa de presentación (Vista/Controlador).

    Atributos de clase:
        BASE_URL (str): URL raíz del Diccionario de la Lengua Española de la RAE.
            Todas las consultas se construyen como ``{BASE_URL}/{palabra}``.

    Atributos de instancia:
        _scraper (cloudscraper.CloudScraper): Instancia reutilizable de
            cloudscraper que mantiene la sesión HTTP y las cookies de Cloudflare
            entre consultas sucesivas, lo que mejora el rendimiento y reduce la
            probabilidad de ser bloqueado.

    Ejemplo de uso:
        >>> servicio = DLEService()
        >>> entrada = servicio.search("resiliencia")
        >>> if entrada.definitions:
        ...     for d in entrada.definitions:
        ...         print(f"{d.number}. ({d.category}) {d.content}")
        ... else:
        ...     print(entrada.error_message)
    """

    BASE_URL = "https://dle.rae.es"

    def __init__(self):
        """Inicializa el servicio creando una instancia de cloudscraper.

        Se crea un único ``CloudScraper`` que se reutiliza en todas las búsquedas
        de esta instancia.  Reutilizar la sesión permite aprovechar las cookies
        de Cloudflare ya resueltas, evitando resolver el desafío anti-bot en
        cada petición.
        """
        self._scraper = cloudscraper.create_scraper()

    def search(self, word):
        """Busca una palabra en el DLE y devuelve un objeto ``DictionaryEntry``.

        Este es el método público principal del servicio. Coordina la validación,
        la petición HTTP, el parsing del HTML y el manejo de errores, devolviendo
        siempre un ``DictionaryEntry`` (nunca lanza excepciones al llamador).

        Flujo interno:
            1. Limpia la entrada con ``TextProcessor.clean()``.
            2. Valida la entrada con ``TextProcessor.is_valid()``.
            3. Descarga el HTML con ``_fetch_html()``.
            4. Parsea el HTML con ``_parse_html()``.
            5. En caso de error, devuelve un ``DictionaryEntry`` con
               ``error_message`` descriptivo en lugar de lanzar una excepción.

        Args:
            word (str): Palabra o expresión a buscar en el diccionario.  Puede
                contener espacios o acentos; será limpiada internamente.

        Returns:
            DictionaryEntry: Entrada del diccionario. Si la búsqueda fue exitosa,
                contiene ``definitions`` y opcionalmente ``etymology``.  Si hubo
                un error, ``definitions`` estará vacío y ``error_message`` contendrá
                una descripción legible del problema.
        """
        # Paso 1: Limpiar la entrada (eliminar espacios, caracteres no deseados, etc.)
        clean_word = TextProcessor.clean(word)

        # Paso 2: Validar que la entrada limpia sea apta para enviar al DLE
        if not TextProcessor.is_valid(clean_word):
            return DictionaryEntry(
                word=word,
                error_message="El término '{}' no es válido para buscar.".format(word)
            )

        try:
            # Paso 3: Descargar el HTML de la página de la palabra en el DLE
            html_content = self._fetch_html(clean_word)
            # Paso 4: Parsear el HTML y construir el DictionaryEntry
            entry = self._parse_html(html_content, clean_word)
            return entry

        # --- Manejo granular de errores ---
        # Cada tipo de excepción produce un mensaje de error adaptado al usuario.
        except DLENotFoundError:
            # Caso más común: la palabra simplemente no existe en el DLE
            return DictionaryEntry(
                word=clean_word,
                error_message="La palabra '{}' no se encontró en el Diccionario de la Lengua Española.".format(
                    clean_word
                )
            )
        except DLEConnectionError as e:
            # Problemas de red: sin Internet, timeout, Cloudflare bloquea, etc.
            log.error("Error de conexión al DLE: %s", e)
            return DictionaryEntry(
                word=clean_word,
                error_message="Error de conexión: No se pudo conectar con el servidor del DLE. "
                              "Verifique su conexión a Internet."
            )
        except DLEParsingError as e:
            # El HTML cambió de estructura: la RAE rediseñó la página
            log.error("Error al parsear respuesta del DLE: %s", e)
            return DictionaryEntry(
                word=clean_word,
                error_message="Error al procesar la respuesta del diccionario. "
                              "Es posible que el formato del sitio haya cambiado."
            )
        except Exception as e:
            # Red de seguridad: captura cualquier error imprevisto para que el
            # complemento de NVDA nunca se rompa de forma silenciosa
            log.error("Error inesperado en DLEService.search: %s", e)
            return DictionaryEntry(
                word=clean_word,
                error_message="Error inesperado: {}".format(str(e))
            )

    def _fetch_html(self, word):
        """Realiza la petición HTTP al DLE y devuelve el cuerpo HTML.

        Utiliza ``cloudscraper`` en lugar de ``requests`` o ``urllib`` porque el
        sitio dle.rae.es está protegido por Cloudflare.  ``cloudscraper`` resuelve
        automáticamente los desafíos JavaScript de Cloudflare, lo que permite
        acceder al contenido como si fuera un navegador real.

        Args:
            word (str): Palabra a consultar, ya limpiada y validada por el
                llamador (``search``).

        Returns:
            str: Contenido HTML completo de la página de definición del DLE.

        Raises:
            DLEConnectionError: Si ocurre un error de red, un código HTTP
                inesperado (distinto de 200 y 404), o cualquier excepción
                durante la conexión.
            DLENotFoundError: Si el servidor responde con HTTP 404, lo que
                indica que la palabra no tiene entrada en el diccionario.
        """
        # Construir la URL de consulta: https://dle.rae.es/{palabra}
        url = "{}/{}".format(self.BASE_URL, word)

        try:
            # Realizar la petición GET con cloudscraper (resuelve Cloudflare)
            response = self._scraper.get(url)
            status_code = response.status_code
            content = response.text

            # HTTP 404: la RAE no tiene esa entrada en el diccionario
            if status_code == 404:
                raise DLENotFoundError("Palabra no encontrada: {}".format(word))

            # Cualquier otro código distinto de 200 se trata como error de conexión
            if status_code != 200:
                raise DLEConnectionError(
                    "El servidor respondió con código HTTP {}".format(status_code)
                )

            return content

        except (DLENotFoundError, DLEConnectionError):
            # Re-lanzar excepciones propias sin envolverlas en DLEConnectionError
            raise
        except Exception as e:
            # Envolver cualquier otra excepción (timeout, DNS, SSL, etc.) en
            # DLEConnectionError para que el llamador tenga un tipo uniforme
            raise DLEConnectionError(
                "No se pudo conectar con el DLE: {}".format(str(e))
            )

    def _parse_html(self, html_content, word):
        """Parsea el HTML completo del DLE y construye un ``DictionaryEntry``.

        Este método orquesta la extracción de todas las partes de una entrada del
        diccionario:
            1. Verifica que el HTML no contenga el mensaje de "entrada no encontrada".
            2. Localiza el elemento ``<article>`` raíz.
            3. Delega la extracción de **etimología** a ``_extract_etymology``.
            4. Delega la extracción de **definiciones** a ``_extract_definitions``.
            5. Ensambla y devuelve el ``DictionaryEntry`` final.

        Estructura HTML esperada del DLE::

            <article>
                <div class="n2">Etimología...</div>          ← etimología
                <ol class="c-definitions">                    ← lista de acepciones
                    <li class="j">...</li>                    ← cada definición
                </ol>
            </article>

        Args:
            html_content (str): HTML completo de la página del DLE.
            word (str): Palabra consultada (se usa para mensajes de error y para
                poblar el campo ``word`` del ``DictionaryEntry`` resultante).

        Returns:
            DictionaryEntry: Entrada del diccionario completamente poblada con
                etimología (si existe), y la lista de definiciones con sus
                categorías gramaticales, sinónimos y antónimos.

        Raises:
            DLEParsingError: Si BeautifulSoup no puede interpretar el HTML.
            DLENotFoundError: Si el HTML indica que la palabra no existe o si no
                se encuentra el ``<article>`` esperado ni definiciones válidas.
        """
        try:
            # Parsear el HTML con html.parser (backend de la stdlib, sin dependencias
            # adicionales como lxml).  Es suficiente para el HTML del DLE.
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            raise DLEParsingError("Error al parsear HTML: {}".format(str(e)))

        # Detección heurística: el DLE incluye este texto literal cuando la
        # palabra no existe, incluso si el HTTP status fue 200 (ej: redirecciones)
        if "La entrada no se encuentra en el Diccionario" in html_content:
            raise DLENotFoundError("Palabra no encontrada en el DLE")

        # El contenido de la definición siempre está dentro de un <article>
        article = soup.find("article")
        if not article:
            raise DLENotFoundError("No se encontró el artículo para '{}'".format(word))

        # Extraer la etimología (puede ser cadena vacía si no hay sección etimológica)
        etymology = self._extract_etymology(article)

        # Extraer la lista de definiciones (acepciones)
        definitions = self._extract_definitions(article)

        # Si no se extrajeron definiciones válidas, se considera como "no encontrada"
        if not definitions:
            raise DLENotFoundError("No se encontraron definiciones para '{}'".format(word))

        # Ensamblar el objeto de dominio con todos los datos extraídos
        return DictionaryEntry(
            word=word,
            definitions=definitions,
            etymology=etymology
        )

    def _extract_etymology(self, article):
        """Extrae la sección de etimología del artículo del DLE.

        La etimología aparece en un ``<div>`` con clase ``n2`` (a veces también
        con clase adicional ``c-text-intro``) ubicado al inicio del ``<article>``.
        No todas las palabras tienen etimología, por lo que este método puede
        devolver una cadena vacía.

        Args:
            article (bs4.element.Tag): Elemento ``<article>`` de BeautifulSoup
                que contiene toda la entrada del diccionario.

        Returns:
            str: Texto de la etimología con espacios normalizados, o cadena vacía
                (``""``) si la entrada no incluye información etimológica.
        """
        # Se busca por clase "n2" que abarca tanto <div class="n2"> como
        # <div class="n2 c-text-intro">, ya que la RAE usa ambas variantes
        etymology_tag = article.find("div", class_="n2")
        if etymology_tag:
            # separator=" " evita que textos de nodos hijos se peguen sin espacio
            return etymology_tag.get_text(separator=" ", strip=True)
        return ""

    def _extract_definitions(self, article):
        """Extrae todas las acepciones (definiciones) del artículo HTML del DLE.

        Las definiciones están organizadas dentro de una lista ordenada
        ``<ol class="c-definitions">``.  Cada acepción individual es un
        ``<li class="j">``.  Los ``<li>`` sin clase ``j`` (por ejemplo, los que
        contienen formas complejas o locuciones) se ignoran.

        Para cada ``<li class="j">`` se extraen:
            - **Categoría gramatical** (``_extract_category``): ej. "f.", "tr."
            - **Texto de la definición** (``_extract_definition_content``): texto
              limpio sin números ordinales ni abreviaturas.
            - **Sinónimos** (``_extract_word_list``): lista de sinónimos, si los hay.
            - **Antónimos** (``_extract_word_list``): lista de antónimos, si los hay.

        Args:
            article (bs4.element.Tag): Elemento ``<article>`` de BeautifulSoup
                que contiene toda la entrada del diccionario.

        Returns:
            list[Definition]: Lista ordenada de objetos ``Definition``, una por
                cada acepción encontrada.  Puede estar vacía si no hay ``<ol>``
                de definiciones o si ningún ``<li class="j">`` contiene texto.
        """
        definitions = []

        # Localizar la lista ordenada que agrupa todas las acepciones
        definitions_list = article.find("ol", class_="c-definitions")
        if not definitions_list:
            # Sin <ol class="c-definitions"> no hay definiciones que extraer
            return definitions

        # Solo los <li> con clase "j" son acepciones; los demás pueden ser
        # encabezados de sección, formas complejas, etc.
        # recursive=False asegura buscar solo hijos directos del <ol>
        definition_items = definitions_list.find_all("li", class_="j", recursive=False)
        # Contador manual porque el ordinal HTML (span.n_acep) puede no coincidir
        # con el orden real si hay elementos intercalados sin clase "j"
        definition_number = 0

        for item in definition_items:
            definition_number += 1

            # Extraer la categoría gramatical (ej: "adj.", "m.", "intr.")
            category = self._extract_category(item)

            # Extraer el texto limpio de la definición, eliminando elementos
            # decorativos (número ordinal, abreviaturas, footer de sinónimos)
            content = self._extract_definition_content(item)

            # Extraer sinónimos y antónimos embebidos en la misma acepción
            synonyms = self._extract_word_list(item, "Sin")
            antonyms = self._extract_word_list(item, "Ant")

            # Solo agregar si el contenido no quedó vacío tras la limpieza
            if content:
                definitions.append(Definition(
                    content=content,
                    number=definition_number,
                    category=category,
                    synonyms=synonyms,
                    antonyms=antonyms
                ))

        return definitions

    def _extract_category(self, definition_item):
        """Extrae la categoría gramatical principal de una acepción.

        Dentro de cada ``<li class="j">``, la primera ``<abbr>`` con clase ``d``
        (categoría gramatical directa, ej: "f.", "m.") o clase ``g`` (marca de
        uso gramatical, ej: "tr.", "prnl.") contiene la categoría gramatical
        principal de la definición.

        Se busca la **primera** aparición porque puede haber múltiples ``<abbr>``
        (marcas de uso regional, de estilo, etc.) y solo la primera es la
        categoría gramatical propiamente dicha.

        Args:
            definition_item (bs4.element.Tag): Elemento ``<li class="j">`` que
                representa una acepción individual del DLE.

        Returns:
            str: Texto de la categoría gramatical (ej: ``"interj."``, ``"adj."``),
                o cadena vacía si no se encontró ninguna ``<abbr>`` de categoría.
        """
        # Buscar la primera <abbr> cuya clase sea "d" (definición) o "g" (gramatical)
        first_abbr = definition_item.find("abbr", class_=["d", "g"])
        if first_abbr:
            return first_abbr.get_text(strip=True)
        return ""

    def _extract_definition_content(self, definition_item):
        """Extrae el texto puro de una definición, eliminando elementos decorativos.

        El HTML de cada acepción contiene, además del texto de la definición,
        elementos que no forman parte del contenido semántico:
            - ``<span class="n_acep">``: Número ordinal de la acepción (ej: "1. ").
            - ``<abbr>``: Abreviaturas de categoría gramatical y marcas de uso.
            - ``<div class="c-definitions__item-footer">``: Footer con sinónimos
              y antónimos (se extraen por separado en ``_extract_word_list``).

        **Estrategia de clonación**: Para evitar modificar el árbol DOM original
        (que otros métodos aún necesitan recorrer), se **clona** el nodo
        serializándolo a string y volviéndolo a parsear con BeautifulSoup.  Sobre
        el clon se eliminan (``decompose()``) los elementos no deseados y luego
        se extrae el texto resultante.

        Args:
            definition_item (bs4.element.Tag): Elemento ``<li class="j">`` que
                representa una acepción individual del DLE.

        Returns:
            str: Texto limpio de la definición, con espacios normalizados y sin
                elementos decorativos.  Puede ser cadena vacía si la acepción
                no contenía texto significativo.
        """
        # Preferir el <div role="definition"> si existe, ya que delimita mejor
        # el contenido semántico.  Si no existe, usar el <li> completo.
        def_div = definition_item.find("div", attrs={"role": "definition"})
        source = def_div if def_div else definition_item

        # Clonar el subárbol para no alterar el DOM original — otros métodos
        # (ej: _extract_word_list) todavía necesitan el árbol intacto.
        clone = BeautifulSoup(str(source), "html.parser")

        # Eliminar los <span class="n_acep"> (numeración ordinal, ej: "1. ")
        # para que no se mezcle con el texto de la definición
        for span in clone.find_all("span", class_="n_acep"):
            span.decompose()

        # Eliminar todas las <abbr> (categorías gramaticales y marcas de uso)
        # ya que se extraen por separado en _extract_category
        for abbr in clone.find_all("abbr"):
            abbr.decompose()

        # Eliminar el footer de sinónimos/antónimos para no duplicar su contenido
        # en el texto de la definición (se extraen en _extract_word_list)
        for footer in clone.find_all("div", class_="c-definitions__item-footer"):
            footer.decompose()

        # Obtener el texto limpio; separator=" " inserta un espacio entre nodos
        # adyacentes para evitar que palabras de distintos tags se peguen
        text = clone.get_text(separator=" ", strip=True)

        # Colapsar espacios múltiples que puedan quedar tras la eliminación
        # de elementos internos (ej: "  " entre donde estaba <abbr> y el texto)
        text = re.sub(r"\s{2,}", " ", text)

        return text.strip()

    def _extract_word_list(self, definition_item, list_type):
        """Extrae sinónimos o antónimos asociados a una acepción del DLE.

        Dentro de cada ``<li class="j">`` puede haber un footer
        (``<div class="c-definitions__item-footer">``) que contiene uno o más
        bloques ``<div class="c-word-list">``.  Cada bloque tiene:

        - Una ``<abbr class="sin-header-inline">`` cuyo texto indica el tipo:
            - ``"Sin.:"`` → sinónimos o afines.
            - ``"Ant.:"`` → antónimos u opuestos.
        - Varios ``<span class="sin">`` con las palabras individuales.

        Se filtran los bloques por el prefijo del texto de la ``<abbr>``
        (``list_type``) para devolver solo la lista solicitada.

        Args:
            definition_item (bs4.element.Tag): Elemento ``<li class="j">`` de la
                acepción de la que se quieren extraer sinónimos o antónimos.
            list_type (str): Prefijo del tipo de lista a extraer.  Usar ``"Sin"``
                para sinónimos y ``"Ant"`` para antónimos.  Se compara con el
                texto de la ``<abbr>`` usando ``startswith()``.

        Returns:
            list[str]: Lista de palabras (sinónimos o antónimos) encontradas.
                Devuelve una lista vacía si la acepción no tiene el tipo solicitado
                o si no existe footer de palabras relacionadas.
        """
        words = []

        # Buscar todos los bloques <div class="c-word-list"> dentro de la acepción.
        # Puede haber varios: uno para sinónimos y otro para antónimos.
        word_lists = definition_item.find_all("div", class_="c-word-list")

        for word_list in word_lists:
            # Identificar el tipo de lista por el texto de la <abbr> con clase
            # "sin-header-inline" (ej: "Sin.:" o "Ant.:")
            label_abbr = word_list.find("abbr", class_="sin-header-inline")
            if not label_abbr:
                # Si no hay <abbr> de cabecera, este bloque no es relevante
                continue

            abbr_text = label_abbr.get_text(strip=True)
            # Comparar con startswith para aceptar tanto "Sin.:" como "Sin.:"
            # con posibles variaciones menores en puntuación
            if not abbr_text.startswith(list_type):
                # Este bloque es del otro tipo (ej: es "Ant" cuando pedimos "Sin")
                continue

            # Extraer cada palabra individual de los <span class="sin">
            sin_spans = word_list.find_all("span", class_="sin")
            for span in sin_spans:
                text = span.get_text(strip=True)
                if text:
                    words.append(text)

        return words
