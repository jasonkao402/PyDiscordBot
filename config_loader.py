import os
import toml

def loadToml():
    tomlpath = './acc/config.toml'
    if not os.path.exists(tomlpath):
        print('config.toml not found, please check the file')
        return {}
    # Load toml with chinese character support
    with open(tomlpath, 'r+', encoding='utf-8') as tomlFile:
        _configToml = toml.load(tomlFile)
        print(f'loaded from {tomlpath}, content:\n{_configToml.keys()}')
        return _configToml

# Load the configuration once and make it accessible
configToml = loadToml()