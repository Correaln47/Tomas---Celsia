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
    let audioDataArray = null;

    // --- Funciones de dibujo y audio (sin cambios mayores, usar versiones previas que funcionaban bien) ---
     function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
         const cw = faceCanvas.width; const ch = faceCanvas.height; const faceCenterX = cw / 2; const faceCenterY = ch / 2;
         const eyeOffsetY = ch * -0.15; const eyeSeparation = cw * 0.3; const baseEyeWidth = cw * 0.1; const baseEyeHeight = ch * 0.1;
         const eyeHeightChangeFactor = baseEyeHeight * 0.4; const mouthOffsetY = ch * 0.15; const baseMouthRadiusX = cw * 0.18;
         const baseMouthRadiusY = ch * 0.05; const mouthOpenFactorY = ch * 0.1; const mouthWidenFactorX = cw * 0.05;
         const t = Date.now() / 1000; const floatOffset = 5 * Math.sin(t * 0.8); ctx.clearRect(0, 0, cw, ch); ctx.fillStyle = "black";
         const leftEyeX = faceCenterX - eyeSeparation / 2 - baseEyeWidth / 2; const rightEyeX = faceCenterX + eyeSeparation / 2 - baseEyeWidth / 2;
         const eyeY = faceCenterY + eyeOffsetY + floatOffset - baseEyeHeight / 2; let adjustedEyeHeight = baseEyeHeight;
         if (mouthState === "talking") { adjustedEyeHeight = baseEyeHeight - (amplitude * eyeHeightChangeFactor); adjustedEyeHeight = Math.max(adjustedEyeHeight, baseEyeHeight * 0.6);
         } else if (emotion === "surprise") { adjustedEyeHeight = baseEyeHeight * 1.2; }
         ctx.fillRect(leftEyeX, eyeY, baseEyeWidth, adjustedEyeHeight); ctx.fillRect(rightEyeX, eyeY, baseEyeWidth, adjustedEyeHeight);
         const mouthCenterX = faceCenterX; const mouthCenterY = faceCenterY + mouthOffsetY + floatOffset;
         let adjustedMouthRadiusY = baseMouthRadiusY; let adjustedMouthRadiusX = baseMouthRadiusX; let startAngle = 0; let endAngle = Math.PI;
         let drawStroke = false; let drawFill = true; ctx.fillStyle = "red"; ctx.strokeStyle = "black"; ctx.lineWidth = Math.max(2, cw * 0.005);
         if (mouthState === "talking") {
             const minTalkRadiusY = baseMouthRadiusY * 0.1; adjustedMouthRadiusY = minTalkRadiusY + (amplitude * (mouthOpenFactorY * 0.8));
             adjustedMouthRadiusX = baseMouthRadiusX + (amplitude * mouthWidenFactorX * 0.5); adjustedMouthRadiusY = Math.max(minTalkRadiusY, adjustedMouthRadiusY);
             adjustedMouthRadiusY = Math.min(baseMouthRadiusY * 2.0, adjustedMouthRadiusY); adjustedMouthRadiusX = Math.max(baseMouthRadiusX * 0.8, adjustedMouthRadiusX);
             startAngle = 0; endAngle = Math.PI * 2; drawFill = true; drawStroke = true; ctx.fillStyle = "black";
         } else if (emotion === "happy") { startAngle = Math.PI; endAngle = 0; adjustedMouthRadiusX = baseMouthRadiusX * 1.1; adjustedMouthRadiusY = baseMouthRadiusY * 1.5; drawStroke = true; drawFill = false; ctx.strokeStyle = "red"; ctx.lineWidth = Math.max(3, cw * 0.01);
         } else if (emotion === "sad") { startAngle = 0; endAngle = Math.PI; adjustedMouthRadiusX = baseMouthRadiusX * 0.9; adjustedMouthRadiusY = baseMouthRadiusY * 1.3; drawStroke = true; drawFill = false; ctx.strokeStyle = "blue"; ctx.lineWidth = Math.max(3, cw * 0.01);
         } else if (emotion === "surprise") { startAngle = 0; endAngle = Math.PI * 2; adjustedMouthRadiusX = baseMouthRadiusX * 0.8; adjustedMouthRadiusY = baseMouthRadiusY * 2.5; ctx.fillStyle = "black"; drawFill = true; drawStroke = false;
         } else if (emotion === "angry") { startAngle = 0; endAngle = Math.PI; adjustedMouthRadiusX = baseMouthRadiusX * 1.1; adjustedMouthRadiusY = baseMouthRadiusY * 0.3; drawStroke = true; drawFill = false; ctx.strokeStyle = "darkred"; ctx.lineWidth = Math.max(4, cw * 0.015);
         } else { startAngle = 0; endAngle = Math.PI; adjustedMouthRadiusY = baseMouthRadiusY * 0.2; adjustedMouthRadiusX = baseMouthRadiusX; drawStroke = true; drawFill = false; ctx.strokeStyle = "black"; ctx.lineWidth = Math.max(3, cw * 0.01); }
         ctx.beginPath(); ctx.ellipse(mouthCenterX, mouthCenterY, adjustedMouthRadiusX, adjustedMouthRadiusY, 0, startAngle, endAngle, (emotion === 'happy'));
         if (drawFill) ctx.fill();
         if (drawStroke || (drawFill && mouthState !== 'talking' && emotion !== 'surprise')) {
              if(drawStroke && !drawFill) { ctx.stroke(); } else { ctx.strokeStyle = "black"; ctx.lineWidth = 2; ctx.stroke(); }
         } ctx.closePath();
     }
     function animateFace() { /* ... (igual que antes) ... */ requestAnimationFrame(animateFace); }
     function setupAudioAnalyser(audioElement) { /* ... (igual que antes) ... */ }
     function playAudio(url) { /* ... (igual que antes, devuelve Promise) ... */
        return new Promise((resolve, reject) => {
            const audio = new Audio(url);
            setupAudioAnalyser(audio); // Configura el analizador para visualizar si estás usando esa parte
            audio.onplay = () => {
                 console.log("JS: Audio started playing:", url);
                 isAudioPlaying = true;
            };
            audio.onended = () => {
                 console.log("JS: Audio ended:", url);
                 isAudioPlaying = false;
                 resolve(); // Resuelve la promesa cuando el audio termina
            };
            audio.onerror = (e) => {
                 console.error("JS: Audio error:", url, e);
                 isAudioPlaying = false;
                 reject(e); // Rechaza la promesa si hay un error
            };
            audio.play().catch(e => {
                 console.error("JS: Error starting audio playback:", url, e);
                 isAudioPlaying = false;
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
                    if (videoContainer.style.display !== "flex") {
                         document.getElementById('main-container').style.display = "flex";
                         videoContainer.style.display = "none";
                         videoFeed.style.display = "block";
                         snapshotContainer.style.display = "none";
                         emotionText.innerText = "Error de conexión..."; // Indicador de problema
                         drawFace("neutral", "neutral", 0);
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
                // Si el flag restart_requested es true Y actualmente se está reproduciendo un video
                if (data.restart_requested && interactionVideo && interactionVideo.paused === false) {
                     console.log("JS: Restart requested from server while video playing. Stopping video and restarting interaction.");
                     restartInteraction(); // Detiene el video actual y reinicia la página
                     return; // Ya hemos manejado el reinicio
                }


                // --- Lógica para manejar video forzado (prioridad alta) ---
                if (data.forced_video && data.forced_video !== currentForcedVideoProcessed) {
                    currentForcedVideoProcessed = data.forced_video;
                    console.log("JS: FORCED VIDEO received:", data.forced_video);

                    document.getElementById('main-container').style.display = "none";
                    videoContainer.style.display = "flex";

                    const videoUrl = `/static/video/${data.forced_video}`;
                    playSpecificVideo(videoUrl);
                    return; // Ya estamos manejando un video forzado
                }


                // --- Lógica para manejar detección de emoción (si no hay video forzado) ---
                if (!currentForcedVideoProcessed) {
                    if (data.detected) {
                        currentEmotion = data.emotion;
                        console.log("JS: DETECTION complete. Emotion:", currentEmotion);

                        videoFeed.style.display = "none";
                        snapshotContainer.style.display = "block";

                        snapshotImg.src = "/snapshot?" + new Date().getTime();
                        emotionText.innerText = "Emoción: " + currentEmotion.toUpperCase();

                        drawFace(currentEmotion, currentEmotion, 0);

                        if (!isAudioPlaying && interactionVideo.paused !== false) {
                            console.log("JS: Triggering audio based on detection.");
                            triggerAudio(currentEmotion);
                        } else {
                            console.log("JS: Audio/Video already playing or forced video pending, skipping triggerAudio/triggerVideo.");
                        }

                    } else { // Si la detección en el servidor NO está completa
                         currentEmotion = "neutral";
                         // Solo restaurar la UI al feed de video si no estamos mostrando ya un video grande
                         if (videoContainer.style.display !== "flex") {
                             console.log("JS: Detection not complete, restoring main UI to video feed.");
                             document.getElementById('main-container').style.display = "flex";
                             videoContainer.style.display = "none";
                             videoFeed.style.display = "block";
                             snapshotContainer.style.display = "none";
                             emotionText.innerText = "";
                             drawFace("neutral", "neutral", 0);
                         }
                    }
                } else {
                     console.log("JS: Processing forced video, skipping normal detection logic.");
                }

            })
            .catch(err => {
                console.error("JS: Error polling detection status:", err);
                currentEmotion = "neutral";
                 if (videoContainer.style.display !== "flex") { // Si no estamos mostrando el video grande
                     document.getElementById('main-container').style.display = "flex";
                     videoContainer.style.display = "none";
                     videoFeed.style.display = "block";
                     snapshotContainer.style.display = "none";
                     emotionText.innerText = "Error de comunicación..."; // Indicador de problema
                     drawFace("neutral", "neutral", 0);
                 }
            });
    }

    function triggerAudio(emotion) {
        const audioEmotion = emotion === "disgust" || emotion === "no_face" ? "neutral" : emotion;
        console.log(`JS: Attempting to fetch audio for emotion: ${audioEmotion}`);

        fetch(`/get_random_audio?emotion=${audioEmotion}`)
            .then(res => {
                if (!res.ok) {
                    console.error(`JS: HTTP error fetching audio: ${res.status}`);
                    if (!currentForcedVideoProcessed && interactionVideo.paused !== false) {
                        console.log("JS: Failed to get audio, triggering video directly.");
                        triggerVideo();
                    }
                    throw new Error(`HTTP error! status: ${res.status}`);
                }
                return res.json();
            })
            .then(data => {
                if (data.audio_url) {
                    console.log("JS: Audio URL received:", data.audio_url);
                    playAudio(data.audio_url)
                        .then(() => {
                            if (!currentForcedVideoProcessed && interactionVideo.paused !== false) {
                                console.log("JS: Audio finished, triggering random video.");
                                triggerVideo();
                            } else {
                                console.log("JS: Audio finished, but forced video active or another video started, skipping triggerVideo.");
                            }
                        })
                        .catch(err => {
                             console.error("JS: Error playAudio promise:", err);
                             if (!currentForcedVideoProcessed && interactionVideo.paused !== false) {
                                console.log("JS: Audio failed, triggering video directly.");
                                triggerVideo();
                            }
                        });
                } else {
                    console.error("JS: No audio_url received for emotion:", audioEmotion, data);
                    if (!currentForcedVideoProcessed && interactionVideo.paused !== false) {
                         console.log("JS: No audio URL, triggering video directly.");
                        triggerVideo();
                    }
                }
            })
            .catch(err => {
                console.error("JS: Error fetching audio URL:", err);
                if (!currentForcedVideoProcessed && interactionVideo.paused !== false) {
                     console.log("JS: Fetch audio failed, triggering video directly.");
                    triggerVideo();
                }
            });
    }

    function triggerVideo() {
        if (currentForcedVideoProcessed) {
            console.log("JS: Forced video is active, NOT triggering random video.");
            return;
        }
        console.log("JS: Triggering RANDOM video.");
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";

        fetch('/get_random_video').then(res => {
            if (!res.ok) {
                console.error(`JS: HTTP error fetching random video: ${res.status}`);
                 console.log("JS: Failed to get random video, restarting interaction.");
                 restartInteraction();
                 throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        })
            .then(data => {
                if (data.video_url) {
                    console.log("JS: Random Video URL received:", data.video_url);
                    interactionVideo.src = data.video_url;

                    interactionVideo.onended = () => {
                        console.log("JS: Random Video ended.");
                        restartInteraction();
                    };
                    interactionVideo.onerror = (e) => {
                        console.error("JS: ERROR Random Video playback:", e);
                        restartInteraction();
                    };

                    interactionVideo.play().catch(e => {
                        console.error("JS: Error starting random video playback:", e);
                        restartInteraction();
                    });

                } else {
                    console.error("JS: No random video file found or URL received.");
                    restartInteraction();
                }
            })
            .catch(err => {
                console.error("JS: Error fetching random video URL:", err);
                restartInteraction();
            });
    }

    function playSpecificVideo(videoUrl) {
        console.log(`JS: Playing SPECIFIC video: ${videoUrl}`);
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";

        interactionVideo.src = videoUrl;

        interactionVideo.onended = () => {
            console.log("JS: Specific Video ended.");
            currentForcedVideoProcessed = null;
            restartInteraction();
        };
        interactionVideo.onerror = (e) => {
            console.error("JS: ERROR Specific Video playback:", e);
            currentForcedVideoProcessed = null;
            restartInteraction();
        };

        interactionVideo.play().catch(e => {
            console.error("JS: Error starting specific video playback:", e);
            currentForcedVideoProcessed = null;
            restartInteraction();
        });
    }

    function restartInteraction() {
        console.log("JS: RESTARTING interaction sequence - FORCING RELOAD.");

        if (pollInterval) {
             clearInterval(pollInterval);
             pollInterval = null;
        }

        isAudioPlaying = false;

        if (interactionVideo) {
             interactionVideo.pause();
             interactionVideo.removeAttribute('src');
             interactionVideo.load();
             interactionVideo.onended = null;
             interactionVideo.onerror = null;
        }

        currentForcedVideoProcessed = null;

        if (audioContext && audioContext.state !== 'closed') {
             audioContext = null;
        }
        audioAnalyser = null;
        audioDataArray = null;

        window.location.reload();
    }

    // --- Inicialización ---
    console.log("JS: Document loaded. Initializing.");
    drawFace("neutral", "neutral", 0);
    animateFace();

    // Iniciar el polling para el estado de detección
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(pollDetectionStatus, 500); // Polling cada 500ms
    console.log("JS: Initial polling started.");

    // Configurar listeners para el video de interacción solo una vez
     if (interactionVideo) {
         // Inicialmente ocultar el contenedor de video
         videoContainer.style.display = "none";
     } else {
         console.error("JS: interactionVideo element not found!");
     }

     // Asegurarse de que el main-container esté visible al inicio
     document.getElementById('main-container').style.display = "flex";

});