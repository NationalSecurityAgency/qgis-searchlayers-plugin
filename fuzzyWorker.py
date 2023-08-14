import os
import re

from qgis.PyQt.QtCore import QObject, pyqtSignal

from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsProject, QgsVectorLayer, QgsFeatureRequest, QgsStringUtils
import traceback

class FuzzyWorker(QObject):
    '''This does all the hard work. It takes all the search parameters and 
    searches through the vector layers for a match.'''
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)
    foundmatch = pyqtSignal(QgsVectorLayer, object, object, str, object, str)
    
    def __init__(self, canvas, vlayers, infield, searchStr, algorithm, case_sensitive,
            fuzzy_contains, selectedField, maxResults, first_match_only,
            search_selected, match_metric, constrain_to_canvas):
        QObject.__init__(self)
        self.canvas = canvas
        self.vlayers = vlayers
        self.infield = infield
        self.searchStr = searchStr
        self.algorithm = algorithm
        self.case_sensitive = case_sensitive
        self.selectedField = selectedField
        self.killed = False
        self.maxResults = maxResults
        self.first_match_only = first_match_only
        self.search_selected = search_selected
        self.fuzzy_contains = fuzzy_contains
        self.match_metric = match_metric
        self.constrain_to_canvas = constrain_to_canvas
        self.epsg4326 = QgsCoordinateReferenceSystem('EPSG:4326')
        
    def run(self):
        '''Worker Run routine'''
        self.found = 0
        try:
            # Check to see if we are searching within a particular column of a specified
            # layer or whether we are searching all columns.
            if self.infield is True:
                for layer in self.vlayers:
                    self.searchFieldInLayer(layer, self.selectedField)
            else:
                for layer in self.vlayers:
                    self.searchLayer(layer)
        except:
            self.error.emit(traceback.format_exc())
            pass
        self.finished.emit(True)
            
    def kill(self):
        '''Set a flag that we want to stop looking for matches.'''
        self.killed = True
        
    def canvasExtent(self, layer):
        canvas_crs = self.canvas.mapSettings().destinationCrs()
        # We need to make sure the canvas extent is within its CRS bounds
        extent = self.canvas.extent() # This is returned as EPSG:4326
        epsg4326_to_canvas = QgsCoordinateTransform(self.epsg4326, canvas_crs, QgsProject.instance())
        legal_bounds = epsg4326_to_canvas.transform(canvas_crs.bounds())
        extent = legal_bounds.intersect(extent)
        
        # transform the extent to the layer's crs
        layer_crs = layer.crs()
        trans = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
        textent = trans.transform(extent)
        return(textent)
        
    def searchLayer(self, layer):
        '''Do a string search across all columns in a table'''
        if self.killed:
            return
        # Check for contraints
        if self.constrain_to_canvas and layer.isSpatial():
            extent = self.canvasExtent(layer)
            request = QgsFeatureRequest(extent)
        else:
            request = QgsFeatureRequest()
        fnames = []
        # Get and Keep a copy of the field names
        for field in layer.fields():
            fnames.append(field.name())
        # Get an iterator for all the features in the vector
        if self.search_selected:
            if layer.selectedFeatureCount() == 0:
                return
            iter = layer.getSelectedFeatures(request)
        else:
            iter = layer.getFeatures(request)
        search_str_len = len(self.searchStr)
        '''self.error.emit('algorithm: {}'.format(self.algorithm))
        self.error.emit('searchStr: {}'.format(self.searchStr))
        self.error.emit('case_sensitive: {}'.format(self.case_sensitive))
        self.error.emit('fuzzy_contains: {}'.format(self.fuzzy_contains))
        self.error.emit('match_metric: {}'.format(self.match_metric))'''
        if self.algorithm == 1:
            search_str_soundex = QgsStringUtils.soundex(self.searchStr)
        for feature in iter:
            # Check to see if it has been aborted
            if self.killed is True:
                return
            attrs = feature.attributes()
            # For now just search as if it were a string
            for id, f in enumerate(attrs):
                try:
                    s = str(f)
                    if self.algorithm == 0:
                        dist = QgsStringUtils.levenshteinDistance(self.searchStr, s, self.case_sensitive)
                        flen = len(s)
                        # self.error.emit('dist {}, flen {}'.format(dist, flen))
                        if flen <= search_str_len:
                            score = 1.0 - dist / search_str_len
                        else:
                            if self.fuzzy_contains:
                                dist = dist - flen + search_str_len
                                # self.error.emit('in fuzzy dist {}, flen {}, search_str_len {}'.format(dist, flen, search_str_len))
                                score = 1.0 - dist / search_str_len
                            else:
                                score = 1.0 - dist / flen
                        # self.error.emit('{} - {} - {}'.format(id, s, score))
                        if score >= self.match_metric:
                            self.foundmatch.emit(layer, feature, fnames[id], str(f), None, None)
                            self.found += 1
                            if self.found >= self.maxResults:
                                self.killed=True
                                return
                            if self.first_match_only:
                                break
                    else:
                        soundex = QgsStringUtils.soundex(s)
                        if soundex == search_str_soundex:
                            self.foundmatch.emit(layer, feature, fnames[id], str(f), None, None)
                            self.found += 1
                            if self.found >= self.maxResults:
                                self.killed=True
                                return
                            if self.first_match_only:
                                break
                except:
                    # self.error.emit(traceback.format_exc())
                    pass
        
    def searchFieldInLayer(self, layer, selectedField):
        '''Do a string search on a specific column in the table.'''
        if self.killed:
            return
        search_str_len = len(self.searchStr)
        if self.constrain_to_canvas and layer.isSpatial():
            extent = self.canvasExtent(layer)
            request = QgsFeatureRequest(extent)
        else:
            request = QgsFeatureRequest()
        # self.error.emit('searchFieldInLayer')
        # request.setSubsetOfAttributes([selectedField], layer.fields())
        if self.search_selected:
            iter = layer.getSelectedFeatures(request)
        else:
            iter = layer.getFeatures(request)
        for feature in iter:
            # Check to see if it has been aborted
            if self.killed is True:
                return
            try:
                f = feature.attribute(selectedField)
                s = str(f)
                if self.algorithm == 0:
                    dist = QgsStringUtils.levenshteinDistance(self.searchStr, s, self.case_sensitive)
                    flen = len(s)
                    # self.error.emit('dist {}, flen {}'.format(dist, flen))
                    if flen <= search_str_len:
                        score = 1.0 - dist / search_str_len
                    else:
                        if self.fuzzy_contains:
                            dist = dist - flen + search_str_len
                            # self.error.emit('in fuzzy dist {}, flen {}, search_str_len {}'.format(dist, flen, search_str_len))
                            score = 1.0 - dist / search_str_len
                        else:
                            score = 1.0 - dist / flen
                    # self.error.emit('{} - {} - {}'.format(id, s, score))
                    if score >= self.match_metric:
                        self.foundmatch.emit(layer, feature, selectedField, s, None, None)
                        self.found += 1
                        if self.found >= self.maxResults:
                            self.killed=True
                            return
                else:
                    soundex = QgsStringUtils.soundex(s)
                    if soundex == search_str_soundex:
                        self.foundmatch.emit(layer, feature, selectedField, str(f), None, None)
                        self.found += 1
                        if self.found >= self.maxResults:
                            self.killed=True
                            return
            except:
                pass

