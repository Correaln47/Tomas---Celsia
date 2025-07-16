document.addEventListener("DOMContentLoaded", function() {
    // --- Selectores de Elementos del DOM ---
    const mainContainer = document.getElementById('main-container');
    const videoFeed = document.getElementById('videoFeed');
    const snapshotContainer = document.getElementById('snapshot-container');
    const snapshotImg = document.getElementById('snapshot');
    const emotionText = document.getElementById('emotionText');
    const faceCanvas = document.getElementById('faceCanvas');
    const videoContainer = document.getElementById('video-container');
    const interactionVideo = document.getElementById('interactionVideo');
    // --- MODIFICADO: Selector para el nuevo video del evento especial ---
    const randomEventVideo = document.getElementById('randomEventVideo'); 
    const ctx = faceCanvas.getContext('2d');
    
    // --- Variables de Estado ---
    let currentEmotion = "neutral";
    let isAudioPlaying = false;
    let currentForcedVideoProcessed = null;
    let audioContext = null;
    let audioAnalyser = null;
    let audioDataArray = null;
    let isAnalyserReady = false;

    // --- Funciones de Dibujo y Audio (sin cambios) ---
    function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
        const cw = faceCanvas.width;
        const ch = faceCanvas.height;
        ctx.clearRect(0, 0, cw, ch);
        const t = Date.now() / 1000;
        const floatOffset = (ch * 0.01) * Math.sin(t * 0.8);
        const eyeOffsetY = ch * -0.2;
        const eyeSeparation = cw * 0.5;
        const baseEyeWidth = cw * 0.15;
        let baseEyeHeight = ch * 0.15;
        ctx.fillStyle = "black";
        if (mouthState === "talking") {
            baseEyeHeight = Math.max(baseEyeHeight * 0.4, baseEyeHeight - (amplitude * baseEyeHeight * 0.6));
        } else if (emotion === "surprise") {
            baseEyeHeight *= 1.2;
        }
        const eyeY = (ch / 2) + eyeOffsetY + floatOffset;
        ctx.fillRect((cw / 2) - (eyeSeparation / 2) - baseEyeWidth / 2, eyeY - baseEyeHeight / 2, baseEyeWidth, baseEyeHeight);
        ctx.fillRect((cw / 2) + (eyeSeparation / 2) - baseEyeWidth / 2, eyeY - baseEyeHeight / 2, baseEyeWidth, baseEyeHeight);
        const mouthCenterY = (ch / 2) + (ch * 0.2) + floatOffset;
        let mouthRadiusX = cw * 0.25;
        let mouthRadiusY = ch * 0.1;
        ctx.beginPath();
        ctx.lineWidth = Math.max(5, cw * 0.015);
        if (mouthState === "talking") {
            mouthRadiusY = (mouthRadiusY * 0.1) + (amplitude * mouthRadiusY * 1.5);
            mouthRadiusX += (amplitude * mouthRadiusX * 0.2);
            ctx.ellipse(cw / 2, mouthCenterY, mouthRadiusX, mouthRadiusY, 0, 0, Math.PI * 2);
            ctx.fillStyle = "black";
            ctx.fill();
        } else {
            ctx.moveTo(cw/2 - mouthRadiusX, mouthCenterY);
            ctx.lineTo(cw/2 + mouthRadiusX, mouthCenterY);
            ctx.stroke();
        }
    }

    function setupAudioAnalyser(audioElement) {
        if (!audioContext) audioContext = new(window.AudioContext || window.webkitAudioContext)();
        if (audioContext.state === 'suspended') audioContext.resume();
        try {
            const source = audioContext.createMediaElementSource(audioElement);
            audioAnalyser = audioContext.createAnalyser();
            audioAnalyser.fftSize = 256;
            audioDataArray = new Uint8Array(audioAnalyser.frequencyBinCount);
            source.connect(audioAnalyser);
            audioAnalyser.connect(audioContext.destination);
            isAnalyserReady = true;
        } catch (e) {
            isAnalyserReady = false;
        }
    }

    function getAverageAmplitude() {
        if (!isAnalyserReady || !audioDataArray) return 0;
        audioAnalyser.getByteFrequencyData(audioDataArray);
        return audioDataArray.slice(0, audioDataArray.length / 2).reduce((s, v) => s + v, 0) / (audioDataArray.length / 2) / 255;
    }

    function animateFace() {
        requestAnimationFrame(animateFace);
        const amplitude = isAudioPlaying && isAnalyserReady ? getAverageAmplitude() : 0;
        const mouthState = isAudioPlaying ? "talking" : "neutral";
        
        // --- MODIFICADO: No dibujar la cara si algún video está activo ---
        if (videoContainer.style.display !== "flex" && randomEventVideo.style.display !== 'block') {
            drawFace(currentEmotion, mouthState, amplitude);
        } else {
            ctx.clearRect(0, 0, faceCanvas.width, faceCanvas.height);
        }
    }

    async function playAudio(url) {
        return new Promise((resolve, reject) => {
            const audio = new Audio(url);
            setupAudioAnalyser(audio);
            audio.onplay = () => isAudioPlaying = true;
            audio.onended = () => { isAudioPlaying = false; resolve(); };
            audio.onerror = () => { isAudioPlaying = false; reject(); };
            audio.play().catch(reject);
        });
    }

    // --- Lógica Principal de Interacción ---

    function pollDetectionStatus() {
        fetch('/detection_status').then(res => res.ok ? res.json() : Promise.reject(res.status))
        .then(data => {
            if (data.restart_requested) {
                return restartInteraction();
            }

            if (data.forced_video && data.forced_video !== currentForcedVideoProcessed) {
                console.log(`JS: Forced video received: ${data.forced_video}`);
                currentForcedVideoProcessed = data.forced_video;
                playSpecificVideo(data.forced_video);
                return;
            }

            if (!currentForcedVideoProcessed) {
                // --- MODIFICADO: Chequea el nuevo video del evento especial ---
                if (data.detected && !isAudioPlaying && interactionVideo.paused && randomEventVideo.paused) {
                    currentEmotion = data.emotion;
                    videoFeed.style.display = "none";
                    snapshotContainer.style.display = "block";
                    snapshotImg.src = "/snapshot?" + Date.now();
                    emotionText.innerText = "Emoción: " + currentEmotion.toUpperCase();
                    triggerAudio(currentEmotion);
                } else if (!data.detected && snapshotContainer.style.display !== 'none') {
                    videoFeed.style.display = "block";
                    snapshotContainer.style.display = "none";
                }
            }
        }).catch(err => console.error("JS: Polling error:", err));
    }

    function triggerAudio(emotion) {
        if (isAudioPlaying) return;
        const audioEmotion = ["disgust", "no_face"].includes(emotion) || !emotion ? "neutral" : emotion;
        fetch(`/get_random_audio?emotion=${audioEmotion}`)
        .then(res => res.ok ? res.json() : Promise.reject())
        .then(data => {
            if (data.audio_url) {
                playAudio(data.audio_url).finally(triggerVideo);
            } else {
                triggerVideo();
            }
        }).catch(triggerVideo);
    }

    function triggerVideo() {
        if (currentForcedVideoProcessed) return;
        fetch('/get_random_video').then(res => res.ok ? res.json() : Promise.reject())
        .then(data => {
            if (data.video_url) {
                playSpecificVideo(data.video_url);
            } else {
                restartInteraction();
            }
        }).catch(restartInteraction);
    }

    // --- NUEVO: Lógica optimizada para reproducir cualquier video ---
    function playSpecificVideo(videoPath) {
        const isSpecial = videoPath.includes('special/event.mp4');
        
        console.log(`Playing ${isSpecial ? 'special' : 'normal'} video: ${videoPath}`);

        if (isSpecial) {
            // Lógica para el video del evento especial (más eficiente)
            faceCanvas.style.display = 'none'; // Ocultar solo la cara
            randomEventVideo.style.display = 'block'; // Mostrar el video en su lugar
            randomEventVideo.src = `/static/${videoPath}`; 
            
            const onEnd = () => {
                randomEventVideo.style.display = 'none'; // Ocultar el video
                faceCanvas.style.display = 'block'; // Mostrar la cara de nuevo
                currentForcedVideoProcessed = null; // Permitir nuevas interacciones
            };
            
            randomEventVideo.onended = onEnd;
            randomEventVideo.onerror = onEnd;
            randomEventVideo.play().catch(e => { console.error("Error playing special video:", e); onEnd(); });

        } else {
            // Lógica para videos de interacción normales (sin cambios)
            mainContainer.style.display = 'none';
            videoContainer.style.display = 'flex';
            interactionVideo.src = videoPath.startsWith('/static') ? videoPath : `/static/video/${videoPath}`;
            
            interactionVideo.onended = restartInteraction;
            interactionVideo.onerror = restartInteraction;
            interactionVideo.play().catch(e => { console.error("Error playing interaction video:", e); restartInteraction(); });
        }
    }

    function restartInteraction() {
        console.log("JS: Restarting interaction by reloading the page.");
        window.location.reload();
    }

    // --- Inicialización ---
    console.log("JS: Document loaded. Initializing client.");
    animateFace();
    setInterval(pollDetectionStatus, 500);
});