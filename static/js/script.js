document.addEventListener("DOMContentLoaded", function() {
    const videoFeed = document.getElementById('videoFeed');
    const snapshotContainer = document.getElementById('snapshot-container');
    const snapshotImg = document.getElementById('snapshot');
    const emotionText = document.getElementById('emotionText');
    const faceCanvas = document.getElementById('faceCanvas');
    const videoContainer = document.getElementById('video-container'); // Contenedor del video de interacción
    const interactionVideo = document.getElementById('interactionVideo'); // Elemento video de interacción
    const ctx = faceCanvas.getContext('2d');
  
    let currentEmotion = "neutral"; 
    let isAudioPlaying = false;
    let pollInterval; // Declarar aquí para que sea accesible globalmente en este script

    // --- Para video forzado ---
    let currentForcedVideoProcessed = null; // Para evitar reprocesar el mismo video forzado múltiples veces
  
    let audioContext = null; 
    let audioAnalyser = null;
    let audioDataArray = null;
  
    function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
        const cw = faceCanvas.width;
        const ch = faceCanvas.height;
        const faceCenterX = cw / 2;
        const faceCenterY = ch / 2; 
        const eyeOffsetY = ch * -0.15; 
        const eyeSeparation = cw * 0.3; 
        const baseEyeWidth = cw * 0.1;   
        const baseEyeHeight = ch * 0.1;  
        const eyeHeightChangeFactor = baseEyeHeight * 0.4; 
        const mouthOffsetY = ch * 0.15; 
        const baseMouthRadiusX = cw * 0.18; 
        const baseMouthRadiusY = ch * 0.05; 
        const mouthOpenFactorY = ch * 0.1;  
        const mouthWidenFactorX = cw * 0.05; 
        const t = Date.now() / 1000; 
        const floatOffset = 5 * Math.sin(t * 0.8); 
        ctx.clearRect(0, 0, cw, ch);
  
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
  
        const mouthCenterX = faceCenterX;
        const mouthCenterY = faceCenterY + mouthOffsetY + floatOffset;
        let adjustedMouthRadiusY = baseMouthRadiusY;
        let adjustedMouthRadiusX = baseMouthRadiusX;
        let startAngle = 0;
        let endAngle = Math.PI; 
        let drawStroke = false;
        let drawFill = true;
        ctx.fillStyle = "red";
        ctx.strokeStyle = "black";
        ctx.lineWidth = Math.max(2, cw * 0.005);
  
        if (mouthState === "talking") {
            const minTalkRadiusY = baseMouthRadiusY * 0.1; 
            adjustedMouthRadiusY = minTalkRadiusY + (amplitude * (mouthOpenFactorY * 0.8)); 
            adjustedMouthRadiusX = baseMouthRadiusX + (amplitude * mouthWidenFactorX * 0.5); 
            adjustedMouthRadiusY = Math.max(minTalkRadiusY, adjustedMouthRadiusY);
            adjustedMouthRadiusY = Math.min(baseMouthRadiusY * 2.0, adjustedMouthRadiusY); 
            adjustedMouthRadiusX = Math.max(baseMouthRadiusX * 0.8, adjustedMouthRadiusX);
            startAngle = 0;         
            endAngle = Math.PI * 2;
            drawFill = true;        
            drawStroke = true;       
            ctx.fillStyle = "black"; 
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
             drawStroke = false; 
        } else if (emotion === "angry") {
             startAngle = 0;
             endAngle = Math.PI;
             adjustedMouthRadiusX = baseMouthRadiusX * 1.1;
             adjustedMouthRadiusY = baseMouthRadiusY * 0.3;
             drawStroke = true;
             drawFill = false;
             ctx.strokeStyle = "darkred";
             ctx.lineWidth = Math.max(4, cw * 0.015);
        } else { // Neutral
             startAngle = 0;
             endAngle = Math.PI;
             adjustedMouthRadiusY = baseMouthRadiusY * 0.2; 
             adjustedMouthRadiusX = baseMouthRadiusX;
             drawStroke = true;
             drawFill = false;
             ctx.strokeStyle = "black";
             ctx.lineWidth = Math.max(3, cw * 0.01);
        }
  
        ctx.beginPath();
        ctx.ellipse(mouthCenterX, mouthCenterY, adjustedMouthRadiusX, adjustedMouthRadiusY, 0, startAngle, endAngle, (emotion === 'happy')); 
        if (drawFill) ctx.fill();
        if (drawStroke || (drawFill && mouthState !== 'talking' && emotion !== 'surprise')) {
             if(drawStroke && !drawFill) { 
                  ctx.stroke();
             } else { 
                 ctx.strokeStyle = "black";
                 ctx.lineWidth = 2;
                 ctx.stroke();
             }
        }
        ctx.closePath();
    } 
  
    function animateFace() {
        let mouthState = "neutral"; 
        let mouthAmplitude = 0;     
        const useAudioContext = true; 
  
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
        requestAnimationFrame(animateFace); 
    }
  
    function setupAudioAnalyser(audioElement) {
        if (!audioContext || audioContext.state === 'closed') {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioContext.state === 'suspended') {
            audioContext.resume().catch(e => console.error("Error reanudando AudioContext:", e));
        }
        if (audioContext.state === 'running') {
            try {
                const track = audioContext.createMediaElementSource(audioElement); 
                audioAnalyser = audioContext.createAnalyser();
                audioAnalyser.fftSize = 256;
                const bufferLength = audioAnalyser.frequencyBinCount;
                audioDataArray = new Uint8Array(bufferLength);
                track.connect(audioAnalyser);
                audioAnalyser.connect(audioContext.destination);
                // console.log("Audio Analyser configurado."); // Comentado
            } catch (e) {
                 console.error("Error configurando Audio Analyser:", e);
                 audioAnalyser = null;
                 audioDataArray = null;
            }
        } else {
            // console.warn("AudioContext no está activo. No se puede configurar Analyser."); // Comentado
            audioAnalyser = null;
            audioDataArray = null;
        }
    }
  
    function playAudio(url) {
        // console.log("Intentando reproducir audio:", url); // Comentado
        return new Promise((resolve, reject) => {
            const audio = new Audio(url);
            // audio.onloadedmetadata = () => console.log(`>>> Metadatos Audio cargados. Duración: ${audio.duration}s`); // Comentado
            audio.onplay = () => {
                // console.log("Audio onplay event."); // Comentado
                setupAudioAnalyser(audio); 
                isAudioPlaying = true;
            };
            audio.onerror = (e) => {
                console.error(">>> ERROR en elemento Audio:", e);
                isAudioPlaying = false;
                audioAnalyser = null; audioDataArray = null;
                reject(e); 
            };
            audio.onended = () => {
                // console.log("Audio onended event."); // Comentado
                isAudioPlaying = false;
                audioAnalyser = null; audioDataArray = null;
                resolve(); 
            };
            audio.play().then(() => {
                // console.log("Comando audio.play() ejecutado para:", url); // Comentado
            }).catch(e => {
                console.error("Error al iniciar audio automáticamente:", e);
                isAudioPlaying = false;
                if (audioContext && audioContext.state === 'suspended') {
                    // console.log("Intentando reanudar AudioContext..."); // Comentado
                    audioContext.resume().then(() => audio.play())
                    .catch(e2 => { console.error("Error en reintento de play:", e2); reject(e); });
                } else {
                    reject(e); 
                }
            });
        });
    }
  
    function pollDetectionStatus() {
        // console.log("Polling detection status..."); // Comentado para reducir logs
        fetch('/detection_status')
            .then(res => {
                if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
                return res.json();
            })
            .then(data => {
                // console.log("Poll data received:", data); // Comentado para logs
                if (data.forced_video && data.forced_video !== currentForcedVideoProcessed) {
                    if(pollInterval) clearInterval(pollInterval); 
                    currentForcedVideoProcessed = data.forced_video; 
                    console.log("FORCED VIDEO received:", data.forced_video);
                    
                    document.getElementById('main-container').style.display = "none";
                    videoContainer.style.display = "flex"; 
                    
                    const videoUrl = `/static/video/${data.forced_video}`;
                    playSpecificVideo(videoUrl);

                } else if (data.detected && !currentForcedVideoProcessed) { 
                    if(pollInterval) clearInterval(pollInterval);
                    currentEmotion = data.emotion;
                    console.log("DETECTION complete. Emotion:", currentEmotion);
                    videoFeed.style.display = "none";
                    snapshotContainer.style.display = "block";
                    snapshotImg.src = "/snapshot?" + new Date().getTime();
                    emotionText.innerText = "Emoción Detectada: " + currentEmotion.toUpperCase();
                    drawFace(currentEmotion, currentEmotion, 0);
                    triggerAudio(currentEmotion); 
                } else if (!data.detected && !currentForcedVideoProcessed) {
                     currentEmotion = "neutral";
                     // Mantener el polling activo si no hay detección y no hay video forzado
                     // console.log("No detection, no forced video. Emotion set to neutral."); // Comentado
                     // Asegurarse que el feed de video esté visible si no lo está
                     if (videoFeed.style.display === "none" && snapshotContainer.style.display === "none" && videoContainer.style.display === "none") {
                        document.getElementById('main-container').style.display = "flex";
                        videoFeed.style.display = "block";
                     }
                }
            })
            .catch(err => {
                console.error("Error polling detection status:", err);
                currentEmotion = "neutral";
                // No reiniciar el polling aquí directamente para evitar bucles si el servidor está caído.
                // Se reiniciará en restartInteraction o al cargar la página.
            });
    }
    
    function triggerAudio(emotion) {
        // console.log(`Triggering audio for emotion: ${emotion}`); // Comentado
        fetch(`/get_random_audio?emotion=${emotion}`)
            .then(res => {
                 if (!res.ok) { throw new Error(`HTTP error! status: ${res.status}, message: ${res.statusText}`); }
                 return res.json();
            })
            .then(data => {
                if (data.audio_url) {
                    // console.log(`Audio URL received: ${data.audio_url}`); // Comentado
                    playAudio(data.audio_url)
                        .then(() => {
                            // console.log("Audio playback finished."); // Comentado
                            if (!currentForcedVideoProcessed) { // Solo si no hay un video forzado pendiente
                                triggerVideo(); // Reproducir video aleatorio después del audio
                            }
                        })
                        .catch(err => {
                             console.error("Error en promesa playAudio:", err);
                             if (!currentForcedVideoProcessed) triggerVideo(); 
                         });
                } else {
                    console.error("No audio file found for emotion:", emotion, "Response:", data);
                    if (!currentForcedVideoProcessed) triggerVideo();
                }
            })
            .catch(err => {
                 console.error("Error fetching audio URL:", err);
                 if (!currentForcedVideoProcessed) triggerVideo();
             });
    }
  
    function triggerVideo() { // Esta función reproduce un video ALEATORIO
        // console.log("Triggering RANDOM video playback."); // Comentado
        if (currentForcedVideoProcessed) {
            // console.log("Skipping random video because a forced video was processed or is active."); // Comentado
            return;
        }
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
  
        fetch('/get_random_video')
             .then(res => {
                 if (!res.ok) { throw new Error(`HTTP error! status: ${res.status}, message: ${res.statusText}`); }
                 return res.json();
             })
            .then(data => {
                if (data.video_url) {
                    // console.log(`Random Video URL received: ${data.video_url}`); // Comentado
                    interactionVideo.src = data.video_url;
                    // interactionVideo.onloadedmetadata = () => console.log(`>>> Random Video metadata. Duration: ${interactionVideo.duration}s`); // Comentado
                    interactionVideo.onerror = (e) => { console.error(">>> ERROR en Random Video:", e); restartInteraction(); };
                    interactionVideo.onended = () => { /*console.log("Random Video onended.");*/ restartInteraction(); };
                    interactionVideo.play().catch(e => { console.error("Error starting random video:", e); restartInteraction(); });
                } else {
                    console.error("No random video file found. Response:", data);
                    restartInteraction();
                }
            })
            .catch(err => {
                 console.error("Error fetching random video URL:", err);
                 restartInteraction();
             });
    }

    function playSpecificVideo(videoUrl) {
        console.log(`Attempting to play SPECIFIC video: ${videoUrl}`);
        // Asegurarse que el contenedor de video esté visible y el principal oculto.
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
        
        interactionVideo.src = videoUrl;
        // interactionVideo.onloadedmetadata = () => console.log(`>>> Specific Video metadata. Duration: ${interactionVideo.duration}s`); // Comentado
        interactionVideo.onerror = (e) => {
            console.error(">>> ERROR in specific Video element:", e);
            restartInteraction(); 
        };
        interactionVideo.onended = () => {
            // console.log("Specific Video onended."); // Comentado
            restartInteraction(); 
        };
        interactionVideo.play().then(() => {
            // console.log("Specific video.play() command executed."); // Comentado
        }).catch(e => {
            console.error("Error starting specific video playback:", e);
            restartInteraction();
        });
    }
  
    function restartInteraction() {
        console.log("RESTARTING interaction sequence...");
        isAudioPlaying = false;
        audioAnalyser = null;
        audioDataArray = null;
        currentForcedVideoProcessed = null; // Limpiar el video forzado procesado
        currentEmotion = "neutral"; // Resetear emoción
        drawFace("neutral", "neutral", 0); // Dibujar cara neutral inmediatamente

        // Detener y limpiar el elemento de video de interacción
        interactionVideo.pause();
        interactionVideo.removeAttribute('src'); // Eliminar la fuente para liberar recursos
        interactionVideo.load();


        // Llamar al endpoint /restart del servidor para resetear su estado
        fetch('/restart')
            .then(res => res.json())
            .then(data => {
                console.log("Restart signal to server response:", data);
                // No recargar la página, manejar el flujo con JS
            })
            .catch(err => {
                console.error("Error sending restart signal to server:", err);
            })
            .finally(() => {
                 // Restaurar la vista de detección
                document.getElementById('main-container').style.display = "flex";
                videoContainer.style.display = "none";
                videoFeed.style.display = "block"; // Mostrar el feed de video de nuevo
                snapshotContainer.style.display = "none"; // Ocultar el snapshot
                emotionText.innerText = ""; // Limpiar texto de emoción

                // Reiniciar el polling
                if (pollInterval) clearInterval(pollInterval);
                pollInterval = setInterval(pollDetectionStatus, 1000); // Reanudar polling
                console.log("Polling restarted after interaction reset.");
            });
    }
  
    // --- Inicialización ---
    console.log("Document loaded. Initializing.");
    drawFace("neutral", "neutral", 0); 
    animateFace(); 
    pollInterval = setInterval(pollDetectionStatus, 1000); // Iniciar polling
  
  });