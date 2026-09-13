import inspect
from jupyter_server.services.kernels.connection.channels import ZMQChannelsWebsocketConnection as C
from jupyter_server.services.kernels.websocket import KernelWebsocketHandler as H
from jupyter_client.manager import KernelManager as K
from jupyter_server.services.kernels.kernelmanager import MappingKernelManager as M
for cls,names in [(C,['session','_session_default','_default_session']),
                  (K,['_create_connected_socket'])]:
    for name in names:
        if hasattr(cls,name):
            obj=getattr(cls,name)
            if callable(obj):print(inspect.getsource(getattr(obj,'func',obj)))
            else:print(cls.__name__,name,type(obj).__name__)
for cls in C.__mro__:
    for name,obj in cls.__dict__.items():
        if 'session' in name.lower() and callable(obj):
            print(cls.__name__,name)
            if 'default' in name:print(inspect.getsource(getattr(obj,'func',obj)))
