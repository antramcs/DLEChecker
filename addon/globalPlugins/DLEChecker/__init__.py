#DLEChecker for NVDA.
#This file is covered by the GNU General Public License.
#See the file COPYING.txt for more details.
#Copyright (C) 2021 Antonio Cascales <antonio.cascales@gmail.com> and Jose Manuel Delicado <jm.delicado@nvda.es>

import wx
import gui

import globalPluginHandler
import ui
import api
import textInfos
from scriptHandler import script
from urllib import request, parse
from threading import Thread
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
	del sys.modules['html']
except:
	pass

from bs4 import BeautifulSoup

import string

sys.path.remove(os.path.dirname(os.path.abspath(__file__)))

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	@script(gesture="kb:NVDA+shift+c", description= _("Busca la definición de la palabra seleccionada en el Diccionario de la Lengua Española"), category= _("DLEChecker"))
	def script_check_dle_term(self, gesture):
		obj = api.getFocusObject()
		selectedText = ""
		
		if hasattr(obj.treeInterceptor, 'TextInfo') and not obj.treeInterceptor.passThrough:
			try:
				info = obj.treeInterceptor.makeTextInfo(textInfos.POSITION_SELECTION)
			except (RuntimeError, NotImplementedError):
				info = None
			
			if not info or info.isCollapsed:
				self.solicitarDefinicionABuscar()
				return
			else:
				selectedText = info.text.lower()
		else:
			try:
				selectedText = obj.selection.text.lower()
			except (RuntimeError, NotImplementedError):
				self.solicitarDefinicionABuscar()
				return
			
			if obj.selection.text == "":
				self.solicitarDefinicionABuscar()
				return
		
		hilo = Hilo(selectedText)
		hilo.start()
	
	def solicitarDefinicionABuscar(self):
		NuevaConsulta(gui.mainFrame, _("Nueva definición a buscar"), _("Introduce el término a consultar:"))
	
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

		etiqueta = wx.StaticText(panel_dialogo, wx.ID_ANY, label=_("Resultado:"))
		textoResultado = wx.TextCtrl(panel_dialogo, wx.ID_ANY, style = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL) 

		verticalBox.Add(etiqueta, 0, wx.EXPAND)
		verticalBox.Add(textoResultado, 1, wx.EXPAND | wx.ALL)

		self.leerBTN = wx.Button(panel_dialogo, wx.ID_ANY, _("Leer resultado"))
		self.copiarBTN = wx.Button(panel_dialogo, wx.ID_ANY, _("Copiar al portapapeles"))
		self.salirBTN = wx.Button(panel_dialogo, wx.ID_CANCEL, _("&Salir"))

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
		ui.message(_("Copiado al portapapeles"))

	def onSalir(self, event):
		self.Destroy()
		gui.mainFrame.postPopup()

class NuevaConsulta(wx.Dialog):
	def __init__(self, parent, titulo, mensaje):
		super(NuevaConsulta, self).__init__(parent, title=titulo, size=(400, 250))
		
		self.mensaje = mensaje
		
		self.iniciarUI()
	
	def iniciarUI(self):
		panel = wx.Panel(self)
		
		verticalBoxSizer = wx.BoxSizer(wx.VERTICAL)
		horizontalBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
		
		self.etiqueta = wx.StaticText(panel, -1, label=self.mensaje)
		self.cuadroEdicion = wx.TextCtrl(panel, -1, "", style=wx.TE_PROCESS_ENTER)
		self.btnAceptar = wx.Button(panel, wx.ID_OK, _("Consultar"))
		self.btnCancelar = wx.Button(panel, wx.ID_CANCEL, _("Cancelar"))
		
		self.Bind(wx.EVT_TEXT_ENTER, self.onAceptar, self.cuadroEdicion)
		self.Bind(wx.EVT_BUTTON, self.onAceptar, self.btnAceptar)
		self.Bind(wx.EVT_BUTTON, self.onCancelar, self.btnCancelar)
		
		verticalBoxSizer.Add(self.etiqueta, wx.EXPAND)
		verticalBoxSizer.Add(self.cuadroEdicion, wx.EXPAND)
		
		horizontalBoxSizer.Add(self.btnAceptar, 0, wx.CENTRE)
		horizontalBoxSizer.Add(self.btnCancelar, 0, wx.CENTRE)
		
		verticalBoxSizer.Add(horizontalBoxSizer)
		
		self.SetSizer(verticalBoxSizer)
		
		self.Centre()
		self.Show()
	
	def onAceptar(self, e):
		terminoABuscar = self.cuadroEdicion.GetValue().lower()
		if terminoABuscar != "":
			self.Close()
			hilo = Hilo(terminoABuscar)
			hilo.start()
		else:
			gui.messageBox(_("Debes introducir un término a consultar."), caption = _("¡Error!"), style = wx.ICON_ERROR)
			self.cuadroEdicion.SetFocus()
	
	def onCancelar(self, e):
		self.Destroy()

