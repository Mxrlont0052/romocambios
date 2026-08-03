#!/bin/bash
# Doble clic para abrir ROMO CAMBIOS en el navegador.
cd "$(dirname "$0")/web" || exit 1
exec /usr/bin/env python3 server.py
