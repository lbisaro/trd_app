from local__config import SERVER_IDENTIFIER, DEBUG

def local_values(request):
    """
    Agrega valores de settings.py al contexto del template.
    """
    return {
        'SERVER_IDENTIFIER': SERVER_IDENTIFIER,
        'DEBUG': DEBUG,
    }