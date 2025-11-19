import os
import toml

def loadToml():
    tomlpath = './acc/config.toml'
    if not os.path.exists(tomlpath):
        print('config.toml not found, please check the file')
        return {}
    
    with open(tomlpath, 'r+') as tomlFile:
        _configToml = toml.load(tomlFile)
        print(f'loaded from {tomlpath}')
        return _configToml

# Load the configuration once and make it accessible
configToml = loadToml()