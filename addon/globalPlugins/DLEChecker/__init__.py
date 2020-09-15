# Autor: Antonio Cascales.
# Descripción: Complemento que permite consultar un término en el Diccionario de la Lengua Española.

import globalPluginHandler
import ui
import api
import textInfos
from scriptHandler import script
from urllib import request, parse
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bs4 import BeautifulSoup
import addonHandler
addonHandler.initTranslation()
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	@script(gesture="kb:NVDA+shift+c")
	def script_check_dle_term(self, gesture):
		obj = api.getFocusObject()
		selectedText = ""
		
		if hasattr(obj.treeInterceptor, 'TextInfo') and not obj.treeInterceptor.passThrough:
			try:
				info = obj.treeInterceptor.makeTextInfo(textInfos.POSITION_SELECTION)
				if not info or info.isCollapsed:
					ui.message(_("Selecciona un texto primero."))
				else:
					selectedText = info.text.lower()
			except (RuntimeError, NotImplementedError):
				ui.message(_("Error en tiempo de ejecución."))
		else:
			selectedText = obj.selection.text
			
			argumentos = {"w": selectedText}
			argumentos_codificados = parse.urlencode(argumentos)
			url = "https://dle.rae.es/?" + argumentos_codificados
			req = request.Request(url, data=None, headers={"User-Agent": "Mozilla/5.0"})
			html = request.urlopen(req)
			datos = html.read().decode('utf-8')
			bs = BeautifulSoup(datos, 'html.parser')
			parrafos = list(bs.section.article)
			message = _("")
			
			for i in parrafos:
				if hasattr(i, 'text'):
					message = message + i.text + "\n"
			
			ui.browseableMessage(message)
