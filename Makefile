PLUGINNAME = searchlayers
PLUGINS = "$(HOME)"/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)
PY_FILES = searchLayers.py __init__.py searchDialog.py searchWorker.py fuzzyWorker.py
EXTRAS = icon.png help.png metadata.txt
UI_FILES = searchlayers.ui

deploy: 
	mkdir -p $(PLUGINS)
	cp -vf $(PY_FILES) $(PLUGINS)
	cp -vf $(UI_FILES) $(PLUGINS)
	cp -vf $(EXTRAS) $(PLUGINS)
	cp -vfr doc $(PLUGINS)
	cp -vf helphead.html index.html
	python -m markdown -x extra readme.md >> index.html
	echo '</body>' >> index.html
	cp -vf index.html $(PLUGINS)/index.html

