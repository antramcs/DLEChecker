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
		treeInterceptor = obj.treeInterceptor
		if hasattr(treeInterceptor, 'TextInfo') and not treeInterceptor.passThrough:
			obj = treeInterceptor
			try:
				info = obj.makeTextInfo(textInfos.POSITION_SELECTION)
			except (RuntimeError, NotImplementedError):
				info = Nonne
			if not info or info.isCollapsed:
				ui.message(_("Selecciona un texto primero."))
			else:
				argumentos = {"w": info.text}
				argumentos_codificados = parse.urlencode(argumentos)
				url = "https://dle.rae.es/?" + argumentos_codificados
				req = request.Request(url, data=None, headers={'User-Agent': 'Mozilla/5.0'})
				html = request.urlopen(req)
				datos = html.read().decode('utf-8')
				bs = BeautifulSoup(datos, 'html.parser')
				parrafos = list(bs.section.article)
				message=_("La definición de {arg0} es:").format(arg0=info.text)
				for i in parrafos:
					if hasattr(i, "text"):
						message=message+"\n"+i.text
				ui.browseableMessage(message)
		else:
			ui.message(_("Caso de uso no implementado"))
