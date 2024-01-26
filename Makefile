PLUGINNAME = searchlayers
PLUGINS = "$(HOME)"/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/$(PLUGINNAME)
PY_FILES = searchLayers.py __init__.py searchDialog.py searchWorker.py fuzzyWorker.py
EXTRAS = icon.png help.svg metadata.txt LICENSE
UI_FILES = searchlayers.ui

deploy: 
	mkdir -p $(PLUGINS)
	cp -vf $(PY_FILES) $(PLUGINS)
	mkdir -p $(PLUGINS)/i18n
	cp -vf i18n/searchLayers_ja.qm $(PLUGINS)/i18n
	cp -vf i18n/searchLayers_hu.qm $(PLUGINS)/i18n
	cp -vf $(UI_FILES) $(PLUGINS)
	cp -vf $(EXTRAS) $(PLUGINS)
	cp -vfr doc $(PLUGINS)
	cp -vf helphead.html index.html
	python -m markdown -x extra readme.md >> index.html
	echo '</body>' >> index.html
	cp -vf index.html $(PLUGINS)/index.html

