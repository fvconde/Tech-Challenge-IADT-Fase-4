"""
Garante que a raiz do projeto esteja no sys.path para que 'import backend.app...'
funcione ao rodar pytest de qualquer lugar.
"""

import os
import sys

RAIZ = os.path.dirname(__file__)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
