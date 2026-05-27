def classFactory(iface):
    from .red_bt import RedBTPlugin
    return RedBTPlugin(iface)
