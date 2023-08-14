import os
import re

from qgis.PyQt.QtCore import QObject, pyqtSignal

from qgis.core import QgsCoordinateTransform, QgsCoordinateReferenceSystem, QgsVectorLayer, QgsFeatureRequest, QgsProject, QgsRectangle
import traceback

class Worker(QObject):
    '''This does all the hard work. It takes all the search parameters and 
    searches through the vector layers for a match.'''
    finished = pyqtSignal(bool)
    error = pyqtSignal(str)
    foundmatch = pyqtSignal(QgsVectorLayer, object, object, str, object, str)
    
    def __init__(self, canvas, vlayers, infield, searchStr, comparisonMode, case_sensitive, not_search,
            and_or, searchStr2, comparisonMode2, case_sensitive2, not_search2, selectedField, maxResults,
            first_match_only, two_string_match_single, search_selected, constrain_to_canvas):
        QObject.__init__(self)
        self.canvas = canvas
        self.vlayers = vlayers
        self.infield = infield
        self.searchStr = searchStr
        self.comparisonMode = comparisonMode
        self.case_sensitive = case_sensitive
        self.not_search = not_search
        self.and_or = and_or
        self.searchStr2 = searchStr2
        self.comparisonMode2 = comparisonMode2
        self.case_sensitive2 = case_sensitive2
        self.not_search2 = not_search2
        self.selectedField = selectedField
        self.killed = False
        self.maxResults = maxResults
        self.first_match_only = first_match_only
        self.two_string_match_single = two_string_match_single
        self.search_selected = search_selected
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
        # self.error.emit('canvas extent: {}'.format(extent))
        epsg4326_to_canvas = QgsCoordinateTransform(self.epsg4326, canvas_crs, QgsProject.instance())
        legal_bounds = epsg4326_to_canvas.transform(canvas_crs.bounds())
        extent = legal_bounds.intersect(extent)
        
        # self.error.emit('clipped canvas extent: {}'.format(extent))
        # transform the extent to the layer's crs
        layer_crs = layer.crs()
        trans = QgsCoordinateTransform(canvas_crs, layer_crs, QgsProject.instance())
        extent = trans.transform(extent)
        # self.error.emit('trans extent: {}'.format(textent))
        return(extent)

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
        if self.case_sensitive:
            flags1 = re.UNICODE
        else:
            flags1 = re.I|re.UNICODE
        if self.comparisonMode == 0: # Searching for an exact match
            p1 = re.compile("^"+re.escape(self.searchStr)+"$", flags1)
        elif self.comparisonMode == 1: # contains string
            p1 = re.compile(re.escape(self.searchStr), flags1)
        elif self.comparisonMode == 2: # begins with
            p1 = re.compile("^"+re.escape(self.searchStr), flags1)
        else: # ends with
            p1 = re.compile(re.escape(self.searchStr)+"$", flags1)
        if self.searchStr2 == '':  # There is only one search string
            if self.not_search:
                for feature in iter:
                    # Check to see if it has been aborted
                    if self.killed is True:
                        return
                    attrs = feature.attributes()
                    # For now just search as if it were a string
                    for id, f in enumerate(attrs):
                        try:
                            if not p1.search(str(f)):
                                self.foundmatch.emit(layer, feature, fnames[id], str(f), None, None)
                                self.found += 1
                                if self.found >= self.maxResults:
                                    self.killed=True
                                    return
                                if self.first_match_only:
                                    break
                        except:
                            pass
            else:
                for feature in iter:
                    # Check to see if it has been aborted
                    if self.killed is True:
                        return
                    attrs = feature.attributes()
                    # For now just search as if it were a string
                    for id, f in enumerate(attrs):
                        try:
                            if p1.search(str(f)):
                                self.foundmatch.emit(layer, feature, fnames[id], str(f), None, None)
                                self.found += 1
                                if self.found >= self.maxResults:
                                    self.killed=True
                                    return
                                if self.first_match_only:
                                    break
                        except:
                            pass
        else:
            if self.case_sensitive2:
                flags2 = re.UNICODE
            else:
                flags2 = re.I|re.UNICODE
            if self.comparisonMode2 == 0: # Searching for an exact match
                p2 = re.compile("^"+re.escape(self.searchStr2)+"$", flags2)
            elif self.comparisonMode2 == 1: # contains string
                p2 = re.compile(re.escape(self.searchStr2), flags2)
            elif self.comparisonMode2 == 2: # begins with
                p2 = re.compile("^"+re.escape(self.searchStr2), flags2)
            else:
                p2 = re.compile(re.escape(self.searchStr2)+"$", flags2)
            if self.two_string_match_single:
                for feature in iter:
                    # Check to see if it has been aborted
                    if self.killed is True:
                        return
                    attrs = feature.attributes()
                    # For now just search as if it were a string
                    for id, f in enumerate(attrs):
                        try:
                            s = str(f)
                            p1_results = True if p1.search(s) else False
                            if self.not_search:
                                p1_results = not p1_results
                            p2_results = True if p2.search(s) else False
                            if self.not_search2:
                                p2_results = not p2_results
                            if self.and_or == 0:  # AND Condition
                                results = p1_results and p2_results
                            else:
                                results = p1_results or p2_results
                            if results:
                                self.foundmatch.emit(layer, feature, fnames[id], s, None, None)
                                self.found += 1
                                if self.found >= self.maxResults:
                                    self.killed=True
                                    return
                                if self.first_match_only:
                                    break
                        except:
                            pass
            else:
                for feature in iter:
                    # Check to see if it has been aborted
                    if self.killed is True:
                        return
                    attrs = feature.attributes()
                    p1_true = False
                    p2_true = False
                    p1_attr = ''
                    p1_str = ''
                    p2_attr = ''
                    p2_str = ''
                    results = False
                    # For now just search as if it were a string
                    for id, f in enumerate(attrs):
                        try:
                            s = str(f)
                            if not p1_true:
                                p1_results = True if p1.search(s) else False
                                if self.not_search:
                                    p1_results = not p1_results
                                if p1_results:
                                    p1_true = True
                                    p1_attr = fnames[id]
                                    p1_str = s
                            if not p2_true:
                                p2_results = True if p2.search(s) else False
                                if self.not_search2:
                                    p2_results = not p2_results
                                if p2_results:
                                    p2_true = True
                                    p2_attr = fnames[id]
                                    p2_str = s
                            
                            if self.and_or == 0:  # AND Condition
                                results = p1_true and p2_true
                            else:
                                results = p1_true or p2_true
                            if results:
                                break
                        except:
                            pass
                    if results:
                        self.foundmatch.emit(layer, feature, p1_attr, p1_str, p2_attr, p2_str)
                        self.found += 1
                        if self.found >= self.maxResults:
                            self.killed=True
                            return

    def SqlStringFormat(self, field, not_search, case_sensitive, search_str, comparisonMode):
        if not_search:
            s_not = 'NOT '
        else:
            s_not = ''
        if comparisonMode == 1 or comparisonMode == 3:
            begin = '%'
        else:
            begin = ''
        if comparisonMode == 1 or comparisonMode == 2:
            end = '%'
        else:
            end = ''
        if case_sensitive:
            fstring = '("{}" {}LIKE \'{}{}{}\')'.format(field, s_not, begin, search_str, end)
        else:
            fstring = '(upper("{}") {}LIKE \'{}{}{}\')'.format(field, s_not, begin, search_str.upper(), end)
        return(fstring)
        
    def searchFieldInLayer(self, layer, selectedField):
        '''Do a string search on a specific column in the table.'''
        if self.killed:
            return
        # self.error.emit('searchFieldInLayer')
        fstring = self.SqlStringFormat(selectedField, self.not_search, self.case_sensitive, self.searchStr, self.comparisonMode)
        # self.error.emit('fstring: {}'.format(fstring))
        if self.searchStr2 != '':  # There are two search strings
            fstring2 = self.SqlStringFormat(selectedField, self.not_search2, self.case_sensitive2, self.searchStr2, self.comparisonMode2)
            if self.and_or == 0:
                fstring = '{} AND {}'.format(fstring, fstring2)
            else:
                fstring = '{} OR {}'.format(fstring, fstring2)

        if self.constrain_to_canvas and layer.isSpatial():
            extent = self.canvasExtent(layer)
            request = QgsFeatureRequest(extent)
        else:
            request = QgsFeatureRequest()
        # request.setSubsetOfAttributes([selectedField], layer.fields())
        request.setFilterExpression(fstring)
        if self.search_selected:
            iter = layer.getSelectedFeatures(request)
        else:
            iter = layer.getFeatures(request)
        for feature in iter:
            # Check to see if it has been aborted
            if self.killed is True:
                return
            f = feature.attribute(selectedField)
            self.foundmatch.emit(layer, feature, selectedField, str(f), None, None)
            self.found += 1
            if self.found >= self.maxResults:
                self.killed=True
                return

