from multiprocessing.sharedctypes import Value
import os
import re
import time
import datetime

from qgis.PyQt.uic import loadUiType
from qgis.PyQt.QtWidgets import QDialog, QAbstractItemView, QTableWidget, QTableWidgetItem
from qgis.PyQt.QtCore import Qt, QThread, QEvent, QCoreApplication

from qgis.core import QgsVectorLayer, Qgis, QgsProject, QgsWkbTypes, QgsMapLayer, QgsFields, QgsExpressionContextUtils
from .searchWorker import Worker
from .fuzzyWorker import FuzzyWorker

def tr(string):
    return QCoreApplication.translate('@default', string)


FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), 'searchlayers.ui'))


class LayerSearchDialog(QDialog, FORM_CLASS):
    button_pressed = 1
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
        self.results2LayersButton.clicked.connect(self.exportResults)
        self.layerListComboBox.activated.connect(self.layerSelected)
        self.searchFieldComboBox.addItems([tr('<All Fields>')])
        self.maxResults = 2000
        self.resultsTable.setEditTriggers(QTableWidget.NoEditTriggers)
        self.resultsTable.setColumnCount(4)
        self.resultsTable.setSortingEnabled(True)
        self.resultsTable.setHorizontalHeaderLabels([tr('Layer'),tr('Feature ID'),tr('Field'),tr('Search Results')])
        self.resultsTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.resultsTable.itemSelectionChanged.connect(self.select_feature)
        # self.resultsTable.viewport().installEventFilter(self)
        self.results = []
        self.ignore_clear = False
        self.worker = None
        self.time_start = 0
        self.last_search_str = ''
        self.last_search_str2 = ''
        self.layers_need_updating = True

    def closeDialog(self):
        '''Close the dialog box when the Close button is pushed'''
        self.hide()

    def eventFilter(self, source, e):
        if e.type() == QEvent.MouseButtonPress:
            self.button_pressed = e.button()
        return super().eventFilter(source, e)

    def updateLayers(self):
        '''Called when a layer has been added or deleted in QGIS.
        It forces the dialog to reload.'''
        # Stop any existing search
        self.killWorker()
        if self.isVisible() or len(self.results) != 0:
            self.populateLayerListComboBox()
            self.clearResults()
            self.layers_need_updating = False
        else:
            self.layers_need_updating = True

    def select_feature(self):
        '''A feature has been selected from the list so we need to select
        and zoom to it'''
        if self.noSelection:
            # We do not want this event while data is being changed
            return
        zoom_pan = self.zoomPanComboBox.currentIndex()
        if self.searchSelectedCheckBox.isChecked():
            if zoom_pan == 0:
                return
            # We are searching on selected features so we don't want to select them from the list.
            selectedItems = self.resultsTable.selectedItems()
            if len(selectedItems) == 0:
                return
            selectedRow = selectedItems[0].row()
            foundid = self.resultsTable.item(selectedRow, 0).data(Qt.UserRole)
            selectedLayer = self.results[foundid][0]
            selectedFeature = self.results[foundid][1]
            fid = selectedFeature.id()
            if zoom_pan == 1:
                self.canvas.zoomToFeatureIds(selectedLayer, [fid])
            else:
                self.canvas.panToFeatureIds(selectedLayer, [fid])
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
        if self.layers_need_updating:
            self.populateLayerListComboBox()

    def populateLayerListComboBox(self):
        '''Find all the vector layers and add them to the layer list
        that the user can select. In addition the user can search on all
        layers or all selected layers.'''
        layerlist = [tr('<All Layers>'),tr('<Selected Layers>'),tr('<Visible Layers>')]
        self.searchLayers = [None, None, None] # This is same size as layerlist
        layers = QgsProject.instance().mapLayers().values()

        '''If the project variable "searchlayers-plugin" is present, only the specified layer is covered.
        Multiple layers are separated by ",".'''
        ProjectInstance = QgsProject.instance()
        if QgsExpressionContextUtils.projectScope(ProjectInstance).variable('searchlayers-plugin'):
            ProjectVariable = QgsExpressionContextUtils.projectScope(ProjectInstance).variable('searchlayers-plugin').split(',')
            for i,j in enumerate(ProjectVariable):
                for layer in layers:
                    if layer.type() == QgsMapLayer.VectorLayer and not layer.sourceName().startswith('__'):
                        if layer.name() == j:
                            layerlist.append(layer.name())
                            self.searchLayers.append(layer)    
        else:
            for layer in layers:
                if layer.type() == QgsMapLayer.VectorLayer and not layer.sourceName().startswith('__'):
                    layerlist.append(layer.name())
                    self.searchLayers.append(layer)

        self.layerListComboBox.clear()
        self.layerListComboBox.addItems(layerlist)
        self.initFieldList()
        self.layers_need_updating = False

    def initFieldList(self):
        selectedLayer = self.layerListComboBox.currentIndex()
        self.searchFieldComboBox.clear()
        self.searchFieldComboBox.addItem('<All Fields>')
        if selectedLayer > 2:
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
            self.resultsTable.setHorizontalHeaderLabels([tr('Layer'),tr('Feature ID'),tr('Field'),tr('Results')])
        else:
            self.resultsTable.setColumnCount(6)
            self.resultsTable.setHorizontalHeaderLabels([tr('Layer'),tr('Feature ID'),tr('Field 1'),tr('Results 1'),tr('Field 2'),tr('Results 2')])

    def setButtons(self, searching):
        if searching:
            self.searchButton.setEnabled(False)
            self.stopButton.setEnabled(True)
            self.doneButton.setEnabled(False)
            self.clearButton.setEnabled(False)
            self.results2LayersButton.setEnabled(False)
        else:
            self.searchButton.setEnabled(True)
            self.clearButton.setEnabled(True)
            self.stopButton.setEnabled(False)
            self.doneButton.setEnabled(True)
            if len(self.results):
                self.results2LayersButton.setEnabled(True)
            else:
                self.results2LayersButton.setEnabled(False)

    def runSearch(self):
        '''Called when the user pushes the Search button'''
        # Set up general parametrs for all search methods
        selected_tab = self.tabWidget.currentIndex()
        self.noSelection = True
        selectedLayer = self.layerListComboBox.currentIndex()
        self.first_match_only = self.firstMatchCheckBox.isChecked()
        self.search_selected = self.searchSelectedCheckBox.isChecked()
        constrain_to_canvas = self.cannvasConstraintCheckBox.isChecked()

        if selectedLayer == 0:
            # Include all vector layers
            layers = QgsProject.instance().mapLayers().values()
        elif selectedLayer == 1:
            # Include all selected vector layers
            layers = self.iface.layerTreeView().selectedLayers()
        elif selectedLayer == 2:
            # This is for visiable layers and content
            layer_trees = QgsProject.instance().layerTreeRoot().findLayers()
            layers = []
            for lt in layer_trees:
                if lt.isVisible():
                    layers.append(lt.layer())
        else:
            # Only search on the selected vector layer
            layers = [self.searchLayers[selectedLayer]]
        self.vlayers=[]
        # Find the vector layers that are to be searched
        for layer in layers:
            if isinstance(layer, QgsVectorLayer) and not layer.sourceName().startswith('__'):
                self.vlayers.append(layer)
        if len(self.vlayers) == 0:
            self.showErrorMessage('There are no vector layers to search')
            return

        # vlayers contains the layers that we will search in
        self.setButtons(True)
        self.resultsLabel.setText('')
        infield = self.searchFieldComboBox.currentIndex() >= 1
        if infield is True:
            selectedField = self.searchFieldComboBox.currentText()
        else:
            selectedField = None

        # Because this could take a lot of time, set up a separate thread
        # for a worker function to do the searching.
        self.time_start = time.perf_counter()
        thread = QThread()
        if selected_tab == 0:
            # Get parameters for regular search
            comparisonMode = self.comparisonComboBox.currentIndex()
            comparisonMode2 = self.comparison2ComboBox.currentIndex()
            and_or = self.andOrComboBox.currentIndex()
            case_sensitive = self.caseSensitiveCheckBox.isChecked()
            case_sensitive2 = self.caseSensitive2CheckBox.isChecked()
            self.two_string_match_single = self.twoStringMatchCheckBox.isChecked()
            not_search = self.notCheckBox.isChecked()
            not_search2 = self.not2CheckBox.isChecked()

            try:
                sstr = self.findStringEdit.text()
                self.last_search_str = sstr
                sstr2 = self.findString2Edit.text()
                self.last_search_str2 = sstr2
            except:
                self.showErrorMessage(tr('Invalid Search String'))
                self.setButtons(False)
                return

            if sstr == '':
                self.showErrorMessage(tr('Search string is empty'))
                self.setButtons(False)
                return
            if sstr2 == '':
                self.is_single_string = True
            else:
                self.is_single_string = False
            self.initSearchResultsTable()
            worker = Worker(self.canvas, self.vlayers, infield, sstr, comparisonMode, case_sensitive, not_search, 
                and_or, sstr2, comparisonMode2, case_sensitive2, not_search2,
                selectedField, self.maxResults, self.first_match_only, self.two_string_match_single,
                self.search_selected, constrain_to_canvas)
        else:
            # Get Fuzzy parameters
            if self.levenshteinButton.isChecked():
                algorithm = 0
            else:
                algorithm = 1
            sstr = self.fuzzyTextEdit.toPlainText()
            case_sensitive = self.fuzzyCaseSensitiveCheckBox.isChecked()
            fuzzy_contains = self.fuzzyContainsCheckBox.isChecked()
            match_metric = self.levenshteinMatchSpinBox.value() / 100.0
            self.is_single_string = True
            self.initSearchResultsTable()
            worker = FuzzyWorker(self.canvas, self.vlayers, infield, sstr, algorithm, case_sensitive,
                fuzzy_contains, selectedField, self.maxResults, self.first_match_only,
                self.search_selected, match_metric, constrain_to_canvas)
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
        total_time = time.perf_counter() - self.time_start
        self.resultsLabel.setText(tr('Results')+': {} in {:.1f}s'.format(self.found, total_time))

        self.vlayers = []
        self.setButtons(False)

    def workerError(self, exception_string):
        '''An error occurred so display it.'''
        # self.showErrorMessage(exception_string)
        print(exception_string)

    def killWorker(self):
        '''This is initiated when the user presses the Stop button
        and will stop the search process'''
        if self.worker is not None:
            self.worker.kill()

    def clearResults(self):
        '''Clear all the search results.'''
        if self.ignore_clear:
            return
        self.noSelection = True
        self.found = 0
        self.results = []
        self.layer_set = set()
        self.resultsTable.setRowCount(0)        
        self.noSelection = False
        self.results2LayersButton.setEnabled(False)

    def addFoundItem(self, layer, feature, attrname1, results1, attrname2, results2):
        '''We found an item so add it to the found list.'''
        # Don't allow sorting while adding new results
        self.resultsTable.setSortingEnabled(False)
        self.resultsTable.insertRow(self.found)
        self.results.append([layer, feature])
        self.layer_set.add(layer)
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

    def exportResults(self):
        # No found results, no export
        if len(self.results) == 0:
            return
        self.resultsTable.setDisabled(True)
        self.ignore_clear = True
        layer_map = self.createExportedLayers()
        for layer, feature in self.results:
            # print('{} {}'.format(layer, feature))
            layer_map[layer].dataProvider().addFeatures([feature])

        dt = datetime.datetime.now()
        dt_name = dt.strftime('%Y-%m-%d %H:%M:%S')
        if len(self.last_search_str) > 20:
            sname = self.last_search_str[0:17]+'...'
        else:
            sname = self.last_search_str
        if len(self.last_search_str2) > 20:
            sname2 = self.last_search_str2[0:17]+'...'
        else:
            sname2 = self.last_search_str2
        if sname2.strip() == '':
            fname = '{}_{}'.format(dt_name, sname)
        else:
            fname = '{}_{}_{}'.format(dt_name, sname, sname2)
        self.ignore_clear = True
        layer_tree = QgsProject.instance().layerTreeRoot()
        group = layer_tree.insertGroup(0, fname)
        for layer in layer_map:
            new_layer = layer_map[layer]
            new_layer.updateExtents()
            QgsProject.instance().addMapLayer(new_layer, False)
            group.addLayer(new_layer)
        self.ignore_clear = False
        self.resultsTable.setDisabled(False)

    def createExportedLayers(self):
        layer_mapping = {}
        for layer in self.layer_set:
            new_name = '__'+layer.name()
            wkb_type = layer.wkbType()
            layer_crs = layer.sourceCrs()
            fields = QgsFields(layer.fields())
            new_layer = QgsVectorLayer("{}?crs={}".format(QgsWkbTypes.displayString(wkb_type), layer_crs.authid()), new_name, "memory")
            dp = new_layer.dataProvider()
            dp.addAttributes(fields)
            new_layer.updateFields()
            layer_mapping[layer] = new_layer
        return(layer_mapping)

    def showErrorMessage(self, message):
        '''Display an error message.'''
        self.iface.messageBar().pushMessage("", message, level=Qgis.Warning, duration=2)
