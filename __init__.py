# Autor: Antonio Cascales.
# Descripción: Complemento que permite consultar un término en el Diccionario de la Lengua Española.

import globalPluginHandler

import ui

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    @script(gesture="kb:NVDA+c")
    def script_check_dle_term(self, gesture):
        ui.message("Funciono.")