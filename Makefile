draw:
	keymap parse -c 10 -z config/hillside46.keymap > keymap-drawer/hillside46.yaml
	keymap draw keymap-drawer/hillside46.yaml > keymap-drawer/hillside46.svg