document.addEventListener("DOMContentLoaded", function() {
    const videoFeed = document.getElementById('videoFeed');
    const snapshotContainer = document.getElementById('snapshot-container');
    const snapshotImg = document.getElementById('snapshot');
    const emotionText = document.getElementById('emotionText');
    const faceCanvas = document.getElementById('faceCanvas');
    const videoContainer = document.getElementById('video-container');
    const interactionVideo = document.getElementById('interactionVideo');
    const ctx = faceCanvas.getContext('2d');
  
    let currentEmotion = "neutral"; // Guarda la emoción detectada
    let isAudioPlaying = false;
  
    // Variables para el análisis de audio
    let audioContext = null; // Contexto de audio global
    let audioAnalyser = null;
    let audioDataArray = null;
  
    // --- Función de Dibujo de Cara (MODIFICADA para boca al hablar) ---
    function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
        const cw = faceCanvas.width;
        const ch = faceCanvas.height;
  
        // --- Parámetros de Dibujo (Ajusta estos valores según tu preferencia) ---
        const faceCenterX = cw / 2;
        const faceCenterY = ch / 2; // Centrar verticalmente también
  
        // Ojos (calculados desde el centro)
        const eyeOffsetY = ch * -0.15; // Qué tan arriba del centro están los ojos
        const eyeSeparation = cw * 0.3; // Separación horizontal entre centros de ojos
        const baseEyeWidth = cw * 0.1;   // Ancho del ojo
        const baseEyeHeight = ch * 0.1;  // Alto base del ojo
        const eyeHeightChangeFactor = baseEyeHeight * 0.4; // Cuánto cambia el alto al hablar
  
        // Boca (calculada desde el centro)
        const mouthOffsetY = ch * 0.15; // Qué tan abajo del centro está la boca
        const baseMouthRadiusX = cw * 0.18; // Radio horizontal base
        const baseMouthRadiusY = ch * 0.05; // Radio vertical base (boca cerrada)
        const mouthOpenFactorY = ch * 0.1;  // Cuánto se abre verticalmente al hablar
        const mouthWidenFactorX = cw * 0.05; // Cuánto se ensancha horizontalmente al hablar
  
        // Limpieza y Oscilación
        const t = Date.now() / 1000; // Tiempo para animación
        const floatOffset = 5 * Math.sin(t * 0.8); // Oscilación vertical más sutil
        ctx.clearRect(0, 0, cw, ch);
  
        // --- Dibujar Ojos ---
        ctx.fillStyle = "black";
        const leftEyeX = faceCenterX - eyeSeparation / 2 - baseEyeWidth / 2;
        const rightEyeX = faceCenterX + eyeSeparation / 2 - baseEyeWidth / 2;
        const eyeY = faceCenterY + eyeOffsetY + floatOffset - baseEyeHeight / 2;
  
        let adjustedEyeHeight = baseEyeHeight;
        if (mouthState === "talking") {
            adjustedEyeHeight = baseEyeHeight - (amplitude * eyeHeightChangeFactor);
            adjustedEyeHeight = Math.max(adjustedEyeHeight, baseEyeHeight * 0.6);
        } else if (emotion === "surprise") {
             adjustedEyeHeight = baseEyeHeight * 1.2;
        }
  
        ctx.fillRect(leftEyeX, eyeY, baseEyeWidth, adjustedEyeHeight);
        ctx.fillRect(rightEyeX, eyeY, baseEyeWidth, adjustedEyeHeight);
  
        // --- Dibujar Boca ---
        const mouthCenterX = faceCenterX;
        const mouthCenterY = faceCenterY + mouthOffsetY + floatOffset;
  
        let adjustedMouthRadiusY = baseMouthRadiusY;
        let adjustedMouthRadiusX = baseMouthRadiusX;
        let startAngle = 0;
        let endAngle = Math.PI; // Por defecto, semicírculo inferior (triste/neutro base)
        let drawStroke = false;
        let drawFill = true;
        ctx.fillStyle = "red";
        ctx.strokeStyle = "black";
        ctx.lineWidth = Math.max(2, cw * 0.005);
  
        // --- Definir forma de la boca según emoción o estado ---
        if (mouthState === "talking") {
            // Calcular qué tan abierta está la boca al hablar
            const minTalkRadiusY = baseMouthRadiusY * 0.1; // Radio Y mínimo al hablar (casi cerrada)
            adjustedMouthRadiusY = minTalkRadiusY + (amplitude * (mouthOpenFactorY * 0.8)); // Abrir menos exagerado que sorpresa
            adjustedMouthRadiusX = baseMouthRadiusX + (amplitude * mouthWidenFactorX * 0.5); // Ensanchar un poco
  
            // Asegurar valores mínimos/máximos razonables
            adjustedMouthRadiusY = Math.max(minTalkRadiusY, adjustedMouthRadiusY);
            adjustedMouthRadiusY = Math.min(baseMouthRadiusY * 2.0, adjustedMouthRadiusY); // No abrir más que sorpresa
            adjustedMouthRadiusX = Math.max(baseMouthRadiusX * 0.8, adjustedMouthRadiusX);
  
            startAngle = 0;         // Dibujar elipse completa
            endAngle = Math.PI * 2;
            drawFill = true;        // Relleno
            drawStroke = true;       // Borde
            ctx.fillStyle = "black"; // Color negro al hablar (o rojo oscuro si prefieres)
  
        } else if (emotion === "happy") {
            startAngle = Math.PI;
            endAngle = 0;
            adjustedMouthRadiusX = baseMouthRadiusX * 1.1;
            adjustedMouthRadiusY = baseMouthRadiusY * 1.5;
            drawStroke = true;
            drawFill = false;
            ctx.strokeStyle = "red";
            ctx.lineWidth = Math.max(3, cw * 0.01);
        } else if (emotion === "sad") {
            startAngle = 0;
            endAngle = Math.PI;
            adjustedMouthRadiusX = baseMouthRadiusX * 0.9;
            adjustedMouthRadiusY = baseMouthRadiusY * 1.3;
            drawStroke = true;
            drawFill = false;
            ctx.strokeStyle = "blue";
            ctx.lineWidth = Math.max(3, cw * 0.01);
        } else if (emotion === "surprise") {
             startAngle = 0;
             endAngle = Math.PI * 2;
             adjustedMouthRadiusX = baseMouthRadiusX * 0.8;
             adjustedMouthRadiusY = baseMouthRadiusY * 2.5;
             ctx.fillStyle = "black";
             drawFill = true;
             drawStroke = false; // Sin borde explícito, ya es negra
        } else if (emotion === "angry") {
             startAngle = 0;
             endAngle = Math.PI;
             adjustedMouthRadiusX = baseMouthRadiusX * 1.1;
             adjustedMouthRadiusY = baseMouthRadiusY * 0.3;
             drawStroke = true;
             drawFill = false;
             ctx.strokeStyle = "darkred";
             ctx.lineWidth = Math.max(4, cw * 0.015);
        } else {
            // Estado Neutral por defecto (o cualquier otra emoción no definida)
             startAngle = 0;
             endAngle = Math.PI;
             adjustedMouthRadiusY = baseMouthRadiusY * 0.2; // Muy plana
             adjustedMouthRadiusX = baseMouthRadiusX;
             drawStroke = true;
             drawFill = false;
             ctx.strokeStyle = "black";
             ctx.lineWidth = Math.max(3, cw * 0.01);
        }
  
        // --- Dibujar la boca ---
        ctx.beginPath();
        ctx.ellipse(mouthCenterX, mouthCenterY, adjustedMouthRadiusX, adjustedMouthRadiusY, 0, startAngle, endAngle, (emotion === 'happy')); // Anticlockwise para sonrisa
  
        if (drawFill) {
            ctx.fill();
        }
        // Añadir borde negro si es necesario (stroke=true O si es relleno y no sorpresa/hablando)
        if (drawStroke || (drawFill && mouthState !== 'talking' && emotion !== 'surprise')) {
             if(drawStroke && !drawFill) { // Si es solo trazo, usa el color/grosor definido antes
                  ctx.stroke();
             } else { // Si hay relleno o es trazo sobre relleno, usa negro estándar
                 ctx.strokeStyle = "black";
                 ctx.lineWidth = 2;
                 ctx.stroke();
             }
        }
        ctx.closePath();
    } // Fin de drawFace
  
    // --- Función de Animación (MODIFICADA) ---
    function animateFace() {
        let mouthState = "neutral"; // Estado base
        let mouthAmplitude = 0;     // Amplitud base
  
        // Desactivar AudioContext temporalmente si causa problemas
        const useAudioContext = true; // Cambiar a false para desactivar animación por audio
  
        if (useAudioContext && isAudioPlaying && audioAnalyser && audioDataArray) {
            if (audioContext && audioContext.state === 'running') {
                audioAnalyser.getByteFrequencyData(audioDataArray);
                let sum = audioDataArray.reduce((a, b) => a + b, 0);
                let avg = audioDataArray.length > 0 ? sum / audioDataArray.length : 0;
                mouthAmplitude = avg / 128;
                mouthAmplitude = Math.min(1.5, Math.max(0, mouthAmplitude));
                mouthState = "talking";
            } else {
                 mouthState = currentEmotion;
            }
        } else {
            mouthState = currentEmotion;
        }
  
        drawFace(currentEmotion, mouthState, mouthAmplitude);
        requestAnimationFrame(animateFace); // Solicitar el siguiente frame
    }
  
    // --- Configuración del Analizador de Audio (MODIFICADA) ---
    function setupAudioAnalyser(audioElement) {
        // Crear contexto sólo si no existe o está cerrado
        if (!audioContext || audioContext.state === 'closed') {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
  
        // Reanudar contexto si está suspendido
        if (audioContext.state === 'suspended') {
            audioContext.resume().catch(e => console.error("Error reanudando AudioContext:", e));
        }
  
        // Sólo proceder si el contexto está activo
        if (audioContext.state === 'running') {
            try {
                // Evitar crear múltiples sources para el mismo elemento
                // (Esto es una suposición, necesitaría una forma más robusta de rastrear si ya existe)
                // if (!audioElement._sourceNode) {
                //     audioElement._sourceNode = audioContext.createMediaElementSource(audioElement);
                // }
                // const track = audioElement._sourceNode;
                const track = audioContext.createMediaElementSource(audioElement); // Simplificado por ahora
  
                audioAnalyser = audioContext.createAnalyser();
                audioAnalyser.fftSize = 256;
                const bufferLength = audioAnalyser.frequencyBinCount;
                audioDataArray = new Uint8Array(bufferLength);
  
                track.connect(audioAnalyser);
                audioAnalyser.connect(audioContext.destination);
                console.log("Audio Analyser configurado.");
            } catch (e) {
                 console.error("Error configurando Audio Analyser:", e);
                 audioAnalyser = null;
                 audioDataArray = null;
            }
        } else {
            console.warn("AudioContext no está activo. No se puede configurar Analyser.");
            audioAnalyser = null;
            audioDataArray = null;
        }
    }
  
  
    // --- Reproducción de Audio (MODIFICADA) ---
    function playAudio(url) {
        console.log("Intentando reproducir audio:", url);
        return new Promise((resolve, reject) => {
            const audio = new Audio(url);
  
            audio.onloadedmetadata = () => {
                console.log(`>>> Metadatos Audio cargados. Duración detectada: ${audio.duration} segundos`);
            };
  
            audio.onplay = () => {
                console.log("Audio onplay event triggered.");
                // Intentar configurar o reconfigurar el analizador
                setupAudioAnalyser(audio); // Descomentar si se usa AudioContext
                isAudioPlaying = true;
            };
  
            audio.onerror = (e) => {
                console.error(">>> ERROR en elemento Audio:", e);
                isAudioPlaying = false;
                audioAnalyser = null;
                audioDataArray = null;
                reject(e); // Rechazar la promesa
            };
  
            audio.onended = () => {
                console.log("Audio onended event triggered.");
                // console.log("DEBUG: Audio onended, llamando a resolve()"); // Log de depuración anterior
                isAudioPlaying = false;
                audioAnalyser = null; // Limpiar para la próxima vez
                audioDataArray = null;
                resolve(); // Resolver la promesa
            };
  
            // Intentar reproducir
            audio.play().then(() => {
                console.log("Comando audio.play() ejecutado para:", url);
            }).catch(e => {
                console.error("Error al iniciar audio automáticamente (audio.play().catch):", e);
                isAudioPlaying = false;
                if (audioContext && audioContext.state === 'suspended') {
                    console.log("Intentando reanudar AudioContext...");
                    audioContext.resume().then(() => {
                         console.log("AudioContext reanudado, reintentando play...");
                         return audio.play(); // Reintentar play
                    }).then(() => {
                        console.log("Reintento de play exitoso tras reanudar contexto.");
                    }).catch(e2 => {
                        console.error("Error en reintento de play:", e2);
                        reject(e); // Rechazar con el error original
                    });
                } else {
                    reject(e); // Rechazar si no es un problema de suspensión
                }
            });
        });
    }
  
  
    // --- Poll Detection Status ---
    function pollDetectionStatus() {
        fetch('/detection_status')
            .then(res => res.json())
            .then(data => {
                if (data.detected) {
                    clearInterval(pollInterval);
                    currentEmotion = data.emotion;
                    console.log("Detection complete. Emotion:", currentEmotion);
                    videoFeed.style.display = "none";
                    snapshotContainer.style.display = "block";
                    const newSrc = "/snapshot?" + new Date().getTime();
                    // console.log("Setting snapshot image src to:", newSrc); // Log menos importante
                    snapshotImg.src = newSrc;
                    emotionText.innerText = "Emoción Detectada: " + currentEmotion;
                    drawFace(currentEmotion, currentEmotion, 0); // Forzar cara de emoción detectada
                    triggerAudio(currentEmotion);
                } else {
                     currentEmotion = "neutral";
                     // drawFace("neutral", "neutral", 0); // Dibuja neutral mientras no detecta
                }
            })
            .catch(err => {
                console.error("Error polling detection status:", err);
                currentEmotion = "neutral";
                // drawFace("neutral", "neutral", 0);
            });
    }
    let pollInterval = setInterval(pollDetectionStatus, 1000); // Revisa cada segundo
  
    // --- Play Emotion-Specific Audio ---
    function triggerAudio(emotion) {
        console.log(`Triggering audio for emotion: ${emotion}`);
        fetch(`/get_random_audio?emotion=${emotion}`)
            .then(res => {
                 if (!res.ok) { throw new Error(`HTTP error! status: ${res.status}, message: ${res.statusText}`); }
                 return res.json();
            })
            .then(data => {
                if (data.audio_url) {
                    console.log(`Audio URL received: ${data.audio_url}`);
                    playAudio(data.audio_url)
                        .then(() => {
                            console.log("Audio playback promise resolved (finished).");
                            // Añadir retraso opcional antes de video
                            // console.log("DEBUG: Audio terminado, esperando 1 segundo antes de video...");
                            // setTimeout(() => {
                            //     console.log("DEBUG: Llamando a triggerVideo ahora.");
                                 triggerVideo();
                            // }, 1000); // Espera 1000ms = 1 segundo
                        })
                        .catch(err => {
                             console.error("Error en promesa playAudio:", err);
                             triggerVideo(); // Ir al video incluso si el audio falla
                         });
                } else {
                    console.error("No audio file found for emotion:", emotion, "Response:", data);
                    triggerVideo();
                }
            })
            .catch(err => {
                 console.error("Error fetching audio URL:", err);
                 triggerVideo();
             });
    }
  
    // --- Trigger Interaction Video ---
    function triggerVideo() {
        console.log("Triggering video playback.");
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
  
        fetch('/get_random_video')
             .then(res => {
                 if (!res.ok) { throw new Error(`HTTP error! status: ${res.status}, message: ${res.statusText}`); }
                 return res.json();
             })
            .then(data => {
                if (data.video_url) {
                    console.log(`Video URL received: ${data.video_url}`);
                    interactionVideo.src = data.video_url;
  
                    interactionVideo.onloadedmetadata = () => {
                        console.log(`>>> Metadatos Video cargados. Duración detectada: ${interactionVideo.duration} segundos`);
                    };
  
                    interactionVideo.onerror = (e) => {
                        console.error(">>> ERROR en elemento Video:", e);
                        // El onended probablemente se llame igual o el flujo siga a restart
                        // Podríamos forzar aquí el reinicio si es necesario:
                        // restartInteraction();
                    };
  
                    interactionVideo.onended = () => {
                        console.log("Video onended event triggered.");
                         // Añadir retraso opcional antes de reiniciar
                         // console.log("DEBUG: Video terminado, esperando 1 segundo antes de reiniciar...");
                         // setTimeout(() => {
                         //    console.log("DEBUG: Llamando a restartInteraction ahora.");
                             restartInteraction();
                         // }, 1000); // Espera 1000ms = 1 segundo
                    };
  
                    interactionVideo.play().then(() => {
                        console.log("Comando video.play() ejecutado.");
                    }).catch(e => {
                         console.error("Error starting video playback:", e);
                         restartInteraction(); // Reiniciar si el video no puede empezar
                     });
  
                } else {
                    console.error("No video file found. Response:", data);
                    restartInteraction();
                }
            })
            .catch(err => {
                 console.error("Error fetching video URL:", err);
                 restartInteraction();
             });
    }
  
    // --- Restart Interaction ---
    function restartInteraction() {
        console.log("Restarting interaction...");
        // Limpiar estado antes de recargar (opcional, pero puede ayudar)
        isAudioPlaying = false;
        audioAnalyser = null;
        audioDataArray = null;
        // No cerrar audioContext aquí, podría causar problemas si se reusa rápido.
  
        fetch('/restart')
            .then(res => res.json())
            .then(data => {
                console.log("Restart signal sent to server:", data);
                location.reload();
            })
            .catch(err => {
                console.error("Error sending restart signal:", err);
                location.reload(); // Intentar recargar igualmente
            });
    }
  
    // --- Inicialización ---
    console.log("Document loaded. Initializing face animation.");
    // Ajustar tamaño inicial del canvas si es necesario
    // faceCanvas.width = faceCanvas.offsetWidth;
    // faceCanvas.height = faceCanvas.offsetHeight;
    drawFace("neutral", "neutral", 0); // Dibujar estado inicial neutral
    animateFace(); // Iniciar el bucle de animación
  
  }); // Fin de DOMContentLoaded