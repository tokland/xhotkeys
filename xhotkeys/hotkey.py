#!/usr/bin/python
import configobj

def string2bool(s):
    if isinstance(s, bool):
        return s
    return (s.lower() in ("enable", "enabled", "true", "yes", "on", "1"))

def strtype2type(s):
  info = {
    "string": str,
    "boolean": bool,
  }
  return info[s]

class ConfigObjModel:
    """Generic model for configobj back-end"""
    name_attribute = "name"
    attributes = {}
    
    def __init__(self, name, opts={}):
        self._name = name
        setattr(self, self.name_attribute, name)
        for name, options in self.attributes.iteritems():
            if "default" in options:
              setattr(self, name, options["default"])
            else:
              setattr(self, name, strtype2type(options["type"])())        
        for attr, value in opts.iteritems():
            if attr != self.name_attribute and attr not in self.attributes:
                raise ValueError, "Attribute unknown: %s" % attr
            if attr in self.attributes:
                options = self.attributes[attr]
                if options["type"] == "boolean":
                    value = string2bool(value)
            setattr(self, attr, value)

    @classmethod    
    def init(cls, configfile):
        cls.config = configobj.ConfigObj(configfile)        
    
    @classmethod    
    def items(cls):        
        return [cls(name, opts) for (name, opts) in cls.config.items()]

    def get_attributes(self):
        return dict((attr, getattr(self, attr)) for attr in self.attributes)
            
    def update(self, params):
        for attr, value in params.iteritems():
            if attr != self.name_attribute and attr not in self.attributes:
                raise ValueError, "Attribute unknown: %s" % attr
            setattr(self, attr, value) 
        
    def valid(self, params=None, attribute=None):
        if not params:
            params = dict((attr, getattr(self, attr)) 
                for attr in self.attributes.keys()+[self.name_attribute])
        #if attribute == self.name_attribute:
        #    return bool(params[self.name_attribute])            
        if not attribute or attribute == self.name_attribute:
            if not params[self.name_attribute]:
                return False
            if self._name != params[self.name_attribute] and \
                    params[self.name_attribute] in self.__class__.config.sections:
                return False
            if attribute == self.name_attribute:
                return True
            tocheck = [(k, v) for (k, v) in params.items() 
                if k != self.name_attribute]
        else:
            tocheck = [(attribute, params[attribute])]            
        for key, value in tocheck:
            if key == self.name_attribute:
                continue
            if not self.attributes[key].get("void", True):
                if not value:
                    return False
        return True
                         
    def save(self):
        if not self.valid():
            raise ValueError, "Validation failed"
        new_attributes = dict((attr, getattr(self, attr)) 
            for attr in self.attributes)
        name_value = getattr(self, self.name_attribute)
        if self._name != name_value:
            if self._name:
                self.__class__.config.rename(self._name, name_value )
            self._name = name_value
        self.__class__.config[self._name] = new_attributes  
        self.__class__.config.write()
        
    def delete(self):
        del self.__class__.config[self.name]
        self.__class__.config.write()

class Hotkey(ConfigObjModel):
    """Model for hotkey item"""
    
    attributes = {
        "command": dict(type="string", void=False),
        "binding": dict(type="string"),
        "directory": dict(type="string", default="~"),
    }
