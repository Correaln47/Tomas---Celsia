document.addEventListener("DOMContentLoaded", function() {
    const videoFeed = document.getElementById('videoFeed');
    const snapshotContainer = document.getElementById('snapshot-container');
    const snapshotImg = document.getElementById('snapshot');
    const emotionText = document.getElementById('emotionText');
    const faceCanvas = document.getElementById('faceCanvas');
    const videoContainer = document.getElementById('video-container');
    const interactionVideo = document.getElementById('interactionVideo');
    const ctx = faceCanvas.getContext('2d');

    let currentEmotion = "neutral";
    let isAudioPlaying = false; // Variable para rastrear si el audio está sonando
    let pollInterval;
    let currentForcedVideoProcessed = null; // Para saber si estamos reproduciendo un video forzado
    let audioContext = null;
    let audioAnalyser = null;
    let audioDataArray = null; // Array para los datos de frecuencia

    // Flag para saber si el analizador está listo y el audio context está activo
    let isAnalyserReady = false;


     // --- Funciones de dibujo y audio (modificadas ligeramente para el analizador) ---
    function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
    const cw = faceCanvas.width;
    const ch = faceCanvas.height;
    const faceCenterX = cw / 2;
    const faceCenterY = ch / 2;
    ctx.clearRect(0, 0, cw, ch);

    // Movimiento sutil de la cara
    const t = Date.now() / 1000;
    const floatOffset = (ch * 0.01) * Math.sin(t * 0.8);

    // --- OJOS (Proporciones ajustadas para un lienzo más grande) ---
    const eyeOffsetY = ch * -0.2; // Ojos un poco más arriba
    const eyeSeparation = cw * 0.5; // Más separados
    const baseEyeWidth = cw * 0.15; // Más anchos
    let baseEyeHeight = ch * 0.15; // Más altos
    ctx.fillStyle = "black";

    let adjustedEyeHeight = baseEyeHeight;
    if (mouthState === "talking") {
        adjustedEyeHeight = baseEyeHeight - (amplitude * baseEyeHeight * 0.6);
        adjustedEyeHeight = Math.max(adjustedEyeHeight, baseEyeHeight * 0.4);
    } else if (emotion === "surprise") {
        adjustedEyeHeight = baseEyeHeight * 1.2;
    }

    const leftEyeX = faceCenterX - (eyeSeparation / 2);
    const rightEyeX = faceCenterX + (eyeSeparation / 2);
    const eyeY = faceCenterY + eyeOffsetY + floatOffset;
    ctx.fillRect(leftEyeX - baseEyeWidth / 2, eyeY - adjustedEyeHeight / 2, baseEyeWidth, adjustedEyeHeight);
    ctx.fillRect(rightEyeX - baseEyeWidth / 2, eyeY - adjustedEyeHeight / 2, baseEyeWidth, adjustedEyeHeight);


    // --- BOCA (Proporciones ajustadas para un lienzo más grande) ---
    const mouthOffsetY = ch * 0.2; // Boca un poco más abajo
    const baseMouthRadiusX = cw * 0.25; // Boca más ancha
    const baseMouthRadiusY = ch * 0.1; // Boca más alta
    const mouthCenterX = faceCenterX;
    const mouthCenterY = faceCenterY + mouthOffsetY + floatOffset;

    let adjustedMouthRadiusX = baseMouthRadiusX;
    let adjustedMouthRadiusY = baseMouthRadiusY;
    let startAngle = 0;
    let endAngle = Math.PI;
    let drawStroke = false;
    let drawFill = false;

    ctx.beginPath();
    ctx.lineWidth = Math.max(5, cw * 0.015); // Línea más gruesa

    if (mouthState === "talking") {
        adjustedMouthRadiusY = (baseMouthRadiusY * 0.1) + (amplitude * baseMouthRadiusY * 1.5);
        adjustedMouthRadiusX = baseMouthRadiusX + (amplitude * baseMouthRadiusX * 0.2);
        startAngle = 0;
        endAngle = Math.PI * 2;
        drawFill = true;
        ctx.fillStyle = "black";
    } else if (emotion === "happy") {
        startAngle = 0; endAngle = Math.PI;
        adjustedMouthRadiusY = baseMouthRadiusY;
        drawStroke = true; ctx.strokeStyle = "red";
    } else if (emotion === "sad") {
        startAngle = Math.PI; endAngle = 0;
        adjustedMouthRadiusY = baseMouthRadiusY;
        drawStroke = true; ctx.strokeStyle = "blue";
    } else if (emotion === "surprise") {
        startAngle = 0; endAngle = Math.PI * 2;
        adjustedMouthRadiusY = baseMouthRadiusY * 1.2;
        drawFill = true; ctx.fillStyle = "black";
    } else if (emotion === "angry") {
        startAngle = 0; endAngle = Math.PI;
        adjustedMouthRadiusY = baseMouthRadiusY * 0.2;
        drawStroke = true; ctx.strokeStyle = "darkred";
    } else { // Neutral
        startAngle = 0; endAngle = Math.PI;
        adjustedMouthRadiusY = baseMouthRadiusY * 0.1;
        drawStroke = true; ctx.strokeStyle = "black";
    }

    ctx.ellipse(mouthCenterX, mouthCenterY, adjustedMouthRadiusX, adjustedMouthRadiusY, 0, startAngle, endAngle);

    if (drawFill) ctx.fill();
    if (drawStroke) ctx.stroke();
    ctx.closePath();
}

     function setupAudioAnalyser(audioElement) {
         // Crea AudioContext la primera vez que se llama
         if (!audioContext) {
             audioContext = new (window.AudioContext || window.webkitAudioContext)();
         }

         // Asegurarse de que el contexto de audio esté activo
         if (audioContext.state === 'suspended') {
             audioContext.resume();
         }


         // Evitar crear múltiples analizadores o fuentes para el mismo elemento de audio
         if (audioAnalyser) {
              audioAnalyser.disconnect();
         }

         try {
             const source = audioContext.createMediaElementSource(audioElement);
             audioAnalyser = audioContext.createAnalyser();
             audioAnalyser.fftSize = 256; // Tamaño del FFT, afecta la granularidad de los datos de frecuencia
             audioDataArray = new Uint8Array(audioAnalyser.frequencyBinCount); // Array para los datos de frecuencia

             source.connect(audioAnalyser);
             audioAnalyser.connect(audioContext.destination);

             isAnalyserReady = true; // Marcar el analizador como listo

         } catch (e) {
             console.error("JS: Error setting up audio analyser:", e);
             audioAnalyser = null;
             audioDataArray = null;
             isAnalyserReady = false;
         }
     }

     function getAverageAmplitude() {
          if (!isAnalyserReady || !audioDataArray) {
               return 0; // No hay datos de audio disponibles
          }
          audioAnalyser.getByteFrequencyData(audioDataArray);
          // Calcular el promedio (o alguna otra métrica) de los datos de frecuencia
          // Puedes ajustar qué parte del array usas para centrarte en diferentes rangos de frecuencia de voz
          const lowerHalf = audioDataArray.slice(0, audioDataArray.length / 2); // Considerar solo las frecuencias más bajas/medias
          const average = lowerHalf.reduce((sum, value) => sum + value, 0) / lowerHalf.length;
          // Normalizar el promedio a un rango entre 0 y 1
          const normalizedAmplitude = average / 255; // Los datos de frecuencia están en el rango 0-255
          return normalizedAmplitude;
     }


     function animateFace() {
         const amplitude = isAudioPlaying && isAnalyserReady ? getAverageAmplitude() : 0;
         const mouthState = isAudioPlaying ? "talking" : currentEmotion; // O 'neutral' si quieres que la boca se cierre completamente

         // Solo dibujar si no estamos mostrando el video a pantalla completa
         if (videoContainer.style.display !== "flex") {
              drawFace(currentEmotion, mouthState, amplitude);
         } else {
             // Opcional: dibujar una cara estática o vaciar el canvas cuando se reproduce video grande
             ctx.clearRect(0, 0, faceCanvas.width, faceCanvas.height);
         }


         requestAnimationFrame(animateFace);
     }

     async function playAudio(url) {
         console.log("JS: Attempting to play audio:", url);
         return new Promise((resolve, reject) => {
            // Usar un nuevo elemento Audio cada vez puede ser más simple
            const audio = new Audio(url);
            setupAudioAnalyser(audio); // Configura el analizador

            audio.onplay = () => {
                 console.log("JS: Audio started playing:", url);
                 isAudioPlaying = true;
            };
            audio.onended = () => {
                 console.log("JS: Audio ended:", url);
                 isAudioPlaying = false;
                 isAnalyserReady = false; // Resetear analizador cuando termina
                 resolve(); // Resuelve la promesa cuando el audio termina
            };
            audio.onerror = (e) => {
                 console.error("JS: Audio error:", url, e);
                 isAudioPlaying = false;
                 isAnalyserReady = false; // Resetear analizador en caso de error
                 reject(e); // Rechaza la promesa si hay un error
            };

            // Es crucial que play() se llame después de una interacción del usuario
            // Aunque la detección no es una interacción directa, el primer play
            // de la página principal podría requerir un clic inicial del usuario.
            // Si estás teniendo problemas, considera un botón "Iniciar" que llame a playAudio por primera vez.
            audio.play().catch(e => {
                 console.error("JS: Error starting audio playback:", url, e);
                 isAudioPlaying = false;
                 isAnalyserReady = false;
                 reject(e); // Rechaza la promesa si play() falla
            });
        });
     }
     // --- FIN Funciones de dibujo y audio ---


    function pollDetectionStatus() {
        fetch('/detection_status')
            .then(res => {
                if (!res.ok) {
                    console.error(`JS: HTTP error! status: ${res.status}`);
                    currentEmotion = "neutral";
                    // Mantener la UI de video feed si no estamos mostrando video grande
                    if (videoContainer.style.display !== "flex") {
                         document.getElementById('main-container').style.display = "flex";
                         videoContainer.style.display = "none";
                         videoFeed.style.display = "block"; // Mostrar el video feed
                         snapshotContainer.style.display = "none"; // Ocultar snapshot
                         emotionText.innerText = "Error de conexión..."; // Indicador de problema
                         // La animación de la cara seguirá corriendo y dibujará neutral
                    }
                    return null;
                }
                return res.json();
            })
            .then(data => {
                if (data === null) {
                    return; // No procesar si hubo un error HTTP
                }

                // --- Lógica para manejar el "skip video" desde otra interfaz (usando restart_requested) ---
                // Si el flag restart_requested es true Y actualmente se está reproduciendo un video grande
                if (data.restart_requested && interactionVideo && interactionVideo.paused === false) {
                     console.log("JS: Restart requested from server while video playing. Stopping video and restarting interaction.");
                     restartInteraction(); // Detiene el video actual y reinicia la página
                     return; // Ya hemos manejado el reinicio, salir de esta ejecución del .then
                }


                // --- Lógica para manejar video forzado (prioridad alta) ---
                // data.forced_video se establece en el servidor (app.py) cuando se recibe /play_specific_video
                // Se resetea a None en el servidor después de enviarlo una vez en /detection_status
                if (data.forced_video && data.forced_video !== currentForcedVideoProcessed) {
                    console.log("JS: FORCED VIDEO received:", data.forced_video);
                    currentForcedVideoProcessed = data.forced_video; // Registrar que estamos manejando este video forzado

                    // Ocultar la interfaz principal y mostrar el contenedor de video
                    document.getElementById('main-container').style.display = "none";
                    videoContainer.style.display = "flex";
                    videoFeed.style.display = "none"; // Asegurarse de que el video feed esté oculto

                    const videoUrl = `/static/video/${data.forced_video}`;
                    playSpecificVideo(videoUrl); // Iniciar la reproducción del video forzado

                    // No necesitamos hacer nada más en este ciclo de polling si estamos reproduciendo un video forzado.
                    // La lógica para volver a la interfaz principal está en playSpecificVideo.onended/onerror
                    return;
                }


                // --- Lógica para manejar detección de emoción (si NO estamos reproduciendo un video forzado) ---
                if (!currentForcedVideoProcessed) {
                     // Si la detección en el servidor está completa y NO estamos reproduciendo audio/video
                    if (data.detected && !isAudioPlaying && interactionVideo.paused !== false) {
                        currentEmotion = data.emotion;
                        console.log("JS: DETECTION complete. Emotion:", currentEmotion);

                        // Mostrar la interfaz principal con el snapshot
                        document.getElementById('main-container').style.display = "flex"; // Asegurar visibilidad
                        videoContainer.style.display = "none"; // Asegurarse de que el video grande esté oculto
                        videoFeed.style.display = "none"; // Ocultar el video feed en vivo
                        snapshotContainer.style.display = "block"; // Mostrar el contenedor del snapshot

                        // Cargar y mostrar el snapshot y la emoción detectada
                        snapshotImg.src = "/snapshot?" + new Date().getTime(); // Añadir timestamp para evitar cache
                        emotionText.innerText = "Emoción: " + currentEmotion.toUpperCase();

                        // Dibujar la cara en el canvas con la emoción detectada (no hablando aún)
                        drawFace(currentEmotion, currentEmotion, 0);

                        // Iniciar la secuencia de audio y video
                        console.log("JS: Triggering audio based on detection.");
                        triggerAudio(currentEmotion); // Esta función llamará a triggerVideo al terminar el audio.


                    } else if (!data.detected) { // Si la detección en el servidor NO está completa
                         currentEmotion = "neutral"; // O puedes mantener la última emoción detectada si prefieres
                         // Solo restaurar la UI al feed de video si no estamos mostrando ya un video grande
                         if (videoContainer.style.display !== "flex") {
                             console.log("JS: Detection not complete, restoring main UI to video feed.");
                             document.getElementById('main-container').style.display = "flex";
                             videoContainer.style.display = "none";
                             videoFeed.style.display = "block"; // Mostrar el video feed
                             snapshotContainer.style.display = "none"; // Ocultar el snapshot
                             emotionText.innerText = ""; // Limpiar el texto de la emoción

                             // Dibujar la cara en estado neutral (no hablando)
                             // La función animateFace ya lo hará si isAudioPlaying es false
                         }
                    }
                    // Si data.detected es true pero isAudioPlaying o interactionVideo.paused es false,
                    // significa que la detección se completó pero ya estamos en medio de una interacción (audio/video).
                    // En este caso, simplemente ignoramos la nueva detección hasta que la interacción actual termine.
                } else {
                     // Estamos procesando un video forzado, ignorar completamente la lógica de detección normal
                     console.log("JS: Processing forced video, skipping normal detection logic.");
                }

            })
            .catch(err => {
                console.error("JS: Error polling detection status:", err);
                currentEmotion = "neutral";
                 // Si no estamos mostrando el video grande, mostrar error en la UI principal
                 if (videoContainer.style.display !== "flex") {
                     document.getElementById('main-container').style.display = "flex";
                     videoContainer.style.display = "none";
                     videoFeed.style.display = "block"; // Mostrar video feed
                     snapshotContainer.style.display = "none"; // Ocultar snapshot
                     emotionText.innerText = "Error de comunicación..."; // Indicador de problema
                     // La animación de la cara seguirá corriendo y dibujará neutral
                 }
            });
    }

    function triggerAudio(emotion) {
        // Asegurarse de que no se disparen múltiples audios
        if (isAudioPlaying) {
             console.log("JS: Audio already playing, skipping new audio trigger.");
             return;
        }

        // Mapear emociones a carpetas, con fallback a neutral si es necesario
        const audioEmotion = emotion === "disgust" || emotion === "no_face" || !emotion ? "neutral" : emotion;
        console.log(`JS: Attempting to fetch audio for emotion: ${audioEmotion}`);

        fetch(`/get_random_audio?emotion=${audioEmotion}`)
            .then(res => {
                if (!res.ok) {
                    console.error(`JS: HTTP error fetching audio: ${res.status}`);
                     // Si falla obtener audio, intentar directamente el video (si no hay video forzado)
                    if (!currentForcedVideoProcessed) {
                        console.log("JS: Failed to get audio, triggering video directly.");
                        triggerVideo();
                    } else {
                         console.log("JS: Failed to get audio, but forced video active, skipping video trigger.");
                         restartInteraction(); // Opcional: reiniciar si falla el audio en medio de una interacción
                    }
                    throw new Error(`HTTP error! status: ${res.status}`); // Propagar el error
                }
                return res.json();
            })
            .then(data => {
                if (data.audio_url) {
                    console.log("JS: Audio URL received:", data.audio_url);
                    // Reproducir audio. La promesa se resuelve cuando termina.
                    playAudio(data.audio_url)
                        .then(() => {
                            // Una vez que el audio termina, disparar la reproducción de video,
                            // PERO solo si no se ha activado un video forzado mientras tanto.
                            if (!currentForcedVideoProcessed) {
                                console.log("JS: Audio finished, triggering random video.");
                                triggerVideo(); // Disparar video aleatorio
                            } else {
                                console.log("JS: Audio finished, but forced video active, skipping triggerVideo.");
                            }
                        })
                        .catch(err => {
                             // Si hay un error en playAudio (ej: no se pudo reproducir), también intentar video
                             console.error("JS: Error playAudio promise:", err);
                             if (!currentForcedVideoProcessed) {
                                console.log("JS: Audio failed during playback, triggering video directly.");
                                triggerVideo();
                            } else {
                                 console.log("JS: Audio failed during playback, but forced video active, skipping video trigger.");
                                 restartInteraction(); // Opcional: reiniciar si falla el audio
                            }
                        });
                } else {
                    console.error("JS: No audio_url received for emotion:", audioEmotion, data);
                     // Si no se recibe URL de audio, intentar directamente el video (si no hay video forzado)
                    if (!currentForcedVideoProcessed) {
                         console.log("JS: No audio URL, triggering video directly.");
                        triggerVideo();
                    } else {
                        console.log("JS: No audio URL, but forced video active, skipping video trigger.");
                        restartInteraction(); // Opcional: reiniciar
                    }
                }
            })
            .catch(err => {
                console.error("JS: Error fetching audio URL:", err);
                 // Si falla la llamada fetch, intentar directamente el video (si no hay video forzado)
                if (!currentForcedVideoProcessed) {
                     console.log("JS: Fetch audio failed, triggering video directly.");
                    triggerVideo();
                } else {
                     console.log("JS: Fetch audio failed, but forced video active, skipping video trigger.");
                     restartInteraction(); // Opcional: reiniciar
                }
            });
    }

    function triggerVideo() {
        // Solo disparar video aleatorio si no hay un video forzado en curso
        if (currentForcedVideoProcessed) {
            console.log("JS: Forced video is active, NOT triggering random video.");
            return;
        }
        console.log("JS: Triggering RANDOM video.");

        // Ocultar interfaz principal y mostrar contenedor de video grande
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
         videoFeed.style.display = "none"; // Asegurarse de que el video feed esté oculto
         snapshotContainer.style.display = "none"; // Ocultar snapshot

        fetch('/get_random_video').then(res => {
            if (!res.ok) {
                console.error(`JS: HTTP error fetching random video: ${res.status}`);
                 console.log("JS: Failed to get random video, restarting interaction.");
                 restartInteraction(); // Reiniciar si falla
                 throw new Error(`HTTP error! status: ${res.status}`); // Propagar el error
            }
            return res.json();
        })
            .then(data => {
                if (data.video_url) {
                    console.log("JS: Random Video URL received:", data.video_url);
                    interactionVideo.src = data.video_url;

                    // Manejar fin del video y errores
                    interactionVideo.onended = () => {
                        console.log("JS: Random Video ended.");
                        restartInteraction(); // Reiniciar al finalizar
                    };
                    interactionVideo.onerror = (e) => {
                        console.error("JS: ERROR Random Video playback:", e);
                        restartInteraction(); // Reiniciar si hay error en reproducción
                    };

                    // Intentar reproducir. El catch maneja errores al iniciar play().
                    interactionVideo.play().catch(e => {
                        console.error("JS: Error starting random video playback:", e);
                        restartInteraction(); // Reiniciar si falla al iniciar
                    });

                } else {
                    console.error("JS: No random video file found or URL received.");
                    restartInteraction(); // Reiniciar si no hay URL
                }
            })
            .catch(err => {
                console.error("JS: Error fetching random video URL:", err);
                restartInteraction(); // Reiniciar si falla el fetch
            });
    }

    function playSpecificVideo(videoUrl) {
        console.log(`JS: Playing SPECIFIC video: ${videoUrl}`);

        // Ocultar interfaz principal y mostrar contenedor de video grande
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
        videoFeed.style.display = "none"; // Asegurarse de que el video feed esté oculto
        snapshotContainer.style.display = "none"; // Ocultar snapshot


        interactionVideo.src = videoUrl;

        // Manejar fin del video y errores para video forzado
        interactionVideo.onended = () => {
            console.log("JS: Specific Video ended.");
            currentForcedVideoProcessed = null; // Resetear flag de video forzado
            restartInteraction(); // Reiniciar al finalizar
        };
        interactionVideo.onerror = (e) => {
            console.error("JS: ERROR Specific Video playback:", e);
            currentForcedVideoProcessed = null; // Resetear flag de video forzado en caso de error
            restartInteraction(); // Reiniciar si hay error en reproducción
        };

        // Intentar reproducir. El catch maneja errores al iniciar play().
        interactionVideo.play().catch(e => {
            console.error("JS: Error starting specific video playback:", e);
            currentForcedVideoProcessed = null; // Resetear flag si falla al iniciar
            restartInteraction(); // Reiniciar si falla al iniciar
        });
    }


    function restartInteraction() {
        console.log("JS: RESTARTING interaction sequence - FORCING RELOAD.");

        // Limpiar el intervalo de polling para evitar llamadas duplicadas
        if (pollInterval) {
             clearInterval(pollInterval);
             pollInterval = null;
        }

        isAudioPlaying = false;
        isAnalyserReady = false; // Asegurarse de resetear el analizador


        // Detener y limpiar el video si está reproduciéndose
        if (interactionVideo) {
             interactionVideo.pause();
             interactionVideo.removeAttribute('src'); // Limpiar la fuente
             interactionVideo.load(); // Cargar para aplicar el cambio de fuente
             // Remover listeners para evitar que se disparen múltiples reinicios
             interactionVideo.onended = null;
             interactionVideo.onerror = null;
        }

        currentForcedVideoProcessed = null; // Resetear flag de video forzado

        // Cerrar y limpiar el contexto de audio si está activo
        if (audioContext && audioContext.state !== 'closed') {
            audioContext.close().then(() => {
                 console.log("JS: AudioContext closed.");
                 audioContext = null;
                 audioAnalyser = null;
                 audioDataArray = null;
                 // Ahora que todo está limpio, recargar la página para un reinicio completo.
                 // Esto asegura que Flask también reinicie su estado.
                 window.location.reload();
            }).catch(e => {
                 console.error("JS: Error closing AudioContext:", e);
                 audioContext = null;
                 audioAnalyser = null;
                 audioDataArray = null;
                 // Aunque hubo error al cerrar, intentar recargar de todas formas
                 window.location.reload();
            });
        } else {
             // Si no hay AudioContext activo, recargar directamente
             window.location.reload();
        }
        // Nota: la recarga de la página detendrá todos los hilos de JS y AudioContext automáticamente,
        // pero limpiar manualmente es una buena práctica antes de la recarga.
    }


    // --- Inicialización ---
    console.log("JS: Document loaded. Initializing.");
    // Iniciar la animación de la cara inmediatamente
    animateFace(); // Esto ahora dibujará una cara neutral si no hay audio sonando

    // Iniciar el polling para el estado de detección
    if (pollInterval) clearInterval(pollInterval); // Limpiar por si acaso
    pollInterval = setInterval(pollDetectionStatus, 500); // Polling cada 500ms
    console.log("JS: Initial polling started.");

    // Configurar listeners para el video de interacción solo una vez al cargar el DOM
     if (interactionVideo) {
         // Inicialmente ocultar el contenedor de video grande
         videoContainer.style.display = "none";
     } else {
         console.error("JS: interactionVideo element not found!");
     }

     // Asegurarse de que el main-container esté visible al inicio
     document.getElementById('main-container').style.display = "flex";

     // Puedes agregar un listener para el botón de skip/restart si lo tienes en index.html
     // (Aunque en tu descripción mencionaste que está en la interfaz del puerto 5001/5002,
     // si lo añades a esta interfaz, necesitarías un botón y un listener aquí)
      const skipButton = document.getElementById('button-skip-video-main'); // Asumiendo un ID si lo añades
      if (skipButton) {
          skipButton.addEventListener('click', restartInteraction);
      }

});