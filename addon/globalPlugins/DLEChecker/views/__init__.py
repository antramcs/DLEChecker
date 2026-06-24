# -*- coding: utf-8 -*-
# DLEChecker - Paquete de vistas
# Patrón MVC: Capa View

"""
Paquete de vistas del plugin DLEChecker.

Este paquete constituye la capa View dentro de la arquitectura MVC del
plugin. Contiene los diálogos de interfaz gráfica basados en ``wx.Dialog``
que permiten la interacción entre el usuario y el lector de pantalla NVDA.

Las vistas NO contienen lógica de negocio. Su responsabilidad se limita a:
    - Recoger la entrada del usuario (``SearchDialog``).
    - Mostrar los resultados de la consulta (``ResultDialog``).
    - Delegar las acciones del usuario al controlador mediante valores
      de retorno modal (``wx.ID_OK``, ``wx.ID_CANCEL``, ``wx.ID_CLOSE``)
      o callbacks inyectados.

Módulos incluidos:

    - ``search_dialog`` (``SearchDialog``):
      Diálogo modal que solicita al usuario una palabra cuando no hay texto
      seleccionado. Incluye campo de texto con soporte para la tecla Enter
      y botones «Consultar» / «Cancelar».

    - ``result_dialog`` (``ResultDialog``):
      Diálogo modal que presenta las definiciones encontradas en un área de
      texto de solo lectura. Ofrece botones para leer con el sintetizador
      de voz (callback del controlador), copiar al portapapeles y cerrar.

Ambos diálogos usan ``gui.mainFrame`` como ventana padre y el estilo
``wx.STAY_ON_TOP`` para garantizar que siempre aparezcan en primer plano,
independientemente de la aplicación que tenga el foco.

Ejemplo de importación típica::

    from .views import SearchDialog, ResultDialog
"""

# Re-exportar las clases de diálogo para simplificar las importaciones
from .search_dialog import SearchDialog
from .result_dialog import ResultDialog

# Interfaz pública del paquete
__all__ = [
    "SearchDialog",
    "ResultDialog",
]
