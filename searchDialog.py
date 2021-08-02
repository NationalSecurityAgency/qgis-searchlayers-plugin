import os
import re

from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDialog, QAbstractItemView, QTableWidget, QTableWidgetItem
from qgis.PyQt.QtCore import Qt, QThread

from qgis.core import QgsVectorLayer, Qgis, QgsProject, QgsMapLayer
from .searchWorker import Worker


FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), 'searchlayers.ui'))


class LayerSearchDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, parent):
        '''Initialize the LayerSearch dialog box'''
        super(LayerSearchDialog, self).__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        # Notify us when vector items ared added and removed in QGIS
        QgsProject.instance().layersAdded.connect(self.updateLayers)
        QgsProject.instance().layersRemoved.connect(self.updateLayers)

        self.doneButton.clicked.connect(self.closeDialog)
        self.stopButton.clicked.connect(self.killWorker)
        self.searchButton.clicked.connect(self.runSearch)
        self.clearButton.clicked.connect(self.clearResults)
        self.layerListComboBox.activated.connect(self.layerSelected)
        self.searchFieldComboBox.addItems(['<All Fields>'])
        self.maxResults = 1500
        self.resultsTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.resultsTable.setColumnCount(4)
        self.resultsTable.setSortingEnabled(True)
        self.resultsTable.setHorizontalHeaderLabels(['Layer','Feature ID','Field','Search Results'])
        self.resultsTable.setSelectionBehavior(QAbstractItemView.SelectRows)
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
            self.clearResults()

    def select_feature(self):
        '''A feature has been selected from the list so we need to select
        and zoom to it'''
        if self.noSelection:
            # We do not want this event while data is being changed
            return
        # Deselect all selections
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer:
                layer.removeSelection()
        # Find the layers that are selected and select the features in the layer
        selectedItems = self.resultsTable.selectedItems()
        selectedLayer = None
        for item in selectedItems:
            selectedRow = item.row()
            foundid = self.resultsTable.item(selectedRow, 0).data(Qt.UserRole)
            selectedLayer = self.results[foundid][0]
            selectedFeature = self.results[foundid][1]
            selectedLayer.select(selectedFeature.id())
        # Zoom to the selected feature
        zoom_pan = self.zoomPanComboBox.currentIndex()
        if selectedLayer and zoom_pan:
            if zoom_pan == 1:
                self.canvas.zoomToSelected(selectedLayer)
            else:
                self.canvas.panToSelected(selectedLayer)

    def layerSelected(self):
        '''The user has made a selection so we need to initialize other
        parts of the dialog box'''
        self.initFieldList()

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
        layers = QgsProject.instance().mapLayers().values()

        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer:
                layerlist.append(layer.name())
                self.searchLayers.append(layer)

        self.layerListComboBox.clear()
        self.layerListComboBox.addItems(layerlist)
        self.initFieldList()

    def initFieldList(self):
        selectedLayer = self.layerListComboBox.currentIndex()
        self.searchFieldComboBox.clear()
        self.searchFieldComboBox.addItem('<All Fields>')
        if selectedLayer > 1:
            self.searchFieldComboBox.setEnabled(True)
            for field in self.searchLayers[selectedLayer].fields():
                self.searchFieldComboBox.addItem(field.name())
        else:
            self.searchFieldComboBox.setCurrentIndex(0)
            self.searchFieldComboBox.setEnabled(False)

    def initSearchResultsTable(self):
        self.clearResults()
        if self.is_single_string or self.two_string_match_single:
            self.resultsTable.setColumnCount(4)
            self.resultsTable.setHorizontalHeaderLabels(['Layer','Feature ID','Field','Results'])
        else:
            self.resultsTable.setColumnCount(6)
            self.resultsTable.setHorizontalHeaderLabels(['Layer','Feature ID','Field 1','Results 1','Field 2','Results 2'])

    def runSearch(self):
        '''Called when the user pushes the Search button'''
        selectedLayer = self.layerListComboBox.currentIndex()
        comparisonMode = self.comparisonComboBox.currentIndex()
        comparisonMode2 = self.comparison2ComboBox.currentIndex()
        and_or = self.andOrComboBox.currentIndex()
        case_sensitive = self.caseSensitiveCheckBox.isChecked()
        case_sensitive2 = self.caseSensitive2CheckBox.isChecked()
        self.two_string_match_single = self.twoStringMatchCheckBox.isChecked()
        self.first_match_only = self.firstMatchCheckBox.isChecked()
        self.noSelection = True
        try:
            sstr = self.findStringEdit.text()
            sstr2 = self.findString2Edit.text()
        except:
            self.showErrorMessage('Invalid Search String')
            return
            
        if sstr == '':
            self.showErrorMessage('Search string is empty')
            return
        if sstr2 == '':
            self.is_single_string = True
        else:
            self.is_single_string = False
        if selectedLayer == 0:
            # Include all vector layers
            layers = QgsProject.instance().mapLayers().values()
        elif selectedLayer == 1:
            # Include all selected vector layers
            layers = self.iface.layerTreeView().selectedLayers()
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
        self.initSearchResultsTable()
        self.searchButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.doneButton.setEnabled(False)
        self.clearButton.setEnabled(False)
        self.resultsLabel.setText('')
        infield = self.searchFieldComboBox.currentIndex() >= 1
        if infield is True:
            selectedField = self.searchFieldComboBox.currentText()
        else:
            selectedField = None
        not_search = self.notCheckBox.isChecked()
        not_search2 = self.not2CheckBox.isChecked()
        
        # Because this could take a lot of time, set up a separate thread
        # for a worker function to do the searching.
        thread = QThread()
        worker = Worker(self.vlayers, infield, sstr, comparisonMode, case_sensitive, not_search, 
            and_or, sstr2, comparisonMode2, case_sensitive2, not_search2,
            selectedField, self.maxResults, self.first_match_only, self.two_string_match_single)
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
        self.clearButton.setEnabled(True)
        self.stopButton.setEnabled(False)
        self.doneButton.setEnabled(True)
    
    def workerError(self, exception_string):
        '''An error occurred so display it.'''
        #self.showErrorMessage(exception_string)
        print(exception_string)
    
    def killWorker(self):
        '''This is initiated when the user presses the Stop button
        and will stop the search process'''
        if self.worker is not None:
            self.worker.kill()
        
    def clearResults(self):
        '''Clear all the search results.'''
        self.noSelection = True
        self.found = 0
        self.results = []
        self.resultsTable.setRowCount(0)        
        self.noSelection = False
    
    def addFoundItem(self, layer, feature, attrname1, results1, attrname2, results2):
        '''We found an item so add it to the found list.'''
        # Don't allow sorting while adding new results
        self.resultsTable.setSortingEnabled(False)
        self.resultsTable.insertRow(self.found)
        self.results.append([layer, feature])
        # Save the search found position in the first element of the table. This way
        # we can allow the user to sort the table, but be able to know which entry it is.
        item = QTableWidgetItem(layer.name())
        item.setData(Qt.UserRole, self.found)
        self.resultsTable.setItem(self.found, 0, item)
        self.resultsTable.setItem(self.found, 1, QTableWidgetItem(str(feature.id())))
        if self.is_single_string or self.two_string_match_single:
            self.resultsTable.setItem(self.found, 2, QTableWidgetItem(attrname1))
            self.resultsTable.setItem(self.found, 3, QTableWidgetItem(results1))
        else:
            self.resultsTable.setItem(self.found, 2, QTableWidgetItem(attrname1))
            self.resultsTable.setItem(self.found, 3, QTableWidgetItem(results1))
            self.resultsTable.setItem(self.found, 4, QTableWidgetItem(attrname2))
            self.resultsTable.setItem(self.found, 5, QTableWidgetItem(results2))
        self.found += 1   
        # Restore sorting
        self.resultsTable.setSortingEnabled(True)
            
    def showErrorMessage(self, message):
        '''Display an error message.'''
        self.iface.messageBar().pushMessage("", message, level=Qgis.Warning, duration=2)
