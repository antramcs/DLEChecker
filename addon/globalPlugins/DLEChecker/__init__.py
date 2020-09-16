#DLEChecker for NVDA.
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.
#Copyright (C) 2020 Antonio Cascales <antonio.cascales@gmail.com> and Jose Manuel Delicado <jm.delicado@nvda.es>

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
	@script(gesture="kb:NVDA+shift+c", description= _("Busca la definición de la palabra seleccionada en el Diccionario de la Lengua Española"), category= _("DLEChecker"))
	def script_check_dle_term(self, gesture):
		obj = api.getFocusObject()
		selectedText = ""
		
		if hasattr(obj.treeInterceptor, 'TextInfo') and not obj.treeInterceptor.passThrough:
			try:
				info = obj.treeInterceptor.makeTextInfo(textInfos.POSITION_SELECTION)
			except:
				info = None
			
			if not info or info.isCollapsed:
				ui.message(_("Selecciona un texto primero."))
				return
			else:
				selectedText = info.text.lower()
		else:
			selectedText = obj.selection.text
			
			if obj.selection.text == "":
				ui.message(_("Selecciona un texto primero."))
				return
		
		argumentos = {"w": selectedText.split(" ")[0]}
		argumentos_codificados = parse.urlencode(argumentos)
		url = "https://dle.rae.es/?" + argumentos_codificados
		req = request.Request(url, data=None, headers={"User-Agent": "Mozilla/5.0"})
		
		try:
			html = request.urlopen(req)
			datos = html.read().decode('utf-8')
			bs = BeautifulSoup(datos, 'html.parser')
			parrafos = list(bs.section.article)
			message = ""
			
			for i in parrafos:
				if hasattr(i, 'text'):
					message = _(message + i.text + "\n")
			
			ui.browseableMessage(message)
		except:
			ui.message(_("Error al intentar obtener la definición de la palabra."))
