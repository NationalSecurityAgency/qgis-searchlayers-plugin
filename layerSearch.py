from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from qgis.gui import *

# Initialize Qt resources from file resources.py
import resources

import os.path
from searchDialog import LayerSearchDialog

class LayerSearch:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        # All the work is done in the LayerSearchDialog
        self.searchDialog = LayerSearchDialog(self.iface, self.iface.mainWindow())
        # Create the menu items in the Plugin menu and attach the icon to the toolbar
        icon = QIcon(":/plugins/layersearch/icon.png")
        self.searchAction = QAction(icon, "Search Layer(s)", self.iface.mainWindow())
        self.searchAction.triggered.connect(self.showSearchDialog)
        self.searchAction.setCheckable(False)
        self.iface.addToolBarIcon(self.searchAction)
        self.iface.addPluginToMenu("Search", self.searchAction)

    def unload(self):
        self.iface.removePluginMenu('Search', self.searchAction)
        self.iface.removeToolBarIcon(self.searchAction)
    
    def showSearchDialog(self):
        self.searchDialog.show()
        
        
