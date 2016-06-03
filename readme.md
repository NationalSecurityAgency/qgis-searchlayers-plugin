#Layer Search Plugin

The Layer Search plugin features enhance textual vector layer searching in QGIS. The existing QGIS searching capabilities are limited to a particular layer and a particular column. What is different about this plugin is that it will search all layers and all fields for a particular string.

Layer Search will be located in the QGIS Plugins menu under *"Plugins->Search->Search Layer(s)"* or by selecting the tool bar icon. ![Toolbar Icon](icon.png)

The following dialog box is displayed when the “Search Layer(s)” is launched.

![Layer Search Dialog](doc/layersearch.jpg)

Enter the search string into the **Find** field. You can search **In** *<All Layers>*, *<Selected layers>*, or on any of the vector layers in your project. Note that only vector layers will be listed. **Comparison** is the matching criteria. It can be.

* **=** - This requires an exact match including case.
* **Contains** - This performs a case independent search in which the search finds any item where a field contains the search string.
* **Begins with** - This is a case independent search in which the search finds any field that begins with the search string.

**Search in** is only enable when a specific vector layer is selected and in that case you can specify which column you want to search.

Click on the **Search** button to begin the search. In the case of a large data set you can click on **Stop** at any time to halt the process. Note that this plugin stops after finding 1500 matches.

Once matches are found, by clicking on them QGIS will zoom to that feature, select, and highlight it.

