PLUGINNAME = layersearch
PY_FILES = layerSearch.py __init__.py searchDialog.py searchWorker.py
EXTRAS = icon.png help.png metadata.txt
UI_FILES = layersearch.ui

default: compile

compile: $(UI_FILES)

deploy: compile
	mkdir -p $(HOME)/.qgis2/python/plugins/$(PLUGINNAME)
	cp -vf $(PY_FILES) $(HOME)/.qgis2/python/plugins/$(PLUGINNAME)
	cp -vf $(UI_FILES) $(HOME)/.qgis2/python/plugins/$(PLUGINNAME)
	cp -vf $(EXTRAS) $(HOME)/.qgis2/python/plugins/$(PLUGINNAME)
	cp -vfr doc $(HOME)/.qgis2/python/plugins/$(PLUGINNAME)
	cp -vf helphead.html $(HOME)/.qgis2/python/plugins/$(PLUGINNAME)/index.html
	python -m markdown -x markdown.extensions.headerid readme.md >> $(HOME)/.qgis2/python/plugins/$(PLUGINNAME)/index.html
	echo '</body>' >> $(HOME)/.qgis2/python/plugins/$(PLUGINNAME)/index.html

