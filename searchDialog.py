import os
import re

from PyQt4 import uic
from PyQt4 import QtCore, QtGui

#from PyQt4.QtCore import *
from qgis.core import *
from qgis.gui import *
from searchWorker import Worker


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'layersearch.ui'))


class LayerSearchDialog(QtGui.QDialog, FORM_CLASS):
    def __init__(self, iface, parent):
        '''Initialize the LayerSearch dialog box'''
        super(LayerSearchDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # Notify us when vector items ared added and removed in QGIS
        iface.legendInterface().itemAdded.connect(self.updateLayers)
        iface.legendInterface().itemRemoved.connect(self.updateLayers)
        
        self.doneButton.clicked.connect(self.closeDialog)
        self.stopButton.clicked.connect(self.killWorker)
        self.searchButton.clicked.connect(self.runSearch)
        self.layerListComboBox.activated.connect(self.layerSelected)
        self.searchInComboBox.addItems(['All Fields', 'Specific Field'])
        self.searchInComboBox.activated.connect(self.layerSelected)
        self.maxResults = 1500
        self.resultsTable.setColumnCount(3)
        self.resultsTable.setSortingEnabled(False)
        self.resultsTable.setHorizontalHeaderLabels(['Value','Layer','Field'])
        self.resultsTable.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.comparisonComboBox.addItems(['=','contains','begins with'])
        self.resultsTable.itemSelectionChanged.connect(self.select_feature)
        self.worker = None

    def closeDialog(self):
        '''Close the dialog box when the Close button is pushed'''
        self.hide()
    
    def updateLayers(self):
        '''Called when a layer has been added or deleted in QGIS.
        It forces the dialog to reload.'''
        # Stop any existing search
        self.killWorker()
        if self.isVisible():
            self.populateLayerListComboBox()
        
    def select_feature(self):
        '''A feature has been selected from the list so we need to select
        and zoom to it'''
        if self.noSelection:
            # We do not want this event while data is being changed
            return
        # Deselect all selections
        layers = self.iface.legendInterface().layers()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                layer.removeSelection()
        # Find the layer that was selected and select the feature in the layer
        selectedRow = self.resultsTable.currentRow()
        selectedLayer = self.results[selectedRow][0]
        selectedFeature = self.results[selectedRow][1]
        selectedLayer.select(selectedFeature.id())
        # Zoom to the selected feature
        self.canvas.zoomToSelected(selectedLayer)
    
    def layerSelected(self):
        '''The user has made a selection so we need to initialize other
        parts of the dialog box'''
        self.initSearchIn()
        
    def showEvent(self, event):
        '''The dialog is being shown. We need to initialize it.'''
        super(LayerSearchDialog, self).showEvent(event)
        self.populateLayerListComboBox()
        
    def populateLayerListComboBox(self):
        '''Find all the vector layers and add them to the layer list
        that the user can select. In addition the user can search on all
        layers or all selected layers.'''
        layerlist = ['<All Layers>','<Selected Layers>']
        self.searchLayers = [None, None] # This is same size as layerlist
        layers = self.iface.legendInterface().layers()
        
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                layerlist.append(layer.name())
                self.searchLayers.append(layer)

        self.layerListComboBox.clear()
        self.layerListComboBox.addItems(layerlist)
        self.initSearchIn()
        
    def initSearchIn(self):
        selectedLayer = self.layerListComboBox.currentIndex()
        if selectedLayer > 1:
            self.searchInComboBox.setEnabled(True)
            self.fieldListComboBox.clear()
            self.fieldListComboBox.setEnabled(True)
            if self.searchInComboBox.currentIndex() == 1:
                for field in self.searchLayers[selectedLayer].pendingFields():
                    self.fieldListComboBox.addItem(field.name())
        else:
            self.searchInComboBox.setCurrentIndex(0)
            self.searchInComboBox.setEnabled(False)
            self.fieldListComboBox.clear()
            self.fieldListComboBox.setEnabled(False)
    
    def runSearch(self):
        '''Called when the user pushes the Search button'''
        selectedLayer = self.layerListComboBox.currentIndex()
        comparisonMode = self.comparisonComboBox.currentIndex()
        self.noSelection = True
        try:
            str = unicode(self.findStringEdit.text()).strip()
        except:
            self.showErrorMessage('Invalid Search String')
            return
            
        if str == '':
            self.showErrorMessage('Search string is empty')
            return
        if selectedLayer == 0:
            # Include all vector layers
            layers = self.iface.legendInterface().layers()
        elif selectedLayer == 1:
            # Include all selected vector layers
            layers = self.iface.legendInterface().selectedLayers()
        else:
            # Only search on the selected vector layer
            layers = [self.searchLayers[selectedLayer]]
        self.vlayers=[]
        # Find the vector layers that are to be searched
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                self.vlayers.append(layer)
        if len(self.vlayers) == 0:
            self.showErrorMessage('There are no vector layers to search through')
            return
        
        # vlayers contains the layers that we will search in
        self.searchButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.doneButton.setEnabled(False)
        self.clearResults()
        self.resultsLabel.setText('')
        infield = self.searchInComboBox.currentIndex() == 1
        if infield is True:
            selectedField = unicode(self.fieldListComboBox.currentText())
        else:
            selectedField = None
        
        # Because this could take a lot of time, set up a separate thread
        # for a worker function to do the searching.
        thread = QtCore.QThread()
        worker = Worker(self.vlayers, infield, str, comparisonMode, selectedField, self.maxResults)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.workerFinished)
        worker.foundmatch.connect(self.addFoundItem)
        worker.error.connect(self.workerError)
        self.thread = thread
        self.worker = worker
        self.noSelection = False
        thread.start()

    def workerFinished(self, status):
        '''Clean up the worker and thread'''
        self.worker.deleteLater()
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.worker = None
        self.resultsLabel.setText('Results: '+str(self.found))

        self.vlayers = []
        self.searchButton.setEnabled(True)
        self.stopButton.setEnabled(False)
        self.doneButton.setEnabled(True)
    
    def workerError(self, exception_string):
        '''An error occurred so display it.'''
        showErrorMessage(exception_string)
    
    def killWorker(self):
        '''This is initiated when the user presses the Stop button
        and will stop the search process'''
        if self.worker is not None:
            self.worker.kill()
        
    def clearResults(self):
        '''Clear all the search results.'''
        self.found = 0
        self.results = []
        self.resultsTable.setRowCount(0)        
    
    def addFoundItem(self, layer, feature, attrname, value):
        '''We found an item so add it to the found list.'''
        self.resultsTable.insertRow(self.found)
        self.results.append([layer, feature])
        self.resultsTable.setItem(self.found, 0, QtGui.QTableWidgetItem(value))
        self.resultsTable.setItem(self.found, 1, QtGui.QTableWidgetItem(layer.name()))
        self.resultsTable.setItem(self.found, 2, QtGui.QTableWidgetItem(attrname))
        self.found += 1        
            
    def showErrorMessage(self, message):
        '''Display an error message.'''
        self.iface.messageBar().pushMessage("", message, level=QgsMessageBar.WARNING, duration=2)
