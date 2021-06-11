# Search Layers Plugin

The Search Layers plugin features enhanced textual vector layer searching in QGIS. It provides the ability to search across all layers and all fields.

Search Layers is located in the QGIS Plugins menu under *"Plugins->Search Layers->Search Layers"* or by selecting the tool bar icon. ![Toolbar Icon](icon.png)

The following dialog box is displayed when "Search Layers" is launched.

![Search Layers Dialog](doc/layersearch.jpg)

Under **Search String**, enter the search string. **Search Layers** specifies whether the search will be on *&lt;All Layers&gt;*, *&lt;Selected layers&gt;*, or on any of the vector layers in the QGIS project. If a specific layer is selected then **Search Fields** will be enabled and by default *&lt;All Fields&gt;* will be selected, but any field can be selected from the layer and the search will only search on that layer and field.

**Comparison** is the matching criteria and is as follows.

* **=** - This requires an exact match including case.
* **Contains** - This performs a case independent search in which a match is made if a field contains the search string.
* **Begins with** - This is a case independent search in which the search finds any field that begins with the search string.

Click  the **Search** button to begin the search. In the case of a large data set, clicking on **Stop** will halt the process. Note that the plugin stops after finding 1500 matches.

When matches are found and clicked on, the features are highlighted on the map. If **Automatically zoom to selected features** is checked, QGIS also zooms to the selected features. The matches can be examined even before the search process has been completed.

