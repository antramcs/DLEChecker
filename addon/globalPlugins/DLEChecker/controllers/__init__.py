# -*- coding: utf-8 -*-
# DLEChecker - Paquete de controladores
# Patrón MVC: Capa Controller

"""
Paquete de controladores del plugin DLEChecker.

Este paquete constituye la capa Controller dentro de la arquitectura MVC
del plugin. Su único módulo público, ``controller.py``, expone la clase
``DLEController``, que orquesta toda la comunicación entre las capas
Model (``models/``) y View (``views/``).

Responsabilidades de la capa Controller:
    - Recibir las solicitudes de búsqueda desde el ``GlobalPlugin``.
    - Validar y limpiar el texto de entrada mediante ``TextProcessor``.
    - Delegar las consultas HTTP al ``DLEService`` en hilos secundarios.
    - Presentar los resultados al usuario a través de los diálogos wx.

Módulos exportados:
    - ``DLEController``: controlador principal del plugin.

Ejemplo de importación típica:
    >>> from .controllers import DLEController
    >>> ctrl = DLEController()
"""

# Re-exportar DLEController para simplificar las importaciones
# desde el paquete padre (p.ej. ``from .controllers import DLEController``)
from .controller import DLEController

# Definir la interfaz pública del paquete: solo se expone el controlador
# principal. Esto ayuda a herramientas de análisis estático y a
# ``from controllers import *`` a saber qué nombres están disponibles.
__all__ = [
    "DLEController",
]
