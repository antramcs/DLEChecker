# Autor: Antonio Cascales.
# Descripción: Complemento que permite consultar un término en el Diccionario de la Lengua Española.

import globalPluginHandler

import ui
import api
import textInfos

from scriptHandler import script
from urllib import request, parse
from . import BeautifulSoup4

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    @script(gesture="kb:NVDA+shift+c")
    def script_check_dle_term(self, gesture):
        obj = api.getFocusObject()
        treeInterceptor = obj.treeInterceptor
        if hasattr(treeInterceptor, 'TextInfo') and not treeInterceptor.passThrough:
            obj = treeInterceptor
        
        try:
            info = obj.makeTextInfo(textInfos.POSITION_SELECTION)
        except (RuntimeError, NotImplementedError):
            info = Nonne
        
        if not info or info.isCollapsed:
            ui.message("Selecciona un texto primero.")
        else:
            argumentos = {"w": info.text}
            argumentos_codificados = parse.urlencode(argumentos)
            
            url = "https://dle.rae.es/?" + argumentos_codificados
            
            req = request.Request(url, data=None, headers={'User-Agent': 'Mozilla/5.0'})
            
            html = request.urlopen(req)
            
            datos = html.read().decode('utf-8')
            
            bs = BeautifulSoup(datos, 'html.parser')
            parrafos = list(bs.section.article)
            
            ui.message("La definición de " + info.text + " es:")
            
            for i in range(0, len(parrafos)):
                ui.message(parrafos[i])