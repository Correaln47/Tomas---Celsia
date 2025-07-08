document.addEventListener("DOMContentLoaded", function() {
    // --- Selectores de Elementos del DOM ---
    const videoFeed = document.getElementById('videoFeed');
    const snapshotContainer = document.getElementById('snapshot-container');
    const snapshotImg = document.getElementById('snapshot');
    const emotionText = document.getElementById('emotionText');
    const faceCanvas = document.getElementById('faceCanvas');
    const videoContainer = document.getElementById('video-container');
    const interactionVideo = document.getElementById('interactionVideo');
    const ctx = faceCanvas.getContext('2d');
    // --- NUEVO: Elementos para el evento especial ---
    const specialOverlay = document.getElementById('specialOverlay');
    const specialAudio = document.getElementById('specialAudio');


    // --- Variables de Estado ---
    let currentEmotion = "neutral";
    let isAudioPlaying = false;
    let pollInterval;
    let currentForcedVideoProcessed = null;
    let audioContext = null;
    let audioAnalyser = null;
    let audioDataArray = null;
    let isAnalyserReady = false;
    // --- NUEVO: Flag de estado para el evento especial ---
    let isSpecialEventActive = false;


    // --- Funciones de Dibujo y Audio ---
    function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
        const cw = faceCanvas.width;
        const ch = faceCanvas.height;
        const faceCenterX = cw / 2;
        const faceCenterY = ch / 2;
        ctx.clearRect(0, 0, cw, ch);
        const t = Date.now() / 1000;
        const floatOffset = (ch * 0.01) * Math.sin(t * 0.8);
        const eyeOffsetY = ch * -0.2;
        const eyeSeparation = cw * 0.5;
        const baseEyeWidth = cw * 0.15;
        let baseEyeHeight = ch * 0.15;
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
        const mouthOffsetY = ch * 0.2;
        const baseMouthRadiusX = cw * 0.25;
        const baseMouthRadiusY = ch * 0.1;
        const mouthCenterX = faceCenterX;
        const mouthCenterY = faceCenterY + mouthOffsetY + floatOffset;
        let adjustedMouthRadiusX = baseMouthRadiusX;
        let adjustedMouthRadiusY = baseMouthRadiusY;
        let startAngle = 0;
        let endAngle = Math.PI;
        let drawStroke = false;
        let drawFill = false;
        ctx.beginPath();
        ctx.lineWidth = Math.max(5, cw * 0.015);
        if (mouthState === "talking") {
            adjustedMouthRadiusY = (baseMouthRadiusY * 0.1) + (amplitude * baseMouthRadiusY * 1.5);
            adjustedMouthRadiusX = baseMouthRadiusX + (amplitude * baseMouthRadiusX * 0.2);
            startAngle = 0;
            endAngle = Math.PI * 2;
            drawFill = true;
            ctx.fillStyle = "black";
        } else if (emotion === "happy") {
            startAngle = 0;
            endAngle = Math.PI;
            adjustedMouthRadiusY = baseMouthRadiusY;
            drawStroke = true;
            ctx.strokeStyle = "red";
        } else if (emotion === "sad") {
            startAngle = Math.PI;
            endAngle = 0;
            adjustedMouthRadiusY = baseMouthRadiusY;
            drawStroke = true;
            ctx.strokeStyle = "blue";
        } else if (emotion === "surprise") {
            startAngle = 0;
            endAngle = Math.PI * 2;
            adjustedMouthRadiusY = baseMouthRadiusY * 1.2;
            drawFill = true;
            ctx.fillStyle = "black";
        } else if (emotion === "angry") {
            startAngle = 0;
            endAngle = Math.PI;
            adjustedMouthRadiusY = baseMouthRadiusY * 0.2;
            drawStroke = true;
            ctx.strokeStyle = "darkred";
        } else {
            startAngle = 0;
            endAngle = Math.PI;
            adjustedMouthRadiusY = baseMouthRadiusY * 0.1;
            drawStroke = true;
            ctx.strokeStyle = "black";
        }
        ctx.ellipse(mouthCenterX, mouthCenterY, adjustedMouthRadiusX, adjustedMouthRadiusY, 0, startAngle, endAngle);
        if (drawFill) ctx.fill();
        if (drawStroke) ctx.stroke();
        ctx.closePath();
    }

    function setupAudioAnalyser(audioElement) {
        if (!audioContext) {
            audioContext = new(window.AudioContext || window.webkitAudioContext)();
        }
        if (audioContext.state === 'suspended') {
            audioContext.resume();
        }
        if (audioAnalyser) {
            audioAnalyser.disconnect();
        }
        try {
            const source = audioContext.createMediaElementSource(audioElement);
            audioAnalyser = audioContext.createAnalyser();
            audioAnalyser.fftSize = 256;
            audioDataArray = new Uint8Array(audioAnalyser.frequencyBinCount);
            source.connect(audioAnalyser);
            audioAnalyser.connect(audioContext.destination);
            isAnalyserReady = true;
        } catch (e) {
            console.error("JS: Error setting up audio analyser:", e);
            audioAnalyser = null;
            audioDataArray = null;
            isAnalyserReady = false;
        }
    }

    function getAverageAmplitude() {
        if (!isAnalyserReady || !audioDataArray) {
            return 0;
        }
        audioAnalyser.getByteFrequencyData(audioDataArray);
        const lowerHalf = audioDataArray.slice(0, audioDataArray.length / 2);
        const average = lowerHalf.reduce((sum, value) => sum + value, 0) / lowerHalf.length;
        const normalizedAmplitude = average / 255;
        return normalizedAmplitude;
    }

    function animateFace() {
        const amplitude = isAudioPlaying && isAnalyserReady ? getAverageAmplitude() : 0;
        const mouthState = isAudioPlaying ? "talking" : currentEmotion;
        // --- NUEVO: No dibujar la cara si el evento especial o el video grande están activos
        if (videoContainer.style.display !== "flex" && !isSpecialEventActive) {
            drawFace(currentEmotion, mouthState, amplitude);
        } else {
            ctx.clearRect(0, 0, faceCanvas.width, faceCanvas.height);
        }
        requestAnimationFrame(animateFace);
    }

    async function playAudio(url) {
        console.log("JS: Attempting to play audio:", url);
        return new Promise((resolve, reject) => {
            const audio = new Audio(url);
            setupAudioAnalyser(audio);
            audio.onplay = () => {
                console.log("JS: Audio started playing:", url);
                isAudioPlaying = true;
            };
            audio.onended = () => {
                console.log("JS: Audio ended:", url);
                isAudioPlaying = false;
                isAnalyserReady = false;
                resolve();
            };
            audio.onerror = (e) => {
                console.error("JS: Audio error:", url, e);
                isAudioPlaying = false;
                isAnalyserReady = false;
                reject(e);
            };
            audio.play().catch(e => {
                console.error("JS: Error starting audio playback:", url, e);
                isAudioPlaying = false;
                isAnalyserReady = false;
                reject(e);
            });
        });
    }


    // --- Lógica Principal de Interacción ---

    function pollDetectionStatus() {
        // --- NUEVO: Pausar el polling si el evento especial está activo ---
        if (isSpecialEventActive) {
            console.log("JS: Special event active, polling paused.");
            return;
        }

        fetch('/detection_status').then(res => {
            if (!res.ok) {
                console.error(`JS: HTTP error! status: ${res.status}`);
                currentEmotion = "neutral";
                if (videoContainer.style.display !== "flex") {
                    document.getElementById('main-container').style.display = "flex";
                    videoContainer.style.display = "none";
                    videoFeed.style.display = "block";
                    snapshotContainer.style.display = "none";
                    emotionText.innerText = "Error de conexión...";
                }
                return null;
            }
            return res.json();
        }).then(data => {
            if (data === null) {
                return;
            }
            if (data.restart_requested && interactionVideo && interactionVideo.paused === false) {
                console.log("JS: Restart requested from server while video playing. Stopping video and restarting interaction.");
                restartInteraction();
                return;
            }
            if (data.forced_video && data.forced_video !== currentForcedVideoProcessed) {
                console.log("JS: FORCED VIDEO received:", data.forced_video);
                currentForcedVideoProcessed = data.forced_video;
                document.getElementById('main-container').style.display = "none";
                videoContainer.style.display = "flex";
                videoFeed.style.display = "none";
                const videoUrl = `/static/video/${data.forced_video}`;
                playSpecificVideo(videoUrl);
                return;
            }
            if (!currentForcedVideoProcessed) {
                if (data.detected && !isAudioPlaying && interactionVideo.paused !== false) {
                    currentEmotion = data.emotion;
                    console.log("JS: DETECTION complete. Emotion:", currentEmotion);
                    document.getElementById('main-container').style.display = "flex";
                    videoContainer.style.display = "none";
                    videoFeed.style.display = "none";
                    snapshotContainer.style.display = "block";
                    snapshotImg.src = "/snapshot?" + new Date().getTime();
                    emotionText.innerText = "Emoción: " + currentEmotion.toUpperCase();
                    drawFace(currentEmotion, currentEmotion, 0);
                    console.log("JS: Triggering audio based on detection.");
                    triggerAudio(currentEmotion);
                } else if (!data.detected) {
                    currentEmotion = "neutral";
                    if (videoContainer.style.display !== "flex") {
                        console.log("JS: Detection not complete, restoring main UI to video feed.");
                        document.getElementById('main-container').style.display = "flex";
                        videoContainer.style.display = "none";
                        videoFeed.style.display = "block";
                        snapshotContainer.style.display = "none";
                        emotionText.innerText = "";
                    }
                }
            } else {
                console.log("JS: Processing forced video, skipping normal detection logic.");
            }
        }).catch(err => {
            console.error("JS: Error polling detection status:", err);
            currentEmotion = "neutral";
            if (videoContainer.style.display !== "flex") {
                document.getElementById('main-container').style.display = "flex";
                videoContainer.style.display = "none";
                videoFeed.style.display = "block";
                snapshotContainer.style.display = "none";
                emotionText.innerText = "Error de comunicación...";
            }
        });
    }

    function triggerAudio(emotion) {
        // --- NUEVO: No disparar audio si el evento especial está activo
        if (isSpecialEventActive) return;

        if (isAudioPlaying) {
            console.log("JS: Audio already playing, skipping new audio trigger.");
            return;
        }
        const audioEmotion = emotion === "disgust" || emotion === "no_face" || !emotion ? "neutral" : emotion;
        console.log(`JS: Attempting to fetch audio for emotion: ${audioEmotion}`);
        fetch(`/get_random_audio?emotion=${audioEmotion}`).then(res => {
            if (!res.ok) {
                console.error(`JS: HTTP error fetching audio: ${res.status}`);
                if (!currentForcedVideoProcessed) {
                    console.log("JS: Failed to get audio, triggering video directly.");
                    triggerVideo();
                } else {
                    console.log("JS: Failed to get audio, but forced video active, skipping video trigger.");
                    restartInteraction();
                }
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        }).then(data => {
            if (data.audio_url) {
                console.log("JS: Audio URL received:", data.audio_url);
                playAudio(data.audio_url).then(() => {
                    if (!currentForcedVideoProcessed) {
                        console.log("JS: Audio finished, triggering random video.");
                        triggerVideo();
                    } else {
                        console.log("JS: Audio finished, but forced video active, skipping triggerVideo.");
                    }
                }).catch(err => {
                    console.error("JS: Error playAudio promise:", err);
                    if (!currentForcedVideoProcessed) {
                        console.log("JS: Audio failed during playback, triggering video directly.");
                        triggerVideo();
                    } else {
                        console.log("JS: Audio failed during playback, but forced video active, skipping video trigger.");
                        restartInteraction();
                    }
                });
            } else {
                console.error("JS: No audio_url received for emotion:", audioEmotion, data);
                if (!currentForcedVideoProcessed) {
                    console.log("JS: No audio URL, triggering video directly.");
                    triggerVideo();
                } else {
                    console.log("JS: No audio URL, but forced video active, skipping video trigger.");
                    restartInteraction();
                }
            }
        }).catch(err => {
            console.error("JS: Error fetching audio URL:", err);
            if (!currentForcedVideoProcessed) {
                console.log("JS: Fetch audio failed, triggering video directly.");
                triggerVideo();
            } else {
                console.log("JS: Fetch audio failed, but forced video active, skipping video trigger.");
                restartInteraction();
            }
        });
    }

    function triggerVideo() {
        // --- NUEVO: No disparar video si el evento especial está activo
        if (isSpecialEventActive) return;

        if (currentForcedVideoProcessed) {
            console.log("JS: Forced video is active, NOT triggering random video.");
            return;
        }
        console.log("JS: Triggering RANDOM video.");
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
        videoFeed.style.display = "none";
        snapshotContainer.style.display = "none";
        fetch('/get_random_video').then(res => {
            if (!res.ok) {
                console.error(`JS: HTTP error fetching random video: ${res.status}`);
                console.log("JS: Failed to get random video, restarting interaction.");
                restartInteraction();
                throw new Error(`HTTP error! status: ${res.status}`);
            }
            return res.json();
        }).then(data => {
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
        }).catch(err => {
            console.error("JS: Error fetching random video URL:", err);
            restartInteraction();
        });
    }

    function playSpecificVideo(videoUrl) {
        console.log(`JS: Playing SPECIFIC video: ${videoUrl}`);
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
        videoFeed.style.display = "none";
        snapshotContainer.style.display = "none";
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
        isAnalyserReady = false;
        if (interactionVideo) {
            interactionVideo.pause();
            interactionVideo.removeAttribute('src');
            interactionVideo.load();
            interactionVideo.onended = null;
            interactionVideo.onerror = null;
        }
        currentForcedVideoProcessed = null;
        if (audioContext && audioContext.state !== 'closed') {
            audioContext.close().then(() => {
                console.log("JS: AudioContext closed.");
                audioContext = null;
                audioAnalyser = null;
                audioDataArray = null;
                window.location.reload();
            }).catch(e => {
                console.error("JS: Error closing AudioContext:", e);
                audioContext = null;
                audioAnalyser = null;
                audioDataArray = null;
                window.location.reload();
            });
        } else {
            window.location.reload();
        }
    }


    // --- NUEVO: Lógica completa para el Evento Especial Aleatorio ---
    function triggerSpecialEvent() {
        // No disparar si ya hay otra interacción importante en curso
        if (isAudioPlaying || (interactionVideo && !interactionVideo.paused) || currentForcedVideoProcessed) {
            console.log("JS: Main interaction is active, postponing special event.");
            // Reprogramar para un poco más tarde para no perder el evento
            setTimeout(setupNextTrigger, 30 * 1000); // Intenta de nuevo en 30s
            return;
        }

        console.log("JS: Activating special event...");
        isSpecialEventActive = true;

        // Ocultar solo la cara, no todo el 'main-container'
        faceCanvas.style.display = 'none';
        specialOverlay.style.display = 'block';

        // Reproducir el audio especial
        specialAudio.currentTime = 0;
        specialAudio.play().catch(error => console.error("Error al reproducir audio especial:", error));

        // Obtener la duración del audio para que el overlay dure lo mismo
        const audioDuration = specialAudio.duration;
        // Usar 5 segundos como fallback si la duración no está disponible
        const displayDuration = (audioDuration && isFinite(audioDuration)) ? audioDuration : 5; 

        // Temporizador para volver a la normalidad
        setTimeout(() => {
            console.log("JS: Finalizing special event.");
            specialOverlay.style.display = 'none';
            faceCanvas.style.display = 'block';
            isSpecialEventActive = false;
        }, displayDuration * 1000);
    }

    function setupNextTrigger() {
        // --- Configuración Personalizable del Evento Especial ---
        const minSeconds = 180; // Mínimo de segundos para esperar (3 minutos)
        const maxSeconds = 300; // Máximo de segundos para esperar (5 minutos)

        const randomDelay = Math.random() * (maxSeconds - minSeconds) + minSeconds;
        console.log(`JS: Next special event scheduled in ${Math.round(randomDelay)} seconds.`);

        setTimeout(() => {
            triggerSpecialEvent();
            // Una vez disparado, configurar el siguiente
            setupNextTrigger();
        }, randomDelay * 1000);
    }
    // --- FIN de la lógica del Evento Especial ---


    // --- Inicialización de la Página ---
    console.log("JS: Document loaded. Initializing.");
    animateFace();
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(pollDetectionStatus, 500);
    console.log("JS: Initial polling started.");
    if (interactionVideo) {
        videoContainer.style.display = "none";
    } else {
        console.error("JS: interactionVideo element not found!");
    }
    document.getElementById('main-container').style.display = "flex";

    // --- NUEVO: Iniciar el ciclo del evento especial aleatorio ---
    if (specialOverlay && specialAudio) {
        setupNextTrigger();
    } else {
        console.error("JS: specialOverlay or specialAudio element not found! The special event will not run.");
    }

    const skipButton = document.getElementById('button-skip-video-main');
    if (skipButton) {
        skipButton.addEventListener('click', restartInteraction);
    }
});