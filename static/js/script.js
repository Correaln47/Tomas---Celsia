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
    let isAudioPlaying = false;
    let pollInterval; 
    let currentForcedVideoProcessed = null;
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
     function playAudio(url) { /* ... (igual que antes, devuelve Promise) ... */ }
     // --- FIN Funciones de dibujo y audio ---

    function pollDetectionStatus() {
        fetch('/detection_status')
            .then(res => {
                if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
                return res.json();
            })
            .then(data => {
                if (data.forced_video && data.forced_video !== currentForcedVideoProcessed) {
                    currentForcedVideoProcessed = data.forced_video; 
                    console.log("JS: FORCED VIDEO received:", data.forced_video);
                    document.getElementById('main-container').style.display = "none";
                    videoContainer.style.display = "flex"; 
                    const videoUrl = `/static/video/${data.forced_video}`;
                    playSpecificVideo(videoUrl); // Esta función llama a restartInteraction al final
                } else if (data.detected && !currentForcedVideoProcessed) { 
                    currentEmotion = data.emotion;
                    console.log("JS: DETECTION complete. Emotion:", currentEmotion);
                    videoFeed.style.display = "none"; snapshotContainer.style.display = "block";
                    snapshotImg.src = "/snapshot?" + new Date().getTime();
                    emotionText.innerText = "Emoción: " + currentEmotion.toUpperCase();
                    drawFace(currentEmotion, currentEmotion, 0);
                    triggerAudio(currentEmotion); // Llama a triggerVideo, que llama a restartInteraction
                } else if (!data.detected && !currentForcedVideoProcessed) { 
                     currentEmotion = "neutral";
                     // Solo restaurar UI si no hay video en reproducción
                     if (videoContainer.style.display === "none") {
                         if (videoFeed.style.display === "none") { // Solo si no se está mostrando ya
                             document.getElementById('main-container').style.display = "flex";
                             videoFeed.style.display = "block";    
                             snapshotContainer.style.display = "none"; 
                             emotionText.innerText = "";
                             drawFace("neutral", "neutral", 0); 
                         }
                     }
                }
            })
            .catch(err => {
                console.error("JS: Error polling detection status:", err);
                currentEmotion = "neutral";
                // No reiniciar el polling aquí para evitar bucles si el servidor está mal
            });
    }
    
    function triggerAudio(emotion) {
        fetch(`/get_random_audio?emotion=${emotion}`)
            .then(res => res.json())
            .then(data => {
                if (data.audio_url) {
                    playAudio(data.audio_url)
                        .then(() => { if (!currentForcedVideoProcessed) triggerVideo(); })
                        .catch(err => { console.error("JS: Error playAudio promise:", err); if (!currentForcedVideoProcessed) triggerVideo(); });
                } else { console.error("JS: No audio file for emotion:", emotion); if (!currentForcedVideoProcessed) triggerVideo(); }
            })
            .catch(err => { console.error("JS: Error fetching audio URL:", err); if (!currentForcedVideoProcessed) triggerVideo(); });
    }
  
    function triggerVideo() { // Reproduce video aleatorio
        if (currentForcedVideoProcessed) return; // No reproducir si hay uno forzado
        console.log("JS: Triggering RANDOM video.");
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
        fetch('/get_random_video').then(res => res.json())
            .then(data => {
                if (data.video_url) {
                    interactionVideo.src = data.video_url;
                    interactionVideo.onerror = (e) => { console.error("JS: ERROR Random Video:", e); restartInteraction(); };
                    interactionVideo.onended = () => { console.log("JS: Random Video ended."); restartInteraction(); };
                    interactionVideo.play().catch(e => { console.error("JS: Error starting random video:", e); restartInteraction(); });
                } else { console.error("JS: No random video file found."); restartInteraction(); }
            })
            .catch(err => { console.error("JS: Error fetching random video URL:", err); restartInteraction(); });
    }

    function playSpecificVideo(videoUrl) {
        console.log(`JS: Playing SPECIFIC video: ${videoUrl}`);
        document.getElementById('main-container').style.display = "none";
        videoContainer.style.display = "flex";
        interactionVideo.src = videoUrl;
        interactionVideo.onerror = (e) => { console.error("JS: ERROR Specific Video:", e); restartInteraction(); };
        interactionVideo.onended = () => { console.log("JS: Specific Video ended."); restartInteraction(); };
        interactionVideo.play().catch(e => { console.error("JS: Error starting specific video:", e); restartInteraction(); });
    }
  
    function restartInteraction() {
        console.log("JS: RESTARTING interaction sequence...");
        isAudioPlaying = false; audioAnalyser = null; audioDataArray = null;
        currentForcedVideoProcessed = null; 
        currentEmotion = "neutral"; drawFace("neutral", "neutral", 0); 

        // Detener y limpiar el video
        interactionVideo.pause();
        interactionVideo.removeAttribute('src'); 
        interactionVideo.load(); // Importante para que el navegador no mantenga el video anterior en memoria
        
        // No necesitamos llamar a fetch('/restart') desde AQUÍ,
        // ya que el servidor se reinicia por el botón "skip" o por su propia lógica interna.
        // El polling recogerá el estado reiniciado del servidor.

        document.getElementById('main-container').style.display = "flex";
        videoContainer.style.display = "none";
        videoFeed.style.display = "block"; 
        snapshotContainer.style.display = "none"; 
        emotionText.innerText = ""; 

        if (pollInterval) clearInterval(pollInterval); // Limpiar el intervalo existente
        pollInterval = setInterval(pollDetectionStatus, 1000); // Reiniciar el polling
        console.log("JS: Polling (re)started by restartInteraction().");
    }
  
    console.log("JS: Document loaded. Initializing.");
    drawFace("neutral", "neutral", 0); 
    animateFace(); 
    // Iniciar el polling después de que todo esté configurado
    if (pollInterval) clearInterval(pollInterval); // Asegurar que no haya uno corriendo
    pollInterval = setInterval(pollDetectionStatus, 1000);
    console.log("JS: Initial polling started.");
});