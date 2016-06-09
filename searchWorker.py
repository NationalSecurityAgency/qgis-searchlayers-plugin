import os
import re

from PyQt4 import uic
from PyQt4 import QtCore, QtGui

from qgis.core import *
from qgis.gui import *

class Worker(QtCore.QObject):
    '''This does all the hard work. It takes all the search parameters and 
    searches through the vector layers for a match.'''
    finished = QtCore.pyqtSignal(bool)
    error = QtCore.pyqtSignal(str)
    foundmatch = QtCore.pyqtSignal(QgsVectorLayer, object, object, unicode)
    
    def __init__(self, vlayers, infield, str, comparisonMode, selectedField, maxResults):
        QtCore.QObject.__init__(self)
        self.vlayers = vlayers
        self.infield = infield
        self.str = str
        self.comparisonMode = comparisonMode
        self.selectedField = selectedField
        self.killed = False
        self.maxResults = maxResults
        
    def run(self):
        '''Worker Run routine'''
        self.found = 0
        try:
            # Check to see if we are searching within a particular column of a specified
            # layer or whether we are searching all columns.
            if self.infield is True:
                for layer in self.vlayers:
                    self.searchFieldInLayer(layer, self.str, self.comparisonMode, self.selectedField)
            else:
                for layer in self.vlayers:
                    self.searchLayer(layer, self.str, self.comparisonMode)
        except:
            import traceback
            self.error.emit(traceback.format_exc())
        self.finished.emit(True)
            
    def kill(self):
        '''Set a flag that we want to stop looking for matches.'''
        self.killed = True
        
    def searchLayer(self, layer, str, comparisonMode):
        '''Do a string search across all columns in a table'''
        if self.killed:
            return
        fnames = []
        # Get and Keep a copy of the field names
        for field in layer.pendingFields():
            fnames.append(field.name())
        # Get an iterator for all the features in the vector
        iter = layer.getFeatures(QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry))
        if comparisonMode == 0: # Searching for an exact match
            for feature in iter:
                # Check to see if it has been aborted
                if self.killed is True:
                    return
                # Get all the feature attributes or columns
                attrs = feature.attributes()
                # For now just search as if it were a string
                for id, f in enumerate(attrs):
                    if unicode(f) == str:
                        self.foundmatch.emit(layer, feature, fnames[id], unicode(f))
                        self.found += 1
                        if self.found >= self.maxResults:
                            self.killed=True
                            return
        elif comparisonMode == 1: # contains string
            p = re.compile(str, re.I)
            for feature in iter:
                # Check to see if it has been aborted
                if self.killed is True:
                    return
                attrs = feature.attributes()
                # For now just search as if it were a string
                for id, f in enumerate(attrs):
                    if p.search(unicode(f)):
                        self.foundmatch.emit(layer, feature, fnames[id], unicode(f))
                        self.found += 1
                        if self.found >= self.maxResults:
                            self.killed=True
                            return
        else: # begins with string
            p = re.compile(str, re.I)
            for feature in iter:
                # Check to see if it has been aborted
                if self.killed is True:
                    return
                attrs = feature.attributes()
                # For now just search as if it were a string
                for id, f in enumerate(attrs):
                    if p.match(unicode(f)):
                        self.foundmatch.emit(layer, feature, fnames[id], unicode(f))
                        self.found += 1
                        if self.found >= self.maxResults:
                            self.killed=True
                            return

    def searchFieldInLayer(self, layer, str, comparisonMode, selectedField):
        '''Do a string search on a specific column in the table.'''
        if self.killed:
            return

        request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([selectedField], layer.fields())
        if comparisonMode == 0: # Searching for an exact match
            request.setFilterExpression('"{}" LIKE \'{}\''.format(selectedField,str))
        elif comparisonMode == 1: # contains string
            request.setFilterExpression('"{}" ILIKE \'%{}%\''.format(selectedField,str))
        else: # begins with string
            request.setFilterExpression('"{}" ILIKE \'{}%\''.format(selectedField,str))

        for feature in layer.getFeatures(request):
            # Check to see if it has been aborted
            if self.killed is True:
                return
            f = feature.attribute(selectedField)
            self.foundmatch.emit(layer, feature, selectedField, unicode(f))
            self.found += 1
            if self.found >= self.maxResults:
                self.killed=True
                return

