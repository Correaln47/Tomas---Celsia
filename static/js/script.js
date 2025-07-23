document.addEventListener("DOMContentLoaded", function () {
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
    let currentEmotion = "happy";
    let isAudioPlaying = false;
    let isShowingStaticEmotion = true;
    let currentForcedVideoProcessed = null;
    let audioContext = null;
    let audioAnalyser = null;
    let audioDataArray = null;
    let isAnalyserReady = false;

    let looping = false
    let firstLoop = true

    // --- NUEVO: Función para ajustar la resolución del canvas ---
    /**
     * Ajusta la resolución interna del canvas para que coincida con su tamaño de visualización,
     * eliminando el pixelado. Vuelve a dibujar la cara para reflejar el cambio.
     */
    function resizeCanvasAndRedraw() {
        const { width, height } = faceCanvas.getBoundingClientRect();

        // Si el tamaño real es 0, no hagas nada (evita errores si está oculto)
        if (width === 0 || height === 0) return;

        // Comprueba si la resolución interna ya coincide para evitar trabajo innecesario
        if (faceCanvas.width !== width || faceCanvas.height !== height) {
            faceCanvas.width = width;
            faceCanvas.height = height;
            console.log(`Canvas HD activado. Resolución: ${width}x${height}`);
        }

        // Vuelve a dibujar el estado actual de la cara con la nueva resolución
        if (isShowingStaticEmotion) {
            drawStaticEmotionFace(ctx, currentEmotion);
        } else if (!isAudioPlaying) {
            // Si no está sonando nada, dibuja la cara "neutra" animada.
            drawAnimatedFace(0);

        }
        // Si el audio está sonando, el bucle 'animateFace' se encargará de redibujar.
    }

    // --- Precargar y "calentar" el video del evento especial ---
    if (randomEventVideo) {
        randomEventVideo.preload = 'auto';
        randomEventVideo.src = '/static/special/event.mp4';
        randomEventVideo.addEventListener('canplaythrough', () => {
            console.log("Special event video is ready for smooth playback.");
        }, { once: true });
        randomEventVideo.load();
    }

    // --- Función para dibujar la cara estática de la emoción (Sin cambios) ---
    function drawStaticEmotionFace(ctx, emotion) {

        // emotion = "sad"
        const cw = ctx.canvas.width;
        const ch = ctx.canvas.height;

        ctx.clearRect(0, 0, cw, ch);
        ctx.fillStyle = "black";
        ctx.strokeStyle = "black";
        ctx.lineWidth = Math.max(5, cw * 0.015);

        // --- Parámetros de la Cara ---
        const faceCenterX = cw / 2;
        const faceCenterY = ch / 2;

        // Ojos
        const eyeOffsetY = ch * -0.2;
        const eyeSeparation = cw * 0.5;
        const baseEyeWidth = cw * 0.15;
        let baseEyeHeight = ch * 0.15;

        if (emotion === "surprise") {
            baseEyeHeight *= 1.2;
        }

        const leftEyeX = faceCenterX - (eyeSeparation / 2);
        const rightEyeX = faceCenterX + (eyeSeparation / 2);
        const eyeY = faceCenterY + eyeOffsetY;
        ctx.fillRect(leftEyeX - baseEyeWidth / 2, eyeY - baseEyeHeight / 2, baseEyeWidth, baseEyeHeight);
        ctx.fillRect(rightEyeX - baseEyeWidth / 2, eyeY - baseEyeHeight / 2, baseEyeWidth, baseEyeHeight);

        // Cejas
        const eyebrowOffsetY = eyeY - baseEyeHeight * 0.8;
        const eyebrowLength = baseEyeWidth * 1.2;
        const eyebrowTilt = ch * 0.08;

        if (emotion === "angry") {
            ctx.beginPath();
            ctx.moveTo(leftEyeX - eyebrowLength / 2, eyebrowOffsetY - eyebrowTilt / 2);
            ctx.lineTo(leftEyeX + eyebrowLength / 2, eyebrowOffsetY + eyebrowTilt / 2);
            ctx.moveTo(rightEyeX - eyebrowLength / 2, eyebrowOffsetY + eyebrowTilt / 2);
            ctx.lineTo(rightEyeX + eyebrowLength / 2, eyebrowOffsetY - eyebrowTilt / 2);
            ctx.stroke();
        } else if (emotion === "fear") {
            ctx.beginPath();
            ctx.moveTo(leftEyeX - eyebrowLength / 2, eyebrowOffsetY + eyebrowTilt / 2);
            ctx.lineTo(leftEyeX + eyebrowLength / 2, eyebrowOffsetY - eyebrowTilt / 2);
            ctx.moveTo(rightEyeX - eyebrowLength / 2, eyebrowOffsetY - eyebrowTilt / 2);
            ctx.lineTo(rightEyeX + eyebrowLength / 2, eyebrowOffsetY + eyebrowTilt / 2);
            ctx.stroke();
        }

        // Boca
        const mouthOffsetY = ch * 0.2;
        const baseMouthRadiusX = cw * 0.25;
        const baseMouthRadiusY = ch * 0.1;
        const mouthCenterX = faceCenterX;
        const mouthCenterY = faceCenterY + mouthOffsetY;

        ctx.beginPath();
        switch (emotion) {
            case "happy":
                ctx.ellipse(mouthCenterX, mouthCenterY, baseMouthRadiusX, baseMouthRadiusY, 0, 0, Math.PI);
                ctx.stroke();
                break;
            case "sad":
                ctx.ellipse(mouthCenterX, mouthCenterY, baseMouthRadiusX, baseMouthRadiusY, 0, Math.PI, 0);
                ctx.stroke();
                break;
            case "surprise":
            case "fear":
                ctx.ellipse(mouthCenterX, mouthCenterY, baseMouthRadiusX, baseMouthRadiusY * 1.2, 0, 0, Math.PI * 2);
                ctx.fill();
                break;
            case "disgust":
                const startX = mouthCenterX - baseMouthRadiusX;
                const endX = mouthCenterX + baseMouthRadiusX;
                const mouthY = mouthCenterY + baseMouthRadiusY * 0.5;
                const amplitude = baseMouthRadiusY;
                ctx.moveTo(startX, mouthY);
                ctx.quadraticCurveTo(mouthCenterX - baseMouthRadiusX / 2, mouthY - amplitude, mouthCenterX, mouthY);
                ctx.quadraticCurveTo(mouthCenterX + baseMouthRadiusX / 2, mouthY + amplitude, endX, mouthY);
                ctx.stroke();
                break;
            case "angry":
            case "neutral":
            default:
                ctx.moveTo(mouthCenterX - baseMouthRadiusX, mouthCenterY);
                ctx.lineTo(mouthCenterX + baseMouthRadiusX, mouthCenterY);
                ctx.stroke();
                break;
        }
    }

    // --- Función para dibujar la cara animada (parlante) (Sin Cambios) ---
    function drawAnimatedFace(amplitude = 0) {
        const cw = faceCanvas.width;
        const ch = faceCanvas.height;

        // Si no hay tamaño, no intentes dibujar.
        if (cw === 0 || ch === 0) return;

        ctx.clearRect(0, 0, cw, ch);

        const t = Date.now() / 1000;
        const floatOffset = (ch * 0.01) * Math.sin(t * 0.8);

        // Ojos
        const eyeOffsetY = ch * -0.2;
        const eyeSeparation = cw * 0.5;
        const baseEyeWidth = cw * 0.15;
        let baseEyeHeight = ch * 0.15;
        ctx.fillStyle = "black";
        baseEyeHeight = Math.max(baseEyeHeight * 0.4, baseEyeHeight - (amplitude * baseEyeHeight * 0.6));

        const eyeY = (ch / 2) + eyeOffsetY + floatOffset;
        ctx.fillRect((cw / 2) - (eyeSeparation / 2) - baseEyeWidth / 2, eyeY - baseEyeHeight / 2, baseEyeWidth, baseEyeHeight);
        ctx.fillRect((cw / 2) + (eyeSeparation / 2) - baseEyeWidth / 2, eyeY - baseEyeHeight / 2, baseEyeWidth, baseEyeHeight);

        // Boca parlante
        const mouthCenterY = (ch / 2) + (ch * 0.2) + floatOffset;
        let mouthRadiusX = cw * 0.25;
        let mouthRadiusY = ch * 0.1;
        ctx.beginPath();
        ctx.lineWidth = Math.max(5, cw * 0.015);

        mouthRadiusY = (mouthRadiusY * 0.1) + (amplitude * mouthRadiusY * 1.5);
        mouthRadiusX += (amplitude * mouthRadiusX * 0.2);
        ctx.ellipse(cw / 2, mouthCenterY, mouthRadiusX, mouthRadiusY, 0, 0, Math.PI * 2);
        ctx.fillStyle = "black";
        ctx.fill();
    }

    // --- Lógica de Audio (Sin cambios) ---
    function setupAudioAnalyser(audioElement) {
        if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
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

    // --- Bucle de Animación ---
    function animateFace() {
        requestAnimationFrame(animateFace);

        if (isShowingStaticEmotion) {
            return;
        }

        const amplitude = isAudioPlaying && isAnalyserReady ? getAverageAmplitude() : 0;

        if (videoContainer.style.display !== "flex" && randomEventVideo.style.display !== 'block') {
            drawAnimatedFace(amplitude);
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

    // --- Lógica Principal de Interacción (Sin cambios) ---
    function pollDetectionStatus() {

        fetch('/get_predete_emotion').then(res => res.ok ? res.json() : Promise.reject(res.status)).then((data) => {
            // console.log(`Predetermined emotion: ${data.emotion}`);
            if (data.emotion !== "neutral") {
                isShowingStaticEmotion = true;
                drawStaticEmotionFace(ctx, data.emotion);

            }
            else {
                isShowingStaticEmotion = false;
                drawAnimatedFace(0);
            }

        })

        fetch('/get_video_loop_state').then(res => res.ok ? res.json() : Promise.reject(res.status))
            .then(data => {
                console.log(data)
                if (data.looping) {
                    if (firstLoop) {
                        looping = true
                        triggerVideo()
                        firstLoop = false
                    }
                }
                else {
                    firstLoop = true
                    looping = false
                }
            })

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
                        handleEmotionDetection(data.emotion);
                    } else if (!data.detected && snapshotContainer.style.display !== 'none') {
                        videoFeed.style.display = "block";
                        snapshotContainer.style.display = "none";
                    }
                }
            }).catch(err => console.error("Polling error:", err));


    }

    function handleEmotionDetection(emotion) {
        isShowingStaticEmotion = true;
        currentEmotion = emotion;

        videoFeed.style.display = "none";
        snapshotContainer.style.display = "block";
        snapshotImg.src = "/snapshot?" + Date.now();
        emotionText.innerText = "Emoción: " + currentEmotion.toUpperCase();

        drawStaticEmotionFace(ctx, currentEmotion);

        setTimeout(() => {
            isShowingStaticEmotion = false;
            triggerAudio(currentEmotion);
        }, 2000);
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

    function playSpecificVideo(videoPath) {
        const isSpecial = videoPath.includes('special/event.mp4');
        console.log(`Playing ${isSpecial ? 'special' : 'normal'} video: ${videoPath}`);

        if (isSpecial) {
            faceCanvas.style.display = 'none';
            randomEventVideo.style.display = 'block';
            randomEventVideo.currentTime = 0;
            const onEnd = () => {
                randomEventVideo.style.display = 'none';
                faceCanvas.style.display = 'block';
                currentForcedVideoProcessed = null;
            };
    if (looping) {
             triggerVideo()
            }
            randomEventVideo.onended = onEnd;
            randomEventVideo.onerror = onEnd;
            const playPromise = randomEventVideo.play();
            if (playPromise !== undefined) {
                playPromise.catch(e => {
                    console.error("Error playing special video:", e);
                    onEnd();
                });
            }
            
        } else {
            mainContainer.style.display = 'none';
            videoContainer.style.display = 'flex';
            interactionVideo.src = videoPath.startsWith('/static') ? videoPath : `/static/video/${videoPath}`;

            // if (looping) {
                // interactionVideo.onended = triggerVideo()
            // }
            // else {
                interactionVideo.onended = restartInteraction;

            // }

            interactionVideo.onerror = restartInteraction;
            interactionVideo.play().catch(e => { console.error("Error playing interaction video:", e); restartInteraction(); });
        }
    }

    function restartInteraction() {
        window.location.reload();
    }

    // --- MODIFICADO: Inicialización ---
    // 1. Ajustar la resolución del canvas al cargar la página.
    resizeCanvasAndRedraw();
    // 2. Ajustar la resolución si cambia el tamaño de la ventana (ej. rotar tablet).
    window.addEventListener('resize', resizeCanvasAndRedraw);
    // 3. Iniciar el bucle de animación.
    animateFace();
    // 4. Iniciar el sondeo del estado del servidor.
    setInterval(pollDetectionStatus, 500);

});