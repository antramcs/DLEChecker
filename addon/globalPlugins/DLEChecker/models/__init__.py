# -*- coding: utf-8 -*-
# DLEChecker - Paquete de modelos
# Patrón MVC: Capa Model

"""
Paquete de modelos del plugin DLEChecker.

Este paquete constituye la capa Model dentro de la arquitectura MVC del
plugin. Contiene toda la lógica de negocio, las estructuras de datos del
dominio y el acceso a datos externos (web scraping del DLE).

Módulos incluidos:

    - ``dictionary_entry`` (``DictionaryEntry``, ``Definition``):
      Estructuras de datos que representan una entrada del diccionario y
      cada una de sus acepciones. Son objetos inmutables que encapsulan el
      resultado de una consulta: palabra, etimología, definiciones con sus
      categorías gramaticales, sinónimos y antónimos.

    - ``text_processor`` (``TextProcessor``):
      Clase con métodos estáticos para limpiar, normalizar y validar el
      texto introducido por el usuario antes de enviarlo como consulta.
      Maneja normalización Unicode NFC para preservar acentos del español.

    - ``dle_service`` (``DLEService`` y excepciones):
      Servicio que realiza las peticiones HTTP al sitio dle.rae.es usando
      ``cloudscraper`` (para evadir la protección Cloudflare) y parsea el
      HTML de respuesta con ``BeautifulSoup``. Define una jerarquía de
      excepciones para cada tipo de error posible:
        - ``DLEServiceError``: excepción base.
        - ``DLEConnectionError``: fallo de red o HTTP.
        - ``DLEParsingError``: HTML con formato inesperado.
        - ``DLENotFoundError``: la palabra no existe en el DLE.

Ejemplo de importación típica::

    from .models import DLEService, DictionaryEntry, TextProcessor
"""

# Re-exportar las clases públicas de cada módulo para simplificar las
# importaciones desde el paquete padre. Así se puede escribir:
#   from ..models import DLEService
# en lugar de:
#   from ..models.dle_service import DLEService
from .dictionary_entry import DictionaryEntry, Definition
from .text_processor import TextProcessor
from .dle_service import DLEService, DLEServiceError, DLEConnectionError, DLEParsingError, DLENotFoundError

# Definir la interfaz pública del paquete: los nombres que se exportan
# con ``from models import *`` y que las herramientas de análisis estático
# reconocen como la API pública del módulo.
__all__ = [
    "DictionaryEntry",
    "Definition",
    "TextProcessor",
    "DLEService",
    "DLEServiceError",
    "DLEConnectionError",
    "DLEParsingError",
    "DLENotFoundError",
]
