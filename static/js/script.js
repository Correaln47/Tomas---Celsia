// static/js/script.js
document.addEventListener('DOMContentLoaded', (event) => {
    // Conectar a Socket.IO. Asegúrate que la URL sea la correcta si no es el mismo origen.
    const socket = io(window.location.origin, {
        transports: ['websocket', 'polling'] // Prioriza WebSockets
    });

    const videoFeed = document.getElementById('video_feed');
    const videoPlayer = document.getElementById('videoPlayer');
    const videoSource = document.getElementById('videoSource');
    const mouthCanvas = document.getElementById('mouthCanvas');
    const mouthCtx = mouthCanvas.getContext('2d');
    const expressionText = document.getElementById('expressionText');
    const recognizedFaceText = document.getElementById('recognizedFaceText');
    const shutdownButton = document.getElementById('shutdownButton');
    const startRecognitionBtn = document.getElementById('startRecognitionBtn');
    const stopRecognitionBtn = document.getElementById('stopRecognitionBtn');
    const uploadPageBtn = document.getElementById('uploadPageBtn');


    let audioTrack = null; // Usaremos un solo Audio object dinámicamente
    let mouthAnimationInterval = null;
    let isMouthAnimating = false;

    // Configuración del canvas de la boca
    mouthCanvas.width = 150; // Ancho del canvas
    mouthCanvas.height = 75; // Alto del canvas

    function drawMouth(openHeightFactor) { // openHeightFactor de 0 (cerrada) a 1 (muy abierta)
        const baseHeight = 10; // Altura mínima de la boca (cerrada)
        const maxOpenOffset = 40; // Cuánto se abre adicionalmente como máximo
        const openHeight = baseHeight + (maxOpenOffset * openHeightFactor);

        mouthCtx.clearRect(0, 0, mouthCanvas.width, mouthCanvas.height);
        mouthCtx.fillStyle = 'rgb(220, 70, 100)'; // Un color de boca más rosado

        const width = mouthCanvas.width * 0.7; // Ancho de la boca
        const x = (mouthCanvas.width - width) / 2;
        const y = (mouthCanvas.height - openHeight) / 2; // Centrar verticalmente

        // Dibuja una elipse o un rectángulo redondeado para la boca
        mouthCtx.beginPath();
        mouthCtx.roundRect(x, y, width, openHeight, [openHeight / 2]); // Curvatura basada en la altura
        mouthCtx.fill();
    }


    function stopMouthAnimation() {
        if (mouthAnimationInterval) {
            clearInterval(mouthAnimationInterval);
            mouthAnimationInterval = null;
        }
        if (audioTrack && !audioTrack.paused) {
            audioTrack.pause();
            audioTrack.currentTime = 0; // Reinicia el audio
        }
        isMouthAnimating = false;
        drawMouth(0); // Dibuja la boca cerrada
        // console.log("Animación de boca y audio detenidos.");
    }

    function playAudioAndAnimateMouth(audioSrc, durationSeconds) {
        // console.log(`playAudioAndAnimateMouth: ${audioSrc}, duration: ${durationSeconds}s`);
        if (isMouthAnimating) {
            stopMouthAnimation(); // Detiene cualquier animación/audio anterior
        }

        // Crear nuevo objeto Audio cada vez para evitar problemas con re-uso
        audioTrack = new Audio(audioSrc);
        isMouthAnimating = true;

        let startTime = Date.now();
        const animationCycleMs = 300; // Duración de un ciclo de abrir/cerrar boca

        audioTrack.play().then(() => {
            // console.log("Audio reproduciéndose.");
            mouthAnimationInterval = setInterval(() => {
                const elapsed = Date.now() - startTime;
                if (elapsed > durationSeconds * 1000) {
                    stopMouthAnimation();
                    return;
                }
                // Simular movimiento de boca basado en un ciclo sinusoidal o triangular
                const cycleProgress = (elapsed % animationCycleMs) / animationCycleMs; // 0 a 1
                const mouthOpenFactor = Math.sin(cycleProgress * Math.PI); // 0 -> 1 -> 0
                drawMouth(mouthOpenFactor);

            }, 50); // Refrescar animación de boca cada 50ms
        }).catch(error => {
            console.error("Error reproduciendo audio:", error);
            stopMouthAnimation(); // Asegurar que se detenga si hay error
        });

        // Fallback por si el audio no emite 'ended' o para asegurar la detención
        setTimeout(() => {
            if (isMouthAnimating) { // Solo detener si sigue activa (por si ya se detuvo)
                // console.log("Timeout para detener animación de boca.");
                stopMouthAnimation();
            }
        }, (durationSeconds * 1000) + 500); // Duración en ms + buffer
    }

    // --- Conexión y eventos de Socket.IO ---
    socket.on('connect', () => {
        console.log('Conectado al servidor Socket.IO');
        recognizedFaceText.innerText = "Conectado. Esperando reconocimiento...";
    });

    socket.on('disconnect', () => {
        console.log('Desconectado del servidor Socket.IO');
        recognizedFaceText.innerText = "Desconectado. Intenta recargar.";
    });

    socket.on('connect_error', (error) => {
        console.error('Error de conexión Socket.IO:', error);
        recognizedFaceText.innerText = "Error de conexión.";
    });

    socket.on('video_frame', (data) => {
        if (videoFeed) {
            videoFeed.src = 'data:image/jpeg;base64,' + data.image;
        }
    });

    socket.on('expression', (data) => {
        if (expressionText) {
            expressionText.innerText = `Expresión: ${data.expression}`;
        }
    });

    socket.on('recognized_face', (data) => {
        console.log('Cara reconocida:', data);
        if (recognizedFaceText) {
            recognizedFaceText.innerText = `¡Hola ${data.name}!`;
        }
        if (data.audio_path && data.audio_duration) {
            // Asegurarse que la boca no esté visible si un video se está mostrando
            if (videoPlayer.style.display !== 'block') {
                 mouthCanvas.style.display = 'block'; // Mostrar canvas de boca
            }
            playAudioAndAnimateMouth(data.audio_path, data.audio_duration);
        } else {
            console.log("Datos de audio no recibidos para cara reconocida.");
        }
    });

    socket.on('play_video', (data) => {
        console.log('Recibido evento play_video:', data);
        if (videoSource && videoPlayer) {
            stopMouthAnimation(); // Detener boca si se va a reproducir un video
            mouthCanvas.style.display = 'none'; // Ocultar canvas de boca
            videoFeed.style.display = 'none'; // Ocultar stream de cámara
            
            videoSource.setAttribute('src', data.video_path);
            videoPlayer.style.display = 'block'; // Mostrar el reproductor de video
            videoPlayer.load();
            videoPlayer.play().then(() => {
                console.log(`Video ${data.video_path} reproduciéndose.`);
            }).catch(error => {
                console.error("Error reproduciendo video:", error);
                // Restaurar vista si falla el video
                mouthCanvas.style.display = 'block';
                videoFeed.style.display = 'block';
                videoPlayer.style.display = 'none';
            });
        } else {
            console.error("Elementos de video no encontrados (videoSource o videoPlayer).");
        }
    });

    socket.on('message', (data) => { // Para mensajes generales del servidor
        console.log('Mensaje del servidor:', data.text);
        if (data.text.toLowerCase().includes("apagando")) {
            document.body.innerHTML = `<div style="text-align:center; padding-top:50px;"><h1>${data.text}</h1><p>Puedes cerrar esta ventana.</p></div>`;
        } else {
            // Podrías tener un área de mensajes en tu HTML
            // alert(data.text); 
        }
    });

    // --- Event Listeners para botones ---
    if (videoPlayer) {
        videoPlayer.onended = () => {
            console.log("Video finalizado.");
            videoPlayer.style.display = 'none'; // Ocultar reproductor
            videoFeed.style.display = 'block';  // Mostrar stream de cámara de nuevo
            mouthCanvas.style.display = 'block';// Mostrar canvas de boca de nuevo
            drawMouth(0); // Boca cerrada
            if (recognizedFaceText) {
                recognizedFaceText.innerText = "Esperando reconocimiento...";
            }
             if (expressionText) {
                expressionText.innerText = "";
            }
        };
        videoPlayer.onerror = () => {
            console.error("Error en el reproductor de video.");
            videoPlayer.style.display = 'none';
            videoFeed.style.display = 'block';
            mouthCanvas.style.display = 'block';
            drawMouth(0);
        };
    }


    if (shutdownButton) {
        shutdownButton.addEventListener('click', () => {
            if (confirm('¿Estás seguro de que quieres apagar el sistema?')) {
                fetch('/shutdown', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        console.log(data.message);
                        // El servidor puede enviar un mensaje de 'apagando' a través de socket.io
                        // o podemos cambiar la UI aquí directamente.
                        document.body.innerHTML = `<div style="text-align:center; padding-top:50px;"><h1>${data.message}</h1><p>El sistema se está apagando. Puedes cerrar esta ventana.</p></div>`;
                    })
                    .catch(error => {
                        console.error('Error durante el apagado:', error);
                        alert('Error al intentar apagar el sistema.');
                    });
            }
        });
    }

    if (startRecognitionBtn) {
        startRecognitionBtn.addEventListener('click', () => {
            fetch('/start_recognition', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    console.log('Respuesta de start_recognition:', data.status);
                    if (recognizedFaceText) recognizedFaceText.innerText = "Reconocimiento iniciado...";
                })
                .catch(error => console.error('Error iniciando reconocimiento:', error));
        });
    }

    if (stopRecognitionBtn) {
        stopRecognitionBtn.addEventListener('click', () => {
            fetch('/stop_recognition', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    console.log('Respuesta de stop_recognition:', data.status);
                    if (recognizedFaceText) recognizedFaceText.innerText = "Reconocimiento detenido.";
                    stopMouthAnimation(); // Detener boca si el reconocimiento se para manualmente
                })
                .catch(error => console.error('Error deteniendo reconocimiento:', error));
        });
    }
    
    if (uploadPageBtn) {
        uploadPageBtn.addEventListener('click', () => {
            window.location.href = '/upload'; // Redirige a la página de subida
        });
    }

    // Inicializar boca cerrada
    drawMouth(0);
    mouthCanvas.style.display = 'block'; // Asegurarse que la boca sea visible al inicio

}); // Fin de DOMContentLoaded