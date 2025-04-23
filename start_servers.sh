#!/bin/bash

# Ruta absoluta al directorio del proyecto
PROJECT_DIR="/home/celsia/Tomas---Celsia"
LOG_FILE="$PROJECT_DIR/server_startup.log"

echo "------------------------------" >> "$LOG_FILE"
echo "$(date): Iniciando secuencia de arranque..." >> "$LOG_FILE"

# Asegurar que el demonio pigpiod esté corriendo
echo "Verificando/Iniciando pigpiod..." | tee -a "$LOG_FILE"
# Verifica si ya está corriendo, si no, lo inicia con sudo (sin contraseña gracias a sudoers)
# El comando 'pgrep -f pigpiod > /dev/null' devuelve 0 si el proceso existe, y 1 si no.
if ! pgrep -f pigpiod > /dev/null ; then
    sudo /usr/bin/pigpiod # Usa la ruta correcta verificada con 'which pigpiod'
    if [ $? -eq 0 ]; then
        echo "pigpiod iniciado correctamente." | tee -a "$LOG_FILE"
        # Esperar un poco para que el demonio inicialice
        sleep 2
    else
        echo "ERROR: Falló al iniciar pigpiod con sudo." | tee -a "$LOG_FILE"
        # Decide si quieres continuar o detener el script si pigpiod falla
        # exit 1 # Descomenta esta línea para detener si pigpiod falla
    fi
else
    echo "pigpiod ya estaba corriendo." | tee -a "$LOG_FILE"
fi


# Navegar al directorio del proyecto
echo "Cambiando al directorio $PROJECT_DIR" | tee -a "$LOG_FILE"
cd "$PROJECT_DIR" || { echo "ERROR: No se pudo cambiar al directorio $PROJECT_DIR" | tee -a "$LOG_FILE"; exit 1; }

# Iniciar servidor principal (app.py) en segundo plano
echo "Iniciando app.py..." | tee -a "$LOG_FILE"
python3 app.py >> "$LOG_FILE" 2>&1 &
APP_PID=$!

# Iniciar servidor de movimiento (movement.py) en segundo plano
echo "Iniciando Movement/movement.py..." | tee -a "$LOG_FILE"
python3 Movement/movement.py >> "$LOG_FILE" 2>&1 &
MOVEMENT_PID=$!

# Iniciar servidor de carga (upload_server.py) en segundo plano
echo "Iniciando upload_server.py..." | tee -a "$LOG_FILE"
python3 upload_server.py >> "$LOG_FILE" 2>&1 &
UPLOAD_PID=$!

echo "Servidores iniciados (ver $LOG_FILE para detalles):"
echo "- Principal (app.py): PID $APP_PID"
echo "- Movimiento (movement.py): PID $MOVEMENT_PID"
echo "- Carga (upload_server.py): PID $UPLOAD_PID"
echo "$(date): Servidores lanzados con PIDs $APP_PID, $MOVEMENT_PID, $UPLOAD_PID" >> "$LOG_FILE"

echo "Puedes detenerlos manualmente usando 'kill <PID>' y 'sudo pkill pigpiod'"