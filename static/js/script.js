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
    const specialOverlay = document.getElementById('specialOverlay');
    const specialVideo = document.getElementById('specialVideo');


    // --- Variables de Estado ---
    let currentEmotion = "neutral";
    let isAudioPlaying = false;
    let pollInterval;
    let currentForcedVideoProcessed = null;
    let audioContext = null;
    let audioAnalyser = null;
    let audioDataArray = null;
    let isAnalyserReady = false;
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
            drawStroke = true;
        } else if (emotion === "sad") {
            startAngle = Math.PI;
            endAngle = 0;
            drawStroke = true;
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
        } else {
            startAngle = 0;
            endAngle = Math.PI;
            adjustedMouthRadiusY = baseMouthRadiusY * 0.1;
            drawStroke = true;
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
            isAnalyserReady = false;
        }
    }

    function getAverageAmplitude() {
        if (!isAnalyserReady || !audioDataArray) return 0;
        audioAnalyser.getByteFrequencyData(audioDataArray);
        const lowerHalf = audioDataArray.slice(0, audioDataArray.length / 2);
        const average = lowerHalf.reduce((sum, value) => sum + value, 0) / lowerHalf.length;
        return average / 255;
    }

    function animateFace() {
        const amplitude = isAudioPlaying && isAnalyserReady ? getAverageAmplitude() : 0;
        const mouthState = isAudioPlaying ? "talking" : "neutral";
        if (videoContainer.style.display !== "flex" && !isSpecialEventActive) {
            drawFace(currentEmotion, mouthState, amplitude);
        } else {
            ctx.clearRect(0, 0, faceCanvas.width, faceCanvas.height);
        }
        requestAnimationFrame(animateFace);
    }

    async function playAudio(url) {
        return new Promise((resolve, reject) => {
            const audio = new Audio(url);
            setupAudioAnalyser(audio);
            audio.onplay = () => { isAudioPlaying = true; };
            audio.onended = () => {
                isAudioPlaying = false;
                isAnalyserReady = false;
                resolve();
            };
            audio.onerror = (e) => {
                isAudioPlaying = false;
                isAnalyserReady = false;
                reject(e);
            };
            audio.play().catch(e => {
                isAudioPlaying = false;
                isAnalyserReady = false;
                reject(e);
            });
        });
    }

    // --- Lógica Principal de Interacción ---

    function pollDetectionStatus() {
        if (isSpecialEventActive) return;

        fetch('/detection_status').then(res => {
            if (!res.ok) {
                console.error(`JS: HTTP error! status: ${res.status}`);
                // Simplified error handling
                return null;
            }
            return res.json();
        }).then(data => {
            if (!data) return;

            if (data.restart_requested) {
                restartInteraction();
                return;
            }

            if (data.forced_video && data.forced_video !== currentForcedVideoProcessed) {
                currentForcedVideoProcessed = data.forced_video;
                const videoUrl = `/static/video/${data.forced_video}`;
                playSpecificVideo(videoUrl);
                return;
            }

            if (!currentForcedVideoProcessed) {
                if (data.detected && !isAudioPlaying && interactionVideo.paused) {
                    currentEmotion = data.emotion;
                    videoFeed.style.display = "none";
                    snapshotContainer.style.display = "block";
                    snapshotImg.src = "/snapshot?" + new Date().getTime();
                    emotionText.innerText = "Emoción: " + currentEmotion.toUpperCase();
                    triggerAudio(currentEmotion);
                } else if (!data.detected && snapshotContainer.style.display !== 'none') {
                    videoFeed.style.display = "block";
                    snapshotContainer.style.display = "none";
                    emotionText.innerText = "";
                }
            }
        }).catch(err => {
            console.error("JS: Error polling detection status:", err);
        });
    }

    function triggerAudio(emotion) {
        if (isSpecialEventActive || isAudioPlaying) return;
        
        const audioEmotion = ["disgust", "no_face"].includes(emotion) || !emotion ? "neutral" : emotion;
        fetch(`/get_random_audio?emotion=${audioEmotion}`)
            .then(res => res.ok ? res.json() : Promise.reject(res.status))
            .then(data => {
                if (data.audio_url) {
                    playAudio(data.audio_url)
                        .then(() => !currentForcedVideoProcessed && triggerVideo())
                        .catch(() => !currentForcedVideoProcessed && triggerVideo());
                } else {
                    triggerVideo();
                }
            }).catch(() => !currentForcedVideoProcessed && triggerVideo());
    }

    function triggerVideo() {
        if (isSpecialEventActive || currentForcedVideoProcessed) return;

        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
        
        fetch('/get_random_video')
            .then(res => res.ok ? res.json() : Promise.reject(res.status))
            .then(data => {
                if (data.video_url) {
                    interactionVideo.src = data.video_url;
                    interactionVideo.play().catch(restartInteraction);
                } else {
                    restartInteraction();
                }
            }).catch(restartInteraction);

        interactionVideo.onended = restartInteraction;
        interactionVideo.onerror = restartInteraction;
    }

    function playSpecificVideo(videoUrl) {
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
        interactionVideo.src = videoUrl;
        interactionVideo.play().catch(restartInteraction);

        interactionVideo.onended = () => {
            currentForcedVideoProcessed = null;
            restartInteraction();
        };
        interactionVideo.onerror = () => {
            currentForcedVideoProcessed = null;
            restartInteraction();
        };
    }

    function restartInteraction() {
        console.log("JS: Restarting interaction by reloading the page.");
        window.location.reload();
    }


    // --- Lógica del Evento Especial Aleatorio ---

    function triggerSpecialEvent() {
        if (isAudioPlaying || (interactionVideo && !interactionVideo.paused) || currentForcedVideoProcessed) {
            setTimeout(setupNextTrigger, 30 * 1000); // Postpone
            return;
        }

        console.log("JS: Activating special event...");
        isSpecialEventActive = true;

        faceCanvas.style.display = 'none';
        specialOverlay.style.display = 'block';

        specialVideo.src = '/static/special/event.mp4'; // Asegúrate que esta ruta es correcta
        specialVideo.currentTime = 0;
        
        // --- NUEVO: Enviar señal al backend cuando el video comienza ---
        specialVideo.onplaying = () => {
            console.log("JS: Special event video has started. Sending trigger to backend.");
            fetch('/trigger_special_event', { method: 'POST' })
                .then(response => {
                    if (!response.ok) console.error("JS: Backend failed to acknowledge movement trigger.");
                    else console.log("JS: Backend acknowledged movement trigger.");
                })
                .catch(error => console.error('JS: Error sending trigger signal:', error));
            
            // Asegurarse que solo se ejecute una vez
            specialVideo.onplaying = null; 
        };

        specialVideo.onended = () => {
            console.log("JS: Special event finished.");
            specialOverlay.style.display = 'none';
            faceCanvas.style.display = 'block';
            isSpecialEventActive = false;
            specialVideo.removeAttribute('src');
            specialVideo.load();
        };
        
        specialVideo.onerror = () => {
             console.error("JS: Error playing special video.");
             specialVideo.onended(); // Reutiliza la lógica de finalización para limpiar
        };

        specialVideo.play().catch(e => specialVideo.onerror());
    }

    function setupNextTrigger() {
        // Chequeo rápido para ver si la función debe correr, basado en la config del otro servidor.
        // No podemos leer la config directamente, pero si el usuario deshabilita el evento,
        // esto simplemente seguirá corriendo en el cliente sin hacer nada visible, lo cual es aceptable.
        const minSeconds = 120;
        const maxSeconds = 180;
        const randomDelay = (Math.random() * (maxSeconds - minSeconds) + minSeconds) * 1000;
        
        console.log(`JS: Next special event check in ${Math.round(randomDelay / 1000)}s.`);
        setTimeout(() => {
            triggerSpecialEvent();
            setupNextTrigger(); // Re-schedule the next one
        }, randomDelay);
    }

    // --- Inicialización ---
    console.log("JS: Document loaded. Initializing.");
    animateFace();
    pollInterval = setInterval(pollDetectionStatus, 500);
    
    // Iniciar el ciclo del evento especial si los elementos existen
    if (specialOverlay && specialVideo) {
        setupNextTrigger();
    } else {
        console.error("JS: specialOverlay or specialVideo element not found! The special event will not run.");
    }
});