draw:
	keymap -c keymap-drawer/config.yaml parse -c 10 -z config/hillside46.keymap > keymap-drawer/hillside46.yaml
	keymap -c keymap-drawer/config.yaml draw keymap-drawer/hillside46.yaml > keymap-drawer/hillside46.svg