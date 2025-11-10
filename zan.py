from inspect import signature
from dubbo.configs import ServiceConfig
print(signature(ServiceConfig.__init__))