class Hilo(Thread):
	
	def __init__(self, palabra):
		super(Hilo, self).__init__()
		self.daemon = True
		self.palabra = palabra
	
	def run(self):
		
		def mostrarDialogoError(mensaje):
			gui.messageBox(mensaje, caption=_("¡Error!"), parent=None, style=wx.ICON_ERROR)
		
		def mostrarDialogoResultado(mensaje):
			ventanaMSG = DialogoMsg(gui.mainFrame, _("DLEChecker"), mensaje)
			gui.mainFrame.prePopup()
			ventanaMSG.Show()
		
		palabra = self.limpiarTexto(self.palabra)
		argumentos = {"w": palabra}
		argumentos_codificados = parse.urlencode(argumentos)
		url = "https://dle.rae.es/?" + argumentos_codificados
		req = request.Request(url, data=None, headers={"User-Agent": "Mozilla/5.0"})
		
		try:
			html = request.urlopen(req)
		except:
			wx.CallAfter(mostrarDialogoError, _("Error. Es posible que la web esté sufriendo problemas técnicos. Inténtalo más tarde."))
			return
		
		try:
			datos = html.read().decode('utf-8')
			bs = BeautifulSoup(datos, 'html.parser')
			message = _("Definiciones de la palabra {palabra}").format(palabra=palabra) + "\n\n"
			
			articulos = bs.find_all('article')
			
			if len(articulos) > 0:
				for articulo in articulos:
					if articulo.find('table', class_='cnj'):
						continue
					
					message += articulo.header.get_text() + "\n"
					
					for parrafo in articulo.find_all('p'):
						message += parrafo.get_text() + "\n"
					message += "\n"
				
				while message[-1] == '\n':
					message = message.rstrip()
				
				message = self.obtenerSinonimosYAntonimos(palabra, message)
			else:
				gui.messageBox(_("No existen definiciones en el Diccionario de la Lengua Española para la palabra introducida. Revisa la ortografía."), caption = _("¡Error!"), style = wx.ICON_ERROR)
				return
			
			wx.CallAfter(mostrarDialogoResultado, message)
		except:
			wx.CallAfter(mostrarDialogoError, _("Error al intentar obtener la definición de la palabra. Comprueba la ortografía, así como que la palabra existe."))
			return
	
	def obtenerSinonimosYAntonimos(self, palabra, mensaje):
		url = "https://wordreference.com/sinonimos/" + request.quote(palabra)
		req = request.Request(url, data=None, headers={"User-Agent": "Mozilla/5.0"})
		
		try:
			html = request.urlopen(req)
			datos = html.read().decode('utf-8')
			bs = BeautifulSoup(datos, 'html.parser')
			
			div = bs.find('div', class_="trans clickable")
			lista_sinonimos = div.ul
			
			mensaje += "\n\nSinónimos: "
			
			for sinonimo in lista_sinonimos:
				if sinonimo.get_text() == "":
					continue
				
				mensaje += sinonimo.get_text() + "\n"
			
		except:
			mensaje += "\n😕 No existen sinónimos ni antónimos definidos para esta palabra, o quizá la página esté sufriendo problemas técnicos."
		
		return mensaje
	
	def limpiarTexto(self, texto):
		cadenaResultante = ""
		
		for caracter in texto:
			if ( caracter in string.ascii_lowercase + 'áéíóúüñ -' ):
				cadenaResultante += caracter
		
		return cadenaResultante
