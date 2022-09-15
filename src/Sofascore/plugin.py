# -*- coding: UTF-8 -*-
from Plugins.Plugin import PluginDescriptor
from .interface import SofaInterface

def main(session, **kwargs):
	session.open(SofaInterface)

def Plugins(**kwargs):
	Descriptors=[]
	Descriptors.append(PluginDescriptor(name='SofaScore', description='Football live scores on SofaScore', where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon='icon.png'))
	return Descriptors