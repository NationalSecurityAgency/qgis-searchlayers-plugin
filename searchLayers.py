from qgis.PyQt.QtCore import QUrl, QCoreApplication, QTranslator, QSettings
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

import os
import webbrowser

from .searchDialog import LayerSearchDialog

def tr(string):
    return QCoreApplication.translate('@default', string)

class SearchLayers:
    def __init__(self, iface):
        self.iface = iface
        self.searchDialog = None

        # Initialize the plugin path directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        try:
            locale = QSettings().value("locale/userLocale", "en", type=str)[0:2]
        except Exception:
            locale = "en"
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'searchLayers_{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    def initGui(self):
        # Create the menu items in the Plugin menu and attach the icon to the toolbar
        icon = QIcon(os.path.dirname(__file__) + "/icon.png")
        self.searchAction = QAction(icon, tr("Search Layers"), self.iface.mainWindow())
        self.searchAction.setObjectName('searchLayers')
        self.searchAction.triggered.connect(self.showSearchDialog)
        self.iface.addToolBarIcon(self.searchAction)
        self.iface.addPluginToMenu(tr("Search Layers"), self.searchAction)

        # Help
        icon = QIcon(os.path.dirname(__file__) + '/help.png')
        self.helpAction = QAction(icon, tr("Help"), self.iface.mainWindow())
        self.helpAction.setObjectName('searchLayersHelp')
        self.helpAction.triggered.connect(self.help)
        self.iface.addPluginToMenu(tr('Search Layers'), self.helpAction)

    def unload(self):
        self.iface.removePluginMenu(tr('Search Layers'), self.searchAction)
        self.iface.removePluginMenu(tr('Search Layers'), self.helpAction)
        self.iface.removeToolBarIcon(self.searchAction)
    
    def showSearchDialog(self):
        if self.searchDialog is None:
            # All the work is done in the LayerSearchDialog
            self.searchDialog = LayerSearchDialog(self.iface, self.iface.mainWindow())
        self.searchDialog.show()
        
    def help(self):
        '''Display a help page'''
        url = QUrl.fromLocalFile(os.path.dirname(__file__) + "/index.html").toString()
        webbrowser.open(url, new=2)
        
