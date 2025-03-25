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

  let audioAnalyser = null;
  let audioDataArray = null;

  // --- Face Animation (draw a simple animated face) ---
  // Draw the face with dynamic eyes and a semi-oval mouth.
  function drawFace(emotion, mouthState = "neutral", amplitude = 0) {
    // Get the canvas width and height.
    const cw = faceCanvas.width;
    const ch = faceCanvas.height;
    
    // Floating offset for a gentle vertical oscillation (face floating in water).
    const t = Date.now() / 1000;
    const floatOffset = 10 * Math.sin(t * 0.5);
  
    // Clear the canvas.
    ctx.clearRect(0, 0, cw, ch);
  
    // --- Draw Eyes as Rectangles (Relative Coordinates) ---
    // Positions relative to canvas dimensions.
    const leftEyeX = cw * 0.2;
    const leftEyeY = ch * 0.3 + floatOffset;
    const rightEyeX = cw * 0.6;
    const rightEyeY = ch * 0.3 + floatOffset;
    // Base dimensions: fixed width, and vertical height proportional to the canvas.
    const baseEyeWidth = cw * 0.05;  // 5% of canvas width
    const baseEyeHeight = ch * 0.15;   // 15% of canvas height
    // Change only vertical dimension when talking.
    const eyeHeightChangeFactor = baseEyeHeight * 0.2; // up to 20% change
    let adjustedEyeHeight = baseEyeHeight;
    if (mouthState === "talking") {
      adjustedEyeHeight = baseEyeHeight - (amplitude * eyeHeightChangeFactor);
      // Ensure the eye height doesn't go below a minimum value (50% of base).
      if (adjustedEyeHeight < baseEyeHeight * 0.5) {
        adjustedEyeHeight = baseEyeHeight * 0.5;
      }
    }
    ctx.fillStyle = "black";
    ctx.fillRect(leftEyeX, leftEyeY, baseEyeWidth, adjustedEyeHeight);
    ctx.fillRect(rightEyeX, rightEyeY, baseEyeWidth, adjustedEyeHeight);
  
    // --- Draw Mouth as a Semi-Oval (Relative Coordinates) ---
    // Define the center of the mouth relative to the canvas.
    const mouthCenterX = cw * 0.5;
    const mouthCenterY = ch * 0.65 + floatOffset;
    // Base horizontal radius: 12.5% of canvas width; base vertical radius: 3% of canvas height.
    const baseMouthRadiusX = cw * 0.125;
    const baseMouthRadiusY = ch * 0.03;
    // Maximum adjustments based on amplitude.
    const mouthOpenFactorY = ch * 0.1; // up to 10% of canvas height extra vertically.
    const mouthOpenFactorX = cw * 0.05; // up to 5% of canvas width extra horizontally.
    let adjustedMouthRadiusY = baseMouthRadiusY;
    let adjustedMouthRadiusX = baseMouthRadiusX;
    if (mouthState === "talking") {
      adjustedMouthRadiusY = baseMouthRadiusY + amplitude * mouthOpenFactorY;
      adjustedMouthRadiusX = baseMouthRadiusX + amplitude * mouthOpenFactorX;
    } else if (mouthState === "happy" || mouthState === "sad") {
      // For other expressions, you could adjust these values further if desired.
      adjustedMouthRadiusY = baseMouthRadiusY;
      adjustedMouthRadiusX = baseMouthRadiusX;
    }
    
    // Draw the bottom half of an ellipse to represent the mouth.
    ctx.fillStyle = "red";
    ctx.beginPath();
    ctx.ellipse(mouthCenterX, mouthCenterY, adjustedMouthRadiusX, adjustedMouthRadiusY, 0, 0, Math.PI, false);
    ctx.fill();
    ctx.strokeStyle = "black";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.closePath();
  }
  
  function animateFace() {
    let mouthState = "neutral";
    let mouthAmplitude = 0; // Default amplitude (normalized between 0 and 1)
    
    if (isAudioPlaying && audioAnalyser) {
      audioAnalyser.getByteFrequencyData(audioDataArray);
      let sum = 0;
      for (let i = 0; i < audioDataArray.length; i++) {
        sum += audioDataArray[i];
      }
      let avg = sum / audioDataArray.length;
      mouthAmplitude = avg / 255; // Normalize amplitude.
      mouthState = "talking";
    } else if (currentEmotion === "happy") {
      mouthState = "happy";
    } else if (currentEmotion === "sad") {
      mouthState = "sad";
    }
    
    // Call drawFace with the current emotion, state, and computed amplitude.
    drawFace(currentEmotion, mouthState, mouthAmplitude);
    requestAnimationFrame(animateFace);
  }
  
  
  function animateFace() {
    let mouthState = "neutral";
    let mouthAmplitude = 0; // default amplitude value
    
    if (isAudioPlaying && audioAnalyser) {
      audioAnalyser.getByteFrequencyData(audioDataArray);
      let sum = 0;
      for (let i = 0; i < audioDataArray.length; i++) {
        sum += audioDataArray[i];
      }
      let avg = sum / audioDataArray.length;
      mouthAmplitude = avg / 255; // normalize amplitude (0 to 1)
      mouthState = "talking";
    } else if (currentEmotion === "happy") {
      mouthState = "happy";
    } else if (currentEmotion === "sad") {
      mouthState = "sad";
    }
    
    // Call the draw function with the computed parameters.
    drawFace(currentEmotion, mouthState, mouthAmplitude);
    requestAnimationFrame(animateFace);
  }
  

  
  
  animateFace();

  function setupAudioAnalyser(audioElement) {
    // Create an AudioContext (use webkitAudioContext for Safari)
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const track = audioContext.createMediaElementSource(audioElement);
    // Create an analyser node
    audioAnalyser = audioContext.createAnalyser();
    audioAnalyser.fftSize = 256;  // Smaller FFT size means faster updates but lower resolution
    const bufferLength = audioAnalyser.frequencyBinCount;
    audioDataArray = new Uint8Array(bufferLength);
    // Connect the audio element through the analyser to the output
    track.connect(audioAnalyser);
    audioAnalyser.connect(audioContext.destination);
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
          // Hide the live video feed and show the snapshot container
          videoFeed.style.display = "none";
          snapshotContainer.style.display = "block";
          // Force a refresh of the snapshot image (avoid caching issues)
          const newSrc = "/snapshot?" + new Date().getTime();
          console.log("Setting snapshot image src to:", newSrc);
          snapshotImg.src = newSrc;
          emotionText.innerText = "Emotion: " + currentEmotion;
          // Trigger audio playback (which then triggers video, etc.)
          triggerAudio(currentEmotion);
        }
      })
      .catch(err => console.error("Error polling detection status:", err));
  }
  let pollInterval = setInterval(pollDetectionStatus, 1000);

  // --- Play Emotion-Specific Audio ---
  function triggerAudio(emotion) {
    fetch(`/get_random_audio?category=emotion&emotion=${emotion}`)
      .then(res => res.json())
      .then(data => {
        if(data.audio_url) {
          playAudio(data.audio_url)
            .then(() => {
              // After audio ends, play the interaction video
              triggerVideo();
            })
            .catch(err => console.error("Error playing audio:", err));
        } else {
          console.error("No audio file found for emotion:", emotion);
          // If no audio, proceed to video
          triggerVideo();
        }
      })
      .catch(err => console.error("Error fetching audio URL:", err));
  }
  
  function playAudio(url) {
    return new Promise((resolve, reject) => {
      const audio = new Audio(url);
      audio.onplay = () => {
        setupAudioAnalyser(audio);
      };
      isAudioPlaying = true;
      audio.play();
      audio.onended = () => {
        isAudioPlaying = false;
        audioAnalyser = null;  // Clear the analyser once audio stops
        resolve();
      };
      audio.onerror = reject;
    });
  }

  // --- Trigger Interaction Video ---
  function triggerVideo() {
    // Hide snapshot and canvas, then show video container
    document.getElementById('main-container').style.display = "none";
    videoContainer.style.display = "flex";  // Use "flex" for proper flexbox styling
    fetch('/get_random_video')
      .then(res => res.json())
      .then(data => {
        if(data.video_url) {
          interactionVideo.src = data.video_url;
          interactionVideo.play();
          interactionVideo.onended = () => {
            // After video finishes, restart the interaction
            restartInteraction();
          };
        } else {
          console.error("No video file found.");
          restartInteraction();
        }
      })
      .catch(err => console.error("Error fetching video URL:", err));
  }
  
  
  // --- Restart Interaction ---
  function restartInteraction() {
    fetch('/restart')
      .then(() => {
        // Reload the page (or reset UI elements) to start over
        location.reload();
      })
      .catch(err => console.error("Error restarting interaction:", err));
  }
});
