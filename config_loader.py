import os
import json
import toml

def loadToml():
    if not os.path.exists('./acc/config.toml'):
        print('config.toml not found, please check the file')
        return {}
    with open('./acc/config.toml', 'r+') as tomlFile:
        print('config.toml loaded')
        _configToml = toml.load(tomlFile)
        print(json.dumps(_configToml, indent=2, ensure_ascii=False))
        return _configToml

# Load the configuration once and make it accessible
configToml = loadToml()