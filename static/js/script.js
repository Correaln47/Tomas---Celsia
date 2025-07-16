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

    // --- Precargar y "calentar" el video del evento especial ---
    if (randomEventVideo) {
        randomEventVideo.preload = 'auto';
        randomEventVideo.src = '/static/special/event.mp4';
        
        // --- NUEVO: "Calentar" el decodificador de video ---
        // Esto fuerza al navegador a preparar el video para una reproducción fluida.
        randomEventVideo.addEventListener('canplaythrough', () => {
            console.log("Special event video is ready for smooth playback.");
            // Opcional: Descomentar la siguiente línea si el stuttering persiste.
            // randomEventVideo.play().then(() => { randomEventVideo.pause(); });
        }, { once: true }); // El listener se ejecuta solo una vez.

        randomEventVideo.load();
    }

    // (El resto del archivo permanece exactamente igual)

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
                currentForcedVideoProcessed = data.forced_video;
                playSpecificVideo(data.forced_video);
                return;
            }

            if (!currentForcedVideoProcessed) {
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
        }).catch(err => console.error("Polling error:", err));
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

    // --- Lógica de reproducción de video (CORREGIDA) ---
    function playSpecificVideo(videoPath) {
        const isSpecial = videoPath.includes('special/event.mp4');
        
        console.log(`Playing ${isSpecial ? 'special' : 'normal'} video: ${videoPath}`);

        if (isSpecial) {
            // Lógica corregida para el evento especial.
            faceCanvas.style.display = 'none'; 
            randomEventVideo.style.display = 'block';
            
            // Rebobinamos el video al inicio por si se reproduce varias veces.
            randomEventVideo.currentTime = 0;
            
            const onEnd = () => {
                randomEventVideo.style.display = 'none';
                faceCanvas.style.display = 'block'; 
                currentForcedVideoProcessed = null; 
            };
            
            randomEventVideo.onended = onEnd;
            randomEventVideo.onerror = onEnd;

            // Simplemente reproducimos el video, que ya debe estar cargado.
            const playPromise = randomEventVideo.play();
            if (playPromise !== undefined) {
                playPromise.catch(e => { 
                    console.error("Error playing special video:", e); 
                    onEnd(); 
                });
            }

        } else {
            // Lógica para videos normales (sin cambios).
            mainContainer.style.display = 'none';
            videoContainer.style.display = 'flex';
            interactionVideo.src = videoPath.startsWith('/static') ? videoPath : `/static/video/${videoPath}`;
            
            interactionVideo.onended = restartInteraction;
            interactionVideo.onerror = restartInteraction;
            interactionVideo.play().catch(e => { console.error("Error playing interaction video:", e); restartInteraction(); });
        }
    }

    function restartInteraction() {
        window.location.reload();
    }

    // --- Inicialización ---
    animateFace();
    setInterval(pollDetectionStatus, 500);
});