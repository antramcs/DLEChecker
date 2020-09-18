#DLEChecker for NVDA.
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.
#Copyright (C) 2020 Antonio Cascales <antonio.cascales@gmail.com> and Jose Manuel Delicado <jm.delicado@nvda.es>

import wx
import gui

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
			selectedText = obj.selection.text.lower()
			
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
			
#			ui.browseableMessage(message)
			self.ventanaMSG = DialogoMsg(gui.mainFrame, "DLEChecker", message)
			gui.mainFrame.prePopup()
			self.ventanaMSG.Show()
		except:
			ui.message(_("Error al intentar obtener la definición de la palabra."))

class DialogoMsg(wx.Dialog):
# Function taken from the add-on emoticons to center the window
	def _calculatePosition(self, width, height):
		w = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_X)
		h = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)
		# Centre of the screen
		x = w / 2
		y = h / 2
		# Minus application offset
		x -= (width / 2)
		y -= (height / 2)
		return (x, y)

	def __init__(self, parent, titulo, mensaje):
		WIDTH = 800
		HEIGHT = 600
		pos = self._calculatePosition(WIDTH, HEIGHT)

		super(DialogoMsg, self).__init__(parent, -1, title=titulo, pos = pos, size = (WIDTH, HEIGHT))

		self.mensaje = mensaje

		panel_dialogo = wx.Panel(self)

		principalBox = wx.BoxSizer(wx.VERTICAL)
		verticalBox = wx.BoxSizer(wx.VERTICAL)
		horizontalBox = wx.BoxSizer(wx.HORIZONTAL)

		etiqueta = wx.StaticText(panel_dialogo, wx.ID_ANY, label="Resultado:")
		textoResultado = wx.TextCtrl(panel_dialogo, wx.ID_ANY, style = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL) 

		verticalBox.Add(etiqueta, 0, wx.EXPAND)
		verticalBox.Add(textoResultado, 1, wx.EXPAND | wx.ALL)

		self.leerBTN = wx.Button(panel_dialogo, wx.ID_ANY, "Leer resultado")
		self.copiarBTN = wx.Button(panel_dialogo, wx.ID_ANY, "Copiar al portapapeles")
		self.salirBTN = wx.Button(panel_dialogo, wx.ID_CANCEL, "&Salir")

		horizontalBox.Add(self.leerBTN, 0, wx.CENTER)
		horizontalBox.Add(self.copiarBTN, 0, wx.CENTER)
		horizontalBox.Add(self.salirBTN, 0, wx.CENTER)

		principalBox.Add(verticalBox, 1, wx.EXPAND | wx.ALL)
		principalBox.Add(horizontalBox, 0, wx.CENTER)

		panel_dialogo.SetSizer(principalBox)

		self.Bind(wx.EVT_BUTTON, self.onLeer, self.leerBTN)
		self.Bind(wx.EVT_BUTTON, self.onCopiar, self.copiarBTN)
		self.Bind(wx.EVT_BUTTON, self.onSalir, id=wx.ID_CANCEL)

		textoResultado.WriteText(self.mensaje)
		textoResultado.SetInsertionPoint(0) 

	def onLeer(self, event):
		ui.message(self.mensaje)

	def onCopiar(self, event):
		api.copyToClip(self.mensaje)
		ui.message("Copiado al portapapeles")

	def onSalir(self, event):
		self.Destroy()
		gui.mainFrame.postPopup()
